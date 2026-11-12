import {test,expect,type Page} from '@playwright/test'

const guest={status:'guest',profile:null,message:null,persistent:false,errorCode:null}
const profile={id:'account-a',name:'研究者甲',email:'researcher@example.org',createdAt:'2026-11-01T10:00:00Z',emailVerified:true,administratorApproved:false,sessionId:'device-a'}
async function nativeFixture(page:Page,mode:'authenticated'|'managed'|'guest'|'storage'='authenticated'){
 await page.addInitScript(({guest,profile,mode})=>{
  if(mode==='managed')profile={...profile,emailVerified:false,administratorApproved:true}
  const w=window as any
  let snapshot=(mode==='authenticated'||mode==='managed')?{...guest,status:'authenticated',persistent:true,profile}:{...guest}
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
const account=(page:Page)=>page.getByRole('region',{name:'账户',exact:true})
async function openAccount(page:Page){await page.locator('.account-trigger').click();await expect(account(page)).toBeVisible()}

async function createLibraryAnalysis(page:Page,name:string){
 const response=await page.request.post('/test-engine',{data:{command:'library_create',payload:{name}}})
 const result=await response.json();expect(result.ok,result.error).toBe(true)
}


test('account occupies the center with usable sidebar and global navigation',async({page})=>{
 await page.goto('/?integration=1');await openAccount(page)
 const sidebar=page.getByRole('complementary',{name:'Titan 导航',exact:true})
 const nav=page.getByRole('navigation',{name:'浏览导航',exact:true})
 await expect(page.getByRole('dialog',{name:'账户',exact:true})).toHaveCount(0)
 await expect(page.locator('.account-dialog,.modal-backdrop,[aria-modal=true]')).toHaveCount(0)
 await expect(account(page).locator('xpath=ancestor::main')).toBeVisible()
 await expect(sidebar.locator('.account-trigger')).toHaveAttribute('aria-current','page')
 await expect(nav).toContainText('账户')
 await expect(nav.getByRole('button',{name:'展开右栏',exact:true})).toBeDisabled()
 const bounds=await account(page).boundingBox(),left=await sidebar.boundingBox(),top=await nav.boundingBox()
 expect(bounds!.x).toBeGreaterThanOrEqual(left!.x+left!.width)
 expect(bounds!.y).toBeGreaterThanOrEqual(top!.y+top!.height)
 await page.screenshot({path:'artifacts/accounts/account-center.png',fullPage:true})
 // Sidebar actions must work while the account page is displayed.
 await sidebar.getByRole('button',{name:'免疫荧光',exact:true}).click()
 await expect(account(page)).toBeHidden()
 await expect(page.getByRole('heading',{name:'免疫荧光',exact:true})).toBeVisible()
 await nav.getByRole('button',{name:'后退',exact:true}).click()
 await expect(account(page)).toBeVisible()
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Titan 工作区',exact:true})).toBeVisible()
 await expect(sidebar.locator('.account-trigger')).not.toHaveAttribute('aria-current','page')
})

for(const tool of ['if','stats'] as const)test(`account navigation preserves the live ${tool} draft${tool==='stats'?' and undo state':''}`,async({page})=>{
 await page.goto('/?integration=1')
 await page.getByRole('button',{name:tool==='if'?'免疫荧光':'统计与绘图',exact:true}).click()
 await page.getByRole('button',{name:tool==='if'?'体验 IF 合成示例':'体验合成示例',exact:true}).click()
 const field=tool==='if'?page.getByLabel('当前视野名称',{exact:true}):page.getByLabel('数值 1 1',{exact:true})
 const before=await field.inputValue(),edited=tool==='if'?'未保存的 IF 视野':'42'
 await field.fill(edited)
 // This unfinished IF polygon exists only inside the mounted canvas, never in
 // autosaved project data, so reopening saved data cannot satisfy the check.
 const polygon=page.locator('.if-canvas polygon[stroke-dasharray]')
 let points:string|null=null
 if(tool==='if'){
  await page.getByLabel('区域工具',{exact:true}).selectOption('polygon')
  const canvas=page.getByLabel('IF 原始坐标画布',{exact:true})
  for(const position of [{x:30,y:30},{x:100,y:30},{x:100,y:100}])await canvas.click({position})
  points=await polygon.getAttribute('points');expect(points).toBeTruthy()
 }
 await openAccount(page)
 await expect(field).toBeHidden()
 // A hidden scientific pane cannot be focused or receive account key presses.
 const pane=page.locator(tool==='if'?'.if-pane':'.stats-pane')
 await expect(pane).toHaveAttribute('inert','')
 await account(page).getByRole('heading',{name:'账户',exact:true}).focus()
 await page.keyboard.press('ControlOrMeta+z');await page.keyboard.press('Delete')
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click()
 await expect(field).toHaveValue(edited)
 const nav=page.getByRole('navigation',{name:'浏览导航',exact:true})
 await nav.getByRole('button',{name:'前进',exact:true}).click();await expect(account(page)).toBeVisible()
 await nav.getByRole('button',{name:'后退',exact:true}).click();await expect(field).toHaveValue(edited)
 if(tool==='if'){await expect(polygon).toHaveAttribute('points',points!);await expect(page.getByRole('button',{name:'闭合多边形',exact:true})).toBeEnabled()}
 if(tool==='stats'){
  await page.getByRole('button',{name:'撤销统计修改',exact:true}).click()
  await expect(field).toHaveValue(before)
 }
})

test('leaving account for another module or library analysis still guards an unsaved WB figure',async({page})=>{
 await page.goto('/?integration=1')
 await createLibraryAnalysis(page,'账户导航离开保护');await page.reload()
 await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'新建组图',exact:true}).click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('保留直到批准离开')
 await openAccount(page)
 let prompts=0
 page.on('dialog',dialog=>{prompts++;void dialog.dismiss()})
 await page.getByRole('complementary',{name:'Titan 导航',exact:true}).getByRole('button',{name:'免疫荧光',exact:true}).click()
 await expect(account(page)).toBeVisible();expect(prompts).toBe(1)
 await page.getByRole('button',{name:'打开分析 账户导航离开保护',exact:true}).click()
 await expect(account(page)).toBeVisible();expect(prompts).toBe(2)
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('保留直到批准离开')
})

test('recent account items and sidebar library entries navigate out of account without stale overlays',async({page})=>{
 await page.goto('/?integration=1')
 await createLibraryAnalysis(page,'账户最近分析');await createLibraryAnalysis(page,'账户左栏分析');await page.reload()
 await openAccount(page)
 await account(page).getByRole('button',{name:'继续项目 账户最近分析',exact:true}).click()
 await expect(account(page)).toBeHidden()
 await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue('账户最近分析')
 const nav=page.getByRole('navigation',{name:'浏览导航',exact:true})
 await nav.getByRole('button',{name:'后退',exact:true}).click();await expect(account(page)).toBeVisible()
 await page.getByRole('button',{name:'打开分析 账户左栏分析',exact:true}).click()
 await expect(account(page)).toBeHidden()
 await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue('账户左栏分析')
 await expect(nav.getByRole('button',{name:'前进',exact:true})).toBeDisabled()
 await nav.getByRole('button',{name:'后退',exact:true}).click();await expect(account(page)).toBeVisible()
 await nav.getByRole('button',{name:'前进',exact:true}).click()
 await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue('账户左栏分析')
})

test('account center preserves a WB figure draft through return and browsing history',async({page})=>{
 await page.goto('/?integration=1')
 await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'新建组图',exact:true}).click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('未保存的账户导航草稿')
 await openAccount(page)
 await account(page).getByRole('button',{name:'登录账户',exact:true}).click()
 await expect(account(page).getByText('登录服务尚未开放',{exact:true})).toBeVisible()
 await expect(account(page).getByRole('heading',{name:'研究足迹',exact:true})).toBeVisible()
 await expect(account(page).getByLabel('最近五十二周的每日分析活动')).toBeVisible()
 await page.keyboard.press('ControlOrMeta+z')
 await page.keyboard.press('Delete')
 await page.keyboard.press('Escape')
 await expect(account(page)).toBeVisible()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toBeHidden()
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('未保存的账户导航草稿')
 const nav=page.getByRole('navigation',{name:'浏览导航',exact:true})
 await nav.getByRole('button',{name:'前进',exact:true}).click()
 await expect(account(page)).toBeVisible()
 await nav.getByRole('button',{name:'后退',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('未保存的账户导航草稿')
})

test('mocked native login stays cancellable across account navigation and ignores its late result',async({page})=>{
 await nativeFixture(page,'guest');await page.goto('/?integration=1');await openAccount(page)
 await account(page).getByRole('button',{name:'登录账户',exact:true}).click()
 await expect(account(page).getByText('等待浏览器完成登录',{exact:true})).toBeVisible()
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click();await openAccount(page)
 await account(page).getByRole('button',{name:'取消登录',exact:true}).click()
 await page.evaluate(()=>(window as any).completeAccountLogin())
 await expect(account(page).getByRole('heading',{name:'本地研究者',exact:true})).toBeVisible()
 await expect(page.locator('.account-trigger')).toContainText('未登录')
 expect(await page.evaluate(()=>(window as any).accountCalls.filter((call:any)=>call.command==='auth_cancel').length)).toBe(1)
})

test('mocked native profile, device list and guarded all-device logout remain usable in the center',async({page})=>{
 await nativeFixture(page);await page.goto('/?integration=1')
 await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'新建组图',exact:true}).click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('昵称编辑不得改变组图')
 await openAccount(page)
 await expect(account(page).getByRole('heading',{name:'研究者甲',exact:true})).toBeVisible()
 await expect(account(page).getByText('测试 Mac',{exact:true})).toBeVisible()
 await expect(account(page).getByText('另一台设备',{exact:true})).toBeVisible()
 await account(page).getByLabel('昵称',{exact:true}).fill('编辑中的昵称')
 await page.keyboard.press('ControlOrMeta+z');await page.keyboard.press('Delete')
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
 await account(page).getByRole('button',{name:'返回工作区',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('昵称编辑不得改变组图')
})

test('credential storage failure waits for explicit memory-only login',async({page})=>{
 await nativeFixture(page,'storage');await page.goto('/?integration=1');await openAccount(page)
 await account(page).getByRole('button',{name:'登录账户',exact:true}).click()
 await expect(account(page).getByRole('button',{name:'仅本次登录',exact:true})).toBeVisible()
 expect(await page.evaluate(()=>(window as any).accountCalls.filter((call:any)=>call.command==='auth_login').length)).toBe(1)
 await account(page).getByRole('button',{name:'仅本次登录',exact:true}).click()
 expect(await page.evaluate(()=>(window as any).accountCalls.filter((call:any)=>call.command==='auth_login').at(-1).args)).toEqual({memoryOnly:true,switchAccount:false})
 await account(page).getByRole('button',{name:'取消登录',exact:true}).click()
})

// Illustrative ledgers are seeded only in isolated browser storage. They are not
// inferred from projects and never written into the installed application's data.
test('activity periods show square calendars and selected lifetime totals at desktop and minimum width',async({page})=>{
 await page.clock.setFixedTime(new Date('2027-01-01T12:00:00+08:00'))
 await page.addInitScript(()=>{
  const images:Record<string,string>={old:'2024-01-01'},bands:Record<string,string>={}
  for(let index=0;index<350;index++){
   const date=new Date(2026,0,5+index,12)
   const day=`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`
   if(index%5<3){images[`image-${index}`]=day;for(let band=0;band<index%4+1;band++)bands[`band-${index}-${band}`]=day}
  }
  images.current='2027-01-01';bands.current='2027-01-01'
  localStorage.setItem('titan-research-activity-v1',JSON.stringify({version:1,startedAt:'2024-01-01T00:00:00Z',images,bands}))
 })
 await page.goto('/?integration=1');await openAccount(page)
 const section=account(page).getByRole('region',{name:'分析活动',exact:true})
 const modes=section.getByRole('group',{name:'活动显示方式',exact:true})
 const daily=section.getByRole('list',{name:'最近五十二周的每日分析活动',exact:true})
 await expect(daily.getByRole('listitem',{includeHidden:true})).toHaveCount(364)
 await expect(daily.getByRole('listitem',{includeHidden:true}).last()).toBeHidden()
 // Width/height are actual rendered geometry, not assertions about CSS source.
 for(const width of [1440,1080]){
  await page.setViewportSize({width,height:1000})
  for(const cell of [daily.getByRole('listitem',{includeHidden:true}).first(),daily.getByRole('listitem',{includeHidden:true}).nth(150)]){
   const box=await cell.boundingBox();expect(box).not.toBeNull();expect(Math.abs(box!.width-box!.height)).toBeLessThan(.1);expect(box!.width).toBeGreaterThanOrEqual(10)
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 }
 await page.setViewportSize({width:1440,height:1000})
 await section.screenshot({path:'artifacts/accounts/activity-daily.png',animations:'disabled'})
 await section.getByRole('button',{name:'条带数',exact:true}).click()
 await modes.getByRole('button',{name:'每周',exact:true}).click()
 const weekly=section.getByRole('list',{name:'最近五十二周的每周分析活动',exact:true})
 await expect(weekly.getByRole('listitem')).toHaveCount(52)
 await expect(weekly.getByRole('listitem').last()).toHaveAttribute('title',/2026-12-28.*2027-01-03.*1 条新增条带.*截至 2027-01-01/)
 const box=await weekly.getByRole('listitem').last().boundingBox();expect(box!.width).toBe(box!.height)
 await expect(section).toContainText('每格一周')
 await section.screenshot({path:'artifacts/accounts/activity-weekly.png',animations:'disabled'})
 await modes.getByRole('button',{name:'累计总量',exact:true}).click()
 const expected=await page.evaluate(()=>Object.keys(JSON.parse(localStorage.getItem('titan-research-activity-v1')!).bands).length)
 await expect(section.locator('.account-activity-total')).toHaveText(`${expected}条累计新增条带`)
 await expect(section).toContainText('全部已记录活动，包含最近 52 周之前的记录')
 await section.getByRole('button',{name:'图像数',exact:true}).click()
 await expect(section.locator('.account-activity-total')).toHaveText('212张累计新增图像')
 await expect(section.getByRole('button',{name:'图像数',exact:true})).toBeEnabled()
 await expect(section.getByRole('button',{name:'条带数',exact:true})).toBeEnabled()
 await expect(section.getByRole('button',{name:'图像数',exact:true})).toHaveAttribute('aria-pressed','true')
 await expect(section.getByRole('button',{name:'条带数',exact:true})).toHaveAttribute('aria-pressed','false')
 await section.screenshot({path:'artifacts/accounts/activity-cumulative.png',animations:'disabled'})
 await modes.getByRole('button',{name:'每日',exact:true}).click();await expect(daily).toBeVisible()
 await page.getByRole('complementary',{name:'Titan 导航',exact:true}).getByRole('button',{name:'首页',exact:true}).click()
 await expect(account(page)).toBeHidden()
 await page.getByRole('navigation',{name:'浏览导航',exact:true}).getByRole('button',{name:'后退',exact:true}).click()
 await expect(daily).toBeVisible()
})

test('activity periods distinguish fresh tracking from unavailable storage',async({page})=>{
 await page.goto('/?integration=1');await openAccount(page)
 const section=account(page).getByRole('region',{name:'分析活动',exact:true})
 await expect(section).toContainText('完成首次真实数据分析后')
 await expect(section.locator('.is-untracked')).not.toHaveCount(0)
 await section.getByRole('button',{name:'每周',exact:true}).click()
 await expect(section).toContainText('仅部分日期已记录')
 await section.getByRole('button',{name:'累计总量',exact:true}).click()
 await expect(section.locator('.account-activity-total')).toHaveText('0张累计新增图像')
 await page.evaluate(()=>localStorage.setItem('titan-research-activity-v1','{broken'))
 await page.reload();await openAccount(page)
 await expect(section).toContainText('读取研究足迹后显示活动')
 await section.getByRole('button',{name:'累计总量',exact:true}).click()
 await expect(section.locator('.account-activity-total')).toHaveCount(0)
 await expect(account(page)).toContainText('研究足迹暂不可用')
 expect(await page.evaluate(()=>localStorage.getItem('titan-research-activity-v1'))).toBe('{broken')
})


test('managed native profile stays usable without a false email verification badge',async({page})=>{
 await nativeFixture(page,'managed');await page.goto('/?integration=1');await openAccount(page)
 await expect(account(page).getByRole('heading',{name:'研究者甲',exact:true})).toBeVisible()
 await expect(account(page).getByLabel('邮箱已验证',{exact:true})).toHaveCount(0)
 await expect(account(page).getByText('researcher@example.org',{exact:true})).toBeVisible()
 await account(page).getByLabel('昵称',{exact:true}).fill('管理员开通账户')
 await account(page).getByRole('button',{name:'保存昵称',exact:true}).click()
 await expect(account(page).getByRole('heading',{name:'管理员开通账户',exact:true})).toBeVisible()
 await expect(account(page).getByLabel('邮箱已验证',{exact:true})).toHaveCount(0)
 await expect(account(page).getByText('测试 Mac',{exact:true})).toBeVisible()
 await account(page).getByRole('button',{name:'退出本机',exact:true}).click()
 await expect(account(page).getByRole('button',{name:'登录账户',exact:true})).toBeVisible()
})
