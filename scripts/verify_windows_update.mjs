import assert from 'node:assert/strict'
import {execFileSync, spawn} from 'node:child_process'
import {createReadStream, readFileSync, statSync} from 'node:fs'
import {createServer} from 'node:http'
import {setTimeout as delay} from 'node:timers/promises'
import {chromium} from 'playwright'

const [executable, installer, signatureFile, version] = process.argv.slice(2)
const feedPort = 18451
const webviewPort = 18452
const projectName = 'Windows updater verification'
const signature = readFileSync(signatureFile, 'ascii').trim()
const packageBytes = statSync(installer).size
const executableLiteral = executable.replaceAll("'", "''")
const appProcesses = `Get-Process titan-wb -ErrorAction SilentlyContinue | Where-Object Path -eq '${executableLiteral}'`
let sendValidPackage = false

const server = createServer((request, response) => {
 if (request.url === '/beta.json') {
  response.setHeader('Content-Type', 'application/json')
  response.end(JSON.stringify({version, platforms:{'windows-x86_64':{
   url:`http://127.0.0.1:${feedPort}/Titan-setup.exe`, signature,
  }}}))
 } else if (request.url === '/Titan-setup.exe' && sendValidPackage) {
  response.setHeader('Content-Length', packageBytes)
  createReadStream(installer).pipe(response)
 } else if (request.url === '/Titan-setup.exe') {
  response.end('Intentionally different from the signed package')
 } else {
  response.writeHead(404).end()
 }
})

async function until(action, description, timeout = 90_000) {
 const deadline = Date.now() + timeout
 do {
  try {
   const result = await action()
   if (result) return result
  } catch { /* The process or WebView can be between startup stages. */ }
  await delay(500)
 } while (Date.now() < deadline)
 throw Error(`Timed out waiting for ${description}`)
}

async function connect() {
 const endpoint = `http://127.0.0.1:${webviewPort}`
 await until(async () => (await (await fetch(`${endpoint}/json/list`)).json())
  .some(target => target.type === 'page' && /tauri\.localhost/.test(target.url)), 'Titan WebView')
 const browser = await chromium.connectOverCDP(endpoint, {timeout:15_000})
 const page = browser.contexts().flatMap(context => context.pages()).find(tab => /tauri\.localhost/.test(tab.url()))
 assert(page, 'Titan WebView is attached')
 page.setDefaultTimeout(45_000)
 await page.waitForFunction(() => typeof window.__TAURI_INTERNALS__?.invoke === 'function')
 return {browser, page}
}

const config = page => page.evaluate(() => window.__TAURI_INTERNALS__.invoke('update_configuration'))
const powershell = command => execFileSync('powershell.exe', ['-NoProfile','-Command',command],
 {encoding:'utf8', timeout:15_000, windowsHide:true}).trim()
const launch = () => spawn(executable, [], {
 env:{...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS:
  `--remote-debugging-port=${webviewPort} --remote-debugging-address=127.0.0.1`},
})

await new Promise((resolve, reject) => {
 server.once('error', reject)
 server.listen(feedPort, '127.0.0.1', resolve)
})

const old = launch()
let spawnError
old.on('error', error => {spawnError = error})
let upgraded
try {
 const {browser, page} = await connect()
 if (spawnError) throw spawnError
 assert.deepEqual(await config(page), {version:'0.0.1', supported:true, enabled:true, installerRestarts:true})
 await page.getByRole('button',{name:'新建分析',exact:true}).first().click()
 await page.getByRole('button',{name:'新建 WB 分析',exact:true}).click()
 const newAnalysis = page.getByRole('dialog',{name:'新建 WB 分析',exact:true})
 await newAnalysis.getByLabel('名称',{exact:true}).fill(projectName)
 await newAnalysis.getByRole('button',{name:'创建',exact:true}).click()
 const analysis = page.getByRole('button',{name:`打开分析 ${projectName}`,exact:true})
 await analysis.waitFor()
 await page.getByRole('button',{name:'更新并重启',exact:true}).click()
 await page.getByText('下载或校验未完成。请重新下载更新。',{exact:true}).waitFor()
 assert.equal(old.exitCode,null)
 assert.equal((await config(page)).version,'0.0.1')
 console.log('Tampered update rejected; the old app still responds')

 sendValidPackage = true
 await page.getByRole('dialog',{name:'软件更新',exact:true}).getByRole('button',{name:'重试更新',exact:true}).click()
 await until(() => old.exitCode === 0, 'old Titan to exit for NSIS', 120_000)
 await until(() => !browser.isConnected() || page.isClosed(), 'previous Titan WebView to close')
 const replacementPid = await until(() => Number(powershell(`${appProcesses} | Where-Object MainWindowHandle -ne 0 | Select-Object -First 1 -ExpandProperty Id`)), 'NSIS to relaunch Titan and show its window')
 assert.notEqual(replacementPid,old.pid)
 const installedVersion = powershell(`(Get-Item -LiteralPath '${executableLiteral}').VersionInfo.ProductVersion`)
 assert.equal(installedVersion.split('.').slice(0,3).join('.'),version)
 console.log(`NSIS automatically relaunched Titan ${version} with PID ${replacementPid}`)

 // NSIS may start the new app without inheriting the old debugging environment.
 const debugging = await fetch(`http://127.0.0.1:${webviewPort}/json/list`).then(response=>response.json()).catch(()=>[])
 if (!debugging.some(target => target.type === 'page' && /tauri\.localhost/.test(target.url))) {
  powershell(`$app = Get-Process -Id ${replacementPid}; $null = $app.CloseMainWindow()`)
  await until(() => !powershell(`Get-Process -Id ${replacementPid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id`), 'the verified replacement to close')
  const reopened = launch()
  reopened.on('error', error => {spawnError = error})
 }
 const replacement = await connect()
 if (spawnError) throw spawnError
 upgraded = replacement.browser
 assert.equal((await config(replacement.page)).version,version)
 await replacement.page.getByRole('button',{name:`打开分析 ${projectName}`,exact:true}).click()
 await replacement.page.getByLabel('实验名称',{exact:true}).waitFor()
 assert.equal(await replacement.page.getByLabel('实验名称',{exact:true}).inputValue(),projectName)
 console.log(`Saved analysis reopened in Titan ${version}`)
} finally {
 if (old.exitCode === null) old.kill()
 if (upgraded) await upgraded.close().catch(() => {})
 powershell(`${appProcesses} | Stop-Process -ErrorAction SilentlyContinue`)
 server.closeAllConnections()
 await new Promise(resolve => server.close(resolve))
}
