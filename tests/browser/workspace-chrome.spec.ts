import {createAnalysis} from './library-actions'
import {test,expect} from '@playwright/test'

async function rpc(page:any,command:string,payload:object={}){
 const envelope=await (await page.request.post('/test-engine',{data:{command,payload}})).json()
 expect(envelope.ok,envelope.error).toBe(true);return envelope.data
}
async function openExperiment(page:any){
 await page.goto('/?integration=1')
 const created=await rpc(page,'library_create',{name:'清爽工作区验收 '+Date.now()});let p=await rpc(page,'demo')
 p.id=created.project.id;p.name=created.project.name;p.project_path=created.project.project_path;p.saved_revision=0
 delete p.demo;p.synthetic=true;p.rois=[];p.lanes=[];p.samples=[];p.lane_layouts=[];p.band_sets=[]
 p=await rpc(page,'save_project',{project:p,path:p.project_path,expected_revision:0})
 await rpc(page,'library_register',{path:p.project_path});await page.reload()
 await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click();return p
}

test('Western blot opens home and resumes the current figure draft',async({page})=>{
 await openExperiment(page)
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'新建组图',exact:true}).click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('未保存的 AKT')

 await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Western blot',exact:true})).toBeVisible({timeout:2000})
 await expect(page.getByLabel('蛋白名称',{exact:true})).toBeHidden()
 await page.getByRole('button',{name:'图像操作指引',exact:true}).click()
 const guide=page.getByRole('dialog',{name:'WB 图像操作指引'})
 await guide.getByRole('button',{name:'调整泳道',exact:true}).click()
 await expect(guide.getByRole('heading',{name:'调整泳道',exact:true})).toBeVisible()
 await page.keyboard.press('Escape')
 await expect(guide).toBeHidden()

 await page.getByRole('button',{name:'继续当前实验',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('未保存的 AKT')
})

test('module navigation resumes WB and opens saved projects from either module',async({page})=>{
 const wb=await openExperiment(page)
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'免疫荧光',exact:true}).click()
 await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click()
 const ifName='跨模块 IF 验收 '+Date.now()
 await page.getByLabel('IF 实验名称').fill(ifName)
 await page.getByRole('button',{name:'保存 IF 实验',exact:true}).click()
 await expect(page.getByRole('status').filter({hasText:'实验已保存'})).toBeVisible()
 await page.getByRole('button',{name:'3D 查看（原型）',exact:true}).click()
 const volume=page.getByRole('dialog',{name:'免疫荧光 3D 查看'})
 await expect(volume).toBeVisible()
 await volume.getByRole('button',{name:'关闭 3D 查看'}).click()

 await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Western blot',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'继续当前实验',exact:true}).click()
 await expect(page.getByRole('button',{name:'新建组图',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'打开分析 '+ifName,exact:true}).click()
 await expect(page.getByLabel('IF 实验名称')).toHaveValue(ifName)
 await page.locator('.if-shell').getByRole('button',{name:'打开分析 '+wb.name,exact:true}).click()
 await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue(wb.name)
})

test('compact title and plain navigation retain accessible experiment operations',async({page})=>{
 await openExperiment(page)
 const nav=page.getByRole('navigation',{name:'实验视图',exact:true})
 await expect(nav).toBeVisible()
 await expect(page.locator('.app-header').getByLabel('实验名称')).toBeVisible()
 await expect(page.locator('.project-heading')).toHaveCount(0)
 expect(await nav.innerText()).not.toMatch(/0[1-4]/)
 expect((await nav.boundingBox())!.y+(await nav.boundingBox())!.height).toBeLessThan(155)
 await expect(page.getByRole('button',{name:'保存实验',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'另存副本',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'导入图像',exact:true})).toBeVisible()
 await expect(page.getByRole('contentinfo').getByText('本地引擎就绪',{exact:true})).toBeVisible()
 await page.getByLabel('实验名称').fill('较长的实验名称，用来检查标题能收缩而不把右侧保存与导入操作挤出窗口')
 await page.getByLabel('显示字号').selectOption('large')
 await page.setViewportSize({width:1080,height:850})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await expect(page.getByRole('button',{name:'导出结果',exact:true})).toHaveCount(0)
 await expect(page.locator('.library-children>button.selected')).toHaveText('条带组图')
 await page.screenshot({path:'artifacts/neutral-workspace/wb-empty-1080-large.png',fullPage:true,animations:'disabled'})
})

