import {test,expect,type Page} from '@playwright/test'

const guest={status:'guest',profile:null,message:null,persistent:false,errorCode:null}
const profile={id:'account-a',name:'研究者甲',email:'researcher@example.org',createdAt:'2026-11-01T10:00:00Z',emailVerified:true,sessionId:'device-a'}
async function nativeFixture(page:Page,mode:'authenticated'|'guest'|'storage'='authenticated'){
 await page.addInitScript(({guest,profile,mode})=>{
  const w=window as any
  let snapshot=mode==='authenticated'?{...guest,status:'authenticated',persistent:true,profile}:{...guest}
  let finish:((value:unknown)=>void)|null=null
  w.accountCalls=[]
  w.completeAccountLogin=()=>{finish?.({...guest,status:'authenticated',persistent:true,profile})}
  w.__TAURI_EVENT_PLUGIN_INTERNALS__={unregisterListener:()=>{}}
  w.__TAURI_INTERNALS__={metadata:{currentWindow:{label:'main'}},transformCallback:()=>1,unregisterCallback:()=>{},invoke:async(command:string,args:any)=>{
   if(command.startsWith('plugin:event|'))return 1
   w.accountCalls.push({command,args})
   if(command==='auth_status')return snapshot
   if(command==='auth_login'){
    if(mode==='storage'&&!args.memoryOnly)return {...guest,status:'unavailable',errorCode:'credential_storage_failed',message:'系统凭据存储不可用，请重试或选择仅本次登录。'}
    return new Promise(resolve=>{finish=resolve})
   }
   if(command==='auth_cancel'||command==='auth_logout'){snapshot={...guest};return snapshot}
   if(command==='auth_update_profile'){snapshot={...snapshot,profile:{...profile,name:args.name}};return snapshot}
   if(command==='auth_sessions')return [{id:'device-a',label:'测试 Mac',platform:'macos',createdAt:'2026-11-01',lastSeenAt:'2026-11-12',expiresAt:'2026-12-01',current:true},{id:'device-b',label:'另一台设备',platform:'windows',createdAt:'2026-11-01',lastSeenAt:'2026-11-10',expiresAt:'2026-12-01',current:false}]
   if(command==='auth_revoke_all')return {...snapshot,errorCode:'recent_auth_required',message:'请重新登录后再退出所有设备。'}
   throw 'service_unavailable'
  }}
 },{guest,profile,mode})
}
const account=(page:Page)=>page.getByRole('dialog',{name:'账户',exact:true})
async function openAccount(page:Page){await page.locator('.account-trigger').click();await expect(account(page)).toBeVisible()}

test('unconfigured account preserves WB figure draft and isolates keyboard shortcuts',async({page})=>{
 await page.goto('/?integration=1')
 await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'新建组图',exact:true}).click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('未保存的账户导航草稿')
 await openAccount(page)
 await account(page).getByRole('button',{name:'登录 / 注册',exact:true}).click()
 await expect(account(page).getByText('登录服务尚未开放',{exact:true})).toBeVisible()
 await expect(account(page).getByRole('heading',{name:'研究足迹',exact:true})).toBeVisible()
 await expect(account(page).getByLabel('最近二十周的分析活动')).toBeVisible()
 await page.keyboard.press('ControlOrMeta+z')
 await page.keyboard.press('Delete')
 await page.keyboard.press('Escape')
 await expect(account(page)).toBeHidden()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('未保存的账户导航草稿')
 await openAccount(page);await account(page).getByRole('button',{name:'返回工作区',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('未保存的账户导航草稿')
})

test('browser login stays cancellable across dialog reopen and ignores its late result',async({page})=>{
 await nativeFixture(page,'guest');await page.goto('/?integration=1');await openAccount(page)
 await account(page).getByRole('button',{name:'登录 / 注册',exact:true}).click()
 await expect(account(page).getByText('等待浏览器完成登录',{exact:true})).toBeVisible()
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click();await openAccount(page)
 await account(page).getByRole('button',{name:'取消登录',exact:true}).click()
 await page.evaluate(()=>(window as any).completeAccountLogin())
 await expect(account(page).getByRole('heading',{name:'本地研究者',exact:true})).toBeVisible()
 await expect(page.locator('.account-trigger')).toContainText('未登录')
 expect(await page.evaluate(()=>(window as any).accountCalls.filter((call:any)=>call.command==='auth_cancel').length)).toBe(1)
})

test('verified profile, device list and guarded all-device logout use native account commands',async({page})=>{
 await nativeFixture(page);await page.goto('/?integration=1');await openAccount(page)
 await expect(account(page).getByRole('heading',{name:'研究者甲',exact:true})).toBeVisible()
 await expect(account(page).getByText('测试 Mac',{exact:true})).toBeVisible()
 await expect(account(page).getByText('另一台设备',{exact:true})).toBeVisible()
 await account(page).getByLabel('昵称',{exact:true}).fill('确认后的昵称')
 await account(page).getByRole('button',{name:'保存昵称',exact:true}).click()
 await expect(account(page).getByRole('heading',{name:'确认后的昵称',exact:true})).toBeVisible()
 await expect(page.locator('.account-trigger')).toContainText('确认后的昵称')
 await account(page).getByRole('button',{name:'退出所有设备',exact:true}).click()
 const confirmation=account(page).getByRole('alertdialog')
 await expect(confirmation).toBeVisible();await page.keyboard.press('Escape');await expect(confirmation).toBeHidden();await expect(account(page)).toBeVisible()
 expect(await page.evaluate(()=>(window as any).accountCalls.some((call:any)=>call.command==='auth_revoke_all'))).toBe(false)
 await account(page).getByRole('button',{name:'退出所有设备',exact:true}).click();await confirmation.getByRole('button',{name:'确认退出所有设备',exact:true}).click()
 await account(page).getByRole('button',{name:'在浏览器中重新验证',exact:true}).click()
 expect(await page.evaluate(()=>(window as any).accountCalls.find((call:any)=>call.command==='auth_login').args)).toEqual({memoryOnly:false,switchAccount:true})
 await page.evaluate(()=>(window as any).completeAccountLogin())
 await page.screenshot({path:'artifacts/accounts/confirmed-account.png',fullPage:true})
 await account(page).getByRole('button',{name:'退出本机',exact:true}).click()
 await expect(account(page).getByText(/服务端撤销未确认/)).toBeVisible()
 await expect(account(page).getByRole('heading',{name:'本地研究者',exact:true})).toBeVisible()
})

test('credential storage failure waits for explicit memory-only login',async({page})=>{
 await nativeFixture(page,'storage');await page.goto('/?integration=1');await openAccount(page)
 await account(page).getByRole('button',{name:'登录 / 注册',exact:true}).click()
 await expect(account(page).getByRole('button',{name:'仅本次登录',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>(window as any).accountCalls.filter((call:any)=>call.command==='auth_login').length)).toBe(1)
 await account(page).getByRole('button',{name:'仅本次登录',exact:true}).click()
 expect(await page.evaluate(()=>(window as any).accountCalls.filter((call:any)=>call.command==='auth_login').at(-1).args)).toEqual({memoryOnly:true,switchAccount:false})
 await account(page).getByRole('button',{name:'取消登录',exact:true}).click()
})
