import {test,expect,type Page} from '@playwright/test'
import {mkdtemp,writeFile,rename,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'
import {createHash,randomUUID} from 'node:crypto'

async function rpc(page:Page,command:string,payload:object={}){
 const result=await(await page.request.post('/test-engine',{data:{command,payload}})).json()
 expect(result.ok,result.error).toBe(true);return result.data
}
async function sidebarFixture(page:Page){
 await page.goto('/?integration=1')
 const tag=Date.now()+'-'+randomUUID().slice(0,5)
 const a=await rpc(page,'library_create_collection',{name:'菜单项目 A '+tag})
 const b=await rpc(page,'library_create_collection',{name:'菜单项目 B '+tag})
 const analysis=await rpc(page,'library_create',{name:'菜单 WB '+tag,collection_id:a.id})
 await page.reload();return {a,b,analysis}
}
const menu=(page:Page)=>page.getByRole('menu')

test('sidebar creation menu survives initial library loading',async({page})=>{
 const project=await rpc(page,'library_create_collection',{name:'初始加载菜单 '+randomUUID()})
 let release!:()=>void,received!:()=>void
 const held=new Promise<void>(resolve=>release=resolve),waiting=new Promise<void>(resolve=>received=resolve)
 await page.route('**/test-engine',async route=>{
  if(route.request().postDataJSON().command==='library_workspace'){
   const response=await route.fetch();received();await held;await route.fulfill({response})
  }else await route.continue()
 })
 try{
  await page.goto('/?integration=1');await waiting
  await page.getByRole('button',{name:'新建或打开',exact:true}).click();await expect(menu(page)).toBeVisible()
  release();await expect(page.getByRole('button',{name:'打开项目 '+project.name,exact:true})).toBeVisible()
  await expect(menu(page).getByRole('menuitem',{name:'新建项目',exact:true})).toBeVisible()
  await menu(page).getByRole('menuitem',{name:'新建项目',exact:true}).click()
  await expect(page.getByRole('dialog',{name:'新建项目',exact:true})).toBeVisible()
 }finally{release()}
})

test('sidebar project and analysis menus share actions without navigating on right click',async({page})=>{
 const {a,b,analysis}=await sidebarFixture(page)
 const library=page.getByRole('navigation',{name:'实验项目库'})
 const project=library.getByRole('button',{name:'打开项目 '+a.name,exact:true})
 await project.click({button:'right'})
 await expect(menu(page)).toBeVisible()
 await expect(menu(page).getByRole('menuitem',{name:'打开项目',exact:true})).toBeFocused()
 const items=await menu(page).getByRole('menuitem').allTextContents()
 expect(items).toEqual(['打开项目','新建分析','重命名','置顶','移出项目列表'])
 await expect(page.getByRole('heading',{name:'Titan 工作区',exact:true})).toBeVisible()
 await page.keyboard.press('Escape')
 await expect(menu(page)).toBeHidden()
 await library.getByRole('button',{name:'项目菜单 '+a.name,exact:true}).click()
 expect(await menu(page).getByRole('menuitem').allTextContents()).toEqual(items)
 await library.getByRole('button',{name:'打开项目 '+b.name,exact:true}).click({button:'right'})
 await menu(page).getByRole('menuitem',{name:'重命名',exact:true}).click()
 await expect(page.getByRole('dialog').getByLabel('名称',{exact:true})).toHaveValue(b.name)
 await page.getByRole('dialog').getByRole('button',{name:'取消',exact:true}).click()
 await project.click({button:'right'});await menu(page).getByRole('menuitem',{name:'置顶',exact:true}).click()
 await expect.poll(async()=>(await rpc(page,'library_workspace')).projects.find((p:any)=>p.id===a.id).pinned).toBe(true)
 await expect(project.locator('svg.lucide-pin')).toBeVisible()
 await project.click({button:'right'});await menu(page).getByRole('menuitem',{name:'移出项目列表',exact:true}).click()
 await page.getByRole('dialog').getByRole('button',{name:'取消',exact:true}).click()
 expect((await rpc(page,'library_workspace')).projects.some((p:any)=>p.id===a.id)).toBe(true)
 await library.getByRole('button',{name:'展开项目 '+a.name,exact:true}).click()
 const target=library.getByRole('button',{name:'打开分析 '+analysis.project.name,exact:true})
 await target.click({button:'right'})
 await expect(menu(page)).toBeVisible()
 await expect(page.getByRole('heading',{name:'Titan 工作区',exact:true})).toBeVisible()
 expect(await menu(page).getByRole('menuitem').allTextContents()).toEqual(['打开分析','移到项目','移出项目','在文件管理器中显示'])
 await menu(page).getByRole('menuitem',{name:'移到项目',exact:true}).click()
 await page.getByRole('dialog').getByRole('button',{name:'取消',exact:true}).click()
 expect((await rpc(page,'library_workspace')).entries.find((e:any)=>e.entry_id===analysis.entry.entry_id).collection_id).toBe(a.id)
 await target.click({button:'right'});await menu(page).getByRole('menuitem',{name:'打开分析',exact:true}).click()
 await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue(analysis.project.name)
})

test('sidebar ellipsis and plus close on the second pointer click',async({page})=>{
 const {a}=await sidebarFixture(page)
 for(const button of [page.getByRole('button',{name:'新建或打开',exact:true}),page.getByRole('button',{name:'项目菜单 '+a.name,exact:true})]){
  await button.click();await expect(menu(page)).toBeVisible();await expect(button).toHaveAttribute('aria-expanded','true')
  await button.click();await expect(menu(page)).toBeHidden();await expect(button).toHaveAttribute('aria-expanded','false')
 }
})

test('sidebar scrolling and resizing restore the original keyboard focus',async({page})=>{
 const {a}=await sidebarFixture(page),origin=page.getByRole('button',{name:'打开项目 '+a.name,exact:true})
 await page.evaluate(()=>{document.body.style.paddingBottom='1500px'})
 await origin.click({button:'right'});await expect(menu(page)).toBeVisible()
 await page.evaluate(()=>window.scrollTo(0,200));await expect(menu(page)).toBeHidden();await expect(origin).toBeFocused()
 await origin.click({button:'right'});await expect(menu(page)).toBeVisible()
 await page.setViewportSize({width:1100,height:850});await expect(menu(page)).toBeHidden();await expect(origin).toBeFocused()
})

test('sidebar menu supports keyboard dismissal viewport edges and live appearance',async({page})=>{
 const {a}=await sidebarFixture(page)
 const project=page.getByRole('button',{name:'打开项目 '+a.name,exact:true})
 await project.focus();await page.keyboard.press('Shift+F10')
 await expect(menu(page)).toBeVisible();await page.keyboard.press('ArrowDown');await page.keyboard.press('Escape')
 await expect(menu(page)).toBeHidden()
 await expect(project).toBeFocused()
 for(const [x,y] of [[1,1],[1439,1],[1,999],[1439,999]]){
  await project.evaluate((el,point)=>el.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,button:2,clientX:point.x,clientY:point.y})),{x,y})
  await expect(menu(page)).toBeVisible()
  await expect.poll(async()=>{
   const box=await menu(page).boundingBox()
   return !!box&&box.x>=8&&box.y>=8&&box.x+box.width<=1432&&box.y+box.height<=992
  }).toBe(true)
  await expect(menu(page)).toHaveCSS('font-size','13px')
  await page.keyboard.press('Escape')
  await expect(menu(page)).toBeHidden()
 }
 await project.click({button:'right'});await page.emulateMedia({colorScheme:'dark'})
 await expect(menu(page)).toHaveCSS('background-color','rgb(32, 34, 36)')
 await page.emulateMedia({colorScheme:'light'});await expect(menu(page)).toHaveCSS('background-color','rgb(255, 255, 255)')
 await page.getByRole('heading',{name:'Titan 工作区',exact:true}).click();await expect(menu(page)).toBeHidden()
 await project.click({button:'right'});await page.setViewportSize({width:1100,height:800});await expect(menu(page)).toBeHidden()
 await project.click({button:'right'});await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await expect(menu(page)).toBeHidden();await expect(page.getByRole('heading',{name:'Western blot',exact:true})).toBeVisible()
})

