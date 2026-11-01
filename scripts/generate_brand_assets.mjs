// Export the approved fist artwork without retracing or changing its silhouette.
import {readFile,writeFile,copyFile,mkdtemp,rm} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {execFile} from 'node:child_process'
import {promisify} from 'node:util'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {chromium} from 'playwright'

const root=new URL('../',import.meta.url)
const master=await readFile(new URL('assets/brand/titan-fist-master.png',root))
const source=`data:image/png;base64,${master.toString('base64')}`
const icon=`<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 512 512" role="img" aria-label="Titan 应用图标"><defs><clipPath id="tile"><rect x="16" y="16" width="480" height="480" rx="108"/></clipPath></defs><g clip-path="url(#tile)"><image width="512" height="512" href="${source}"/></g></svg>\n`
await writeFile(new URL('assets/icon.svg',root),icon)
const browser=await chromium.launch({headless:true})
try{
 const page=await browser.newPage({viewport:{width:1024,height:1024},deviceScaleFactor:1})
 await page.goto(new URL('assets/icon.svg',root).href)
 await page.screenshot({path:fileURLToPath(new URL('assets/icon.png',root)),omitBackground:true})
}finally{await browser.close()}
const output=await mkdtemp(join(tmpdir(),'titan-brand-icons-'))
try{
 await promisify(execFile)('npm',['exec','--','tauri','icon','assets/icon.png','--output',output],{cwd:fileURLToPath(root)})
 for(const name of ['icon.png','icon.icns','icon.ico','32x32.png','64x64.png','128x128.png','128x128@2x.png']){
  await copyFile(join(output,name),new URL(`src-tauri/icons/${name}`,root))
 }
 await copyFile(join(output,'128x128.png'),new URL('assets/brand/titan-app-icon-128.png',root))
 await copyFile(join(output,'32x32.png'),new URL('assets/brand/titan-favicon-32.png',root))
}finally{await rm(output,{recursive:true,force:true})}
console.log('Exported the approved fist as app/web assets, macOS ICNS, Windows ICO and desktop PNG sizes.')