test('WB empty state has one centered creation action and saved documents remain discoverable',async({page})=>{
 await openExperiment(page)
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 const create=page.getByRole('button',{name:'新建组图',exact:true})
 await expect(create).toHaveCount(1)
 const centers=await page.locator('.wb-empty').evaluate(el=>{
  const nodes=[el.querySelector('h3')!,el.querySelector('p')!,el.querySelector('button')!]
  return nodes.map(node=>{const range=document.createRange();range.selectNodeContents(node);const r=range.getBoundingClientRect();return r.x+r.width/2})
 })
 expect(Math.max(...centers)-Math.min(...centers)).toBeLessThan(3)
 expect(await page.locator('.wb-empty').evaluate(el=>getComputedStyle(el).borderStyle)).not.toContain('dashed')
 await page.screenshot({path:'artifacts/neutral-workspace/wb-empty-1440.png',fullPage:true,animations:'disabled'})
 await create.click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('AKT')
 await page.getByLabel('预期分子量 kDa',{exact:true}).fill('60')
 await page.getByLabel('裁剪 X0',{exact:true}).fill('20');await page.getByLabel('裁剪 X1',{exact:true}).fill('500')
 await page.getByLabel('裁剪 Y0',{exact:true}).fill('20');await page.getByLabel('裁剪 Y1',{exact:true}).fill('80')
 await page.getByRole('button',{name:'确认本行裁剪',exact:true}).click()
 await page.getByRole('button',{name:'保存组图',exact:true}).click()
 await expect(page.getByRole('status').filter({hasText:'组图已保存'})).toBeVisible()
 await expect(page.getByLabel('已保存的组图',{exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'导出组图',exact:true})).toBeEnabled()
 await page.screenshot({path:'artifacts/neutral-workspace/wb-editor-1440.png',fullPage:true})
 await page.getByLabel('蛋白名称',{exact:true}).fill('待保存修改')
 page.once('dialog',dialog=>dialog.dismiss())
 await page.getByRole('button',{name:'内参',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('待保存修改')
 page.once('dialog',dialog=>dialog.accept())
 await page.getByRole('button',{name:'首页',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Titan 工作区',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await page.getByRole('button',{name:'继续当前实验',exact:true}).click()
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('AKT')
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await expect(page.getByRole('img',{name:'WB 组图预览',exact:true})).toBeVisible()
 await page.screenshot({path:'artifacts/neutral-workspace/wb-editor-390.png',fullPage:true})
})

test('analysis and results remain available in the neutral shell',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await expect(page.getByRole('button',{name:'开始定量',exact:true})).toBeVisible()
 await page.screenshot({path:'artifacts/neutral-workspace/analysis-1440.png',fullPage:true})
 await page.getByRole('button',{name:'开始定量',exact:true}).click()
 await expect(page.getByRole('button',{name:'导出结果',exact:true})).toBeEnabled()
 await page.getByRole('button',{name:'样本与分析设置',exact:true}).click()
 await expect(page.getByLabel('group L1',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'定量结果',exact:true}).click()
 await page.screenshot({path:'artifacts/neutral-workspace/results-1440.png',fullPage:true})
})

test('an empty WB experiment offers import and readonly users can inspect saved assemblies',async({page})=>{
 await page.goto('/?integration=1');await createAnalysis(page,'wb')
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await expect(page.getByRole('button',{name:'导入图像',exact:true})).toBeEnabled()
 await expect(page.getByRole('button',{name:'新建组图',exact:true})).toHaveCount(0)
 const p=await openExperiment(page),d=await rpc(page,'wb_new',{project:p});d.rows[0].confirmed=true
 const saved=await rpc(page,'wb_save',{project:p,document:d})
 await page.reload()
 await page.route('**/test-engine',async route=>{
  if(route.request().postDataJSON().command!=='open_project'){await route.continue();return}
  const response=await route.fetch(),body=await response.json();body.data.read_only=true
  await route.fulfill({response,json:body})
 })
 await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click()
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await expect(page.getByRole('button',{name:'新建组图',exact:true})).toHaveCount(1)
 await expect(page.getByRole('button',{name:'新建组图',exact:true})).toBeDisabled()
 await page.getByLabel('已保存的组图',{exact:true}).selectOption(saved.id)
 await expect(page.getByRole('button',{name:'保存组图',exact:true})).toBeDisabled()
 await expect(page.getByRole('button',{name:'导出组图',exact:true})).toBeEnabled()
})

test('an unfinished WB draft can import another source without losing labels or crops',async({page})=>{
 const p=await openExperiment(page)
 await page.getByRole('button',{name:'WB 组图',exact:true}).click()
 await page.getByRole('button',{name:'新建组图',exact:true}).click()
 await page.getByLabel('蛋白名称',{exact:true}).fill('未完成的 AKT')
 await page.getByLabel('裁剪 X0',{exact:true}).fill('20')
 await expect(page.getByRole('button',{name:'导出组图',exact:true})).toBeDisabled()
 await expect(page.getByRole('button',{name:'导入图像',exact:true})).toBeVisible()
 await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async(command:string)=>{
  if(command==='plugin:dialog|open')return [source]
  throw new Error(command)
 }}},p.images[0].path)
 await page.getByRole('button',{name:'导入图像',exact:true}).click()
 await expect(page.getByLabel('添加行的原图').locator('option')).toHaveCount(2)
 await expect(page.getByLabel('蛋白名称',{exact:true})).toHaveValue('未完成的 AKT')
 await expect(page.getByLabel('裁剪 X0',{exact:true})).toHaveValue('20')
 await expect(page.getByRole('button',{name:'导出组图',exact:true})).toBeDisabled()
 await page.getByLabel('添加行的原图').selectOption({index:1})
 await page.getByRole('button',{name:'添加蛋白行',exact:true}).click()
 await expect(page.locator('.wb-row-list>button')).toHaveCount(2)
})