test('sidebar legacy figures frozen stats plots and exports have the same context entry points',async({page})=>{
 await page.setViewportSize({width:1440,height:650})
 const {analysis}=await sidebarFixture(page)
 let wb=await rpc(page,'demo')
 Object.assign(wb,{id:analysis.project.id,name:analysis.project.name,project_path:analysis.project.project_path,saved_revision:0})
 wb=await rpc(page,'save_project',{project:wb,path:wb.project_path,expected_revision:0})
 const result=await rpc(page,'analyze',{project:wb})
 await rpc(page,'save_figure',{project:wb,result,figure_settings:{},name:'菜单 WB 图 '+wb.id})
 let stats=await rpc(page,'stats_demo');stats.name='菜单统计 '+stats.id
 const d=stats.datasets[0];d.analysis.method='descriptive'
 stats.figures.push({id:randomUUID(),name:'菜单冻结图 '+stats.id,source_revision:stats.revision,dataset:{...d,runs:[]},run:null,style:d.style})
 stats.revision++;stats=await rpc(page,'stats_save',{project:stats})
 const folder=await mkdtemp(join(tmpdir(),'titan-context-export-')),file=join(folder,'results.svg'),content='<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>'
 try{
  await writeFile(file,content)
  await rpc(page,'library_record_export',{project_path:wb.project_path,project_id:wb.id,record:{kind:'result_export',title:'菜单导出 '+wb.id,destination:file,files:[file],source_revision:wb.revision,primary_sha256:createHash('sha256').update(content).digest('hex')}})
  await page.reload()
  await page.getByRole('button',{name:'展开项目 '+(await rpc(page,'library_workspace')).projects.find((p:any)=>p.id===analysis.entry.collection_id).name,exact:true}).click()
  for(const [label,trigger] of [['打开图表 菜单 WB 图 '+wb.id,'图表菜单 菜单 WB 图 '+wb.id],['打开组图 菜单冻结图 '+stats.id,'产物菜单 菜单冻结图 '+stats.id],['打开导出 菜单导出 '+wb.id,'产物菜单 菜单导出 '+wb.id]]){
   await page.getByRole('button',{name:label,exact:true}).click({button:'right'})
   await expect(menu(page).getByRole('menuitem',{name:'打开源分析',exact:true})).toBeVisible()
   const labels=await menu(page).getByRole('menuitem').allTextContents()
   expect(labels).toContain('打开源分析')
   await page.keyboard.press('Escape');await page.getByRole('button',{name:trigger,exact:true}).click()
   await expect(menu(page).getByRole('menuitem',{name:'打开源分析',exact:true})).toBeVisible()
   expect(await menu(page).getByRole('menuitem').allTextContents()).toEqual(labels)
   await page.keyboard.press('Escape')
  }
  await page.getByRole('button',{name:'打开组图 菜单冻结图 '+stats.id,exact:true}).click({button:'right'})
  await menu(page).getByRole('menuitem',{name:'打开图表',exact:true}).click()
  await expect(page.getByText(/正在查看冻结图形/)).toBeVisible()
  const snapshot=await rpc(page,'stats_open',{path:stats.project_path})
  expect(snapshot.figures[0].dataset.rows).toEqual(stats.figures[0].dataset.rows)
  await page.getByRole('button',{name:'打开导出 菜单导出 '+wb.id,exact:true}).click({button:'right'})
  await menu(page).getByRole('menuitem',{name:'打开源分析',exact:true}).click()
  await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue(wb.name)
  await rename(file,file+'.moved');await page.reload()
  await page.getByRole('button',{name:'展开项目 '+(await rpc(page,'library_workspace')).projects.find((p:any)=>p.id===analysis.entry.collection_id).name,exact:true}).click()
  await page.getByRole('button',{name:'产物菜单 菜单导出 '+wb.id,exact:true}).click()
  await expect(menu(page).getByRole('menuitem',{name:'打开导出',exact:true})).toBeDisabled()
  await expect(menu(page).getByRole('menuitem',{name:'在文件管理器中显示',exact:true})).toBeDisabled()
  await expect(menu(page).getByRole('menuitem',{name:'打开源分析',exact:true})).toBeEnabled()
 }finally{await rm(folder,{recursive:true,force:true})}
})

async function statsFixture(page:Page){
 await page.goto('/?integration=1')
 let p=await rpc(page,'stats_demo');p.name='单元格菜单 '+p.id
 const d=p.datasets[0];d.name='菜单原表';d.analysis.method='descriptive'
 const run=await rpc(page,'stats_analyze',{dataset:d});d.runs.push(run)
 p.datasets.push({...structuredClone(d),id:randomUUID(),name:'菜单另一表',runs:[]})
 p.figures.push({id:randomUUID(),name:'菜单只读快照 '+p.id,source_revision:p.revision,dataset:{...d,runs:[]},run,style:d.style})
 p.revision++;p=await rpc(page,'stats_save',{project:p})
 await page.reload();await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click()
 await expect(page.getByLabel('统计项目名称')).toHaveValue(p.name)
 return p
}

test('statistics cell exclusion requires a menu choice and preserves raw values and undo',async({page})=>{
 const p=await statsFixture(page),cell=page.getByLabel('数值 1 1',{exact:true}),td=cell.locator('..')
 const original=await cell.inputValue()
 await cell.click({button:'right'})
 await expect(td).not.toHaveClass(/excluded/)
 await expect(menu(page).getByRole('menuitem',{name:'排除此值',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'撤销统计修改',exact:true})).toBeDisabled()
 await page.keyboard.press('Escape');await expect(td).not.toHaveClass(/excluded/)
 await cell.click({button:'right'});await menu(page).getByRole('menuitem',{name:'排除此值',exact:true}).click()
 await expect(td).toHaveClass(/excluded/);await expect(cell).toHaveValue(original)
 await page.getByRole('navigation',{name:'统计工作区'}).getByRole('button',{name:'统计分析',exact:true}).click()
 await expect(page.getByText('数据或设置已改变，请重新运行分析。',{exact:true})).toBeVisible()
 await page.getByRole('navigation',{name:'统计工作区'}).getByRole('button',{name:'数据表',exact:true}).click()
 await page.getByRole('button',{name:'撤销统计修改',exact:true}).click();await expect(td).not.toHaveClass(/excluded/)
 await cell.click({button:'right'});await menu(page).getByRole('menuitem',{name:'排除此值',exact:true}).click()
 await cell.click({button:'right'});await menu(page).getByRole('menuitem',{name:'恢复此值',exact:true}).click()
 await expect(td).not.toHaveClass(/excluded/);await expect(cell).toHaveValue(original)
 await page.getByRole('button',{name:'保存',exact:true}).click()
 const saved=await rpc(page,'stats_open',{path:p.project_path})
 expect(saved.datasets[0].rows[0].values[p.datasets[0].groups[0].id]).toBe(original)
 expect(saved.datasets[0].runs[0].summaries[0].n).toBe(3)
})

test('statistics cell menu respects frozen snapshots and locked WB sources',async({page})=>{
 const p=await statsFixture(page)
 await page.getByLabel('选择数据表或图形').selectOption('figure:'+p.figures[0].id)
 await page.getByRole('navigation',{name:'统计工作区'}).getByRole('button',{name:'数据表',exact:true}).click()
 await page.locator('.stats-grid tbody td').first().click({button:'right'})
 await expect(menu(page).getByRole('menuitem',{name:'排除此值',exact:true})).toBeDisabled()
 await expect(menu(page)).toContainText('历史快照只读')
 await page.keyboard.press('Escape')
 const created=await rpc(page,'library_create',{name:'单元格锁定来源 '+randomUUID()})
 let wb=await rpc(page,'demo')
 Object.assign(wb,{id:created.project.id,name:created.project.name,project_path:created.project.project_path,saved_revision:0})
 wb=await rpc(page,'save_project',{project:wb,path:wb.project_path,expected_revision:0})
 const locked=await rpc(page,'stats_from_wb',{project:wb})
 await page.reload();await page.getByRole('button',{name:'打开分析 '+locked.name,exact:true}).click()
 await expect(page.getByLabel('数值 1 1',{exact:true})).toBeDisabled()
 await page.locator('.stats-grid tbody td').first().click({button:'right'})
 await expect(menu(page)).toContainText('来源数据已锁定')
 await expect(menu(page).getByRole('menuitem',{name:'排除此值',exact:true})).toBeDisabled()
 await page.keyboard.press('Escape')
 const after=await rpc(page,'stats_open',{path:locked.project_path})
 expect(after.datasets[0].rows).toEqual(locked.datasets[0].rows)
 expect((await rpc(page,'stats_open',{path:p.project_path})).figures[0].dataset.rows).toEqual(p.figures[0].dataset.rows)
})

test('statistics cell menu invalidates on table changes and row removal without changing another value',async({page})=>{
 const p=await statsFixture(page),picker=page.getByLabel('选择数据表或图形')
 await page.getByLabel('数值 1 1',{exact:true}).click({button:'right'})
 await picker.selectOption('table:'+p.datasets[1].id)
 await expect(menu(page)).toBeHidden()
 await expect(page.locator('.stats-grid td.excluded')).toHaveCount(0)
 await picker.selectOption('table:'+p.datasets[0].id)
 await page.getByLabel('数值 2 1',{exact:true}).click({button:'right'})
 await page.getByRole('button',{name:'删除行 1',exact:true}).evaluate((button:HTMLButtonElement)=>button.click())
 await expect(menu(page)).toBeHidden();await expect(page.locator('.stats-grid td.excluded')).toHaveCount(0)
 await expect(page.getByLabel('数值 1 1',{exact:true})).toHaveValue(p.datasets[0].rows[1].values[p.datasets[0].groups[0].id])
 await page.getByLabel('数值 1 1',{exact:true}).focus();await page.keyboard.press('Shift+F10')
 await expect(menu(page)).toBeVisible()
 await page.getByRole('button',{name:'导入 / 粘贴',exact:true}).evaluate((button:HTMLButtonElement)=>button.click())
 await expect(page.getByRole('dialog')).toBeVisible();await expect(menu(page)).toBeHidden()
})
