import {test,expect,type Page} from '@playwright/test'
import {mkdtempSync,readFileSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'

async function rpc(page:Page,command:string,payload:object={}){
 const response=await (await page.request.post('/test-engine',{data:{command,payload}})).json()
 expect(response.ok,response.error).toBe(true);return response.data
}

test('ordinary existing targets can be remeasured without fabricating a loading control',async({page})=>{
 await page.goto('/?integration=1')
 const p=await rpc(page,'reference_case',{mode:'annotated'})
 delete p.example_case;p.name='Unlinked target '+p.id
 await rpc(page,'library_create_from_wb',{project:p})
 await page.reload()
 await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click()
 await page.getByRole('button',{name:'目标',exact:true}).click()
 await page.getByRole('button',{name:'重新识别',exact:true}).click()
 await expect(page.getByRole('button',{name:'确认目标',exact:true})).toBeEnabled()
 for(const select of await page.getByRole('combobox').all()){
  if((await select.getAttribute('aria-label'))?.endsWith('选择峰'))await select.selectOption('0')
 }
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 await expect(page.getByText('目标已确认',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'结果',exact:true}).click()
 const rows=page.getByRole('table',{name:'泳道定量结果'}).locator('tbody tr')
 await expect(rows).toHaveCount(9)
 await expect(rows.first()).toContainText('缺少参考')
})

async function drawRegion(page:Page){
 await page.getByRole('button',{name:'选择区域',exact:true}).click()
 const canvas=page.getByLabel('泳道分析画布')
 const points=await canvas.evaluate(e=>[[800,1200],[2040,1380]].map(xy=>{const p=new DOMPoint(...xy).matrixTransform((e as SVGSVGElement).getScreenCTM()!);return [p.x,p.y]}))
 await page.mouse.move(points[0][0],points[0][1]);await page.mouse.down();await page.mouse.move(points[1][0],points[1][1],{steps:4});await page.mouse.up()
}
async function chooseMainPeaks(page:Page){
 await expect(page.getByRole('button',{name:'确认目标',exact:true})).toBeVisible()
 for(const select of await page.getByRole('combobox').all()){
  if(!(await select.getAttribute('aria-label'))?.endsWith('选择峰'))continue
  const values=await select.locator('option').evaluateAll(options=>options.map(o=>({value:(o as HTMLOptionElement).value,text:o.textContent??''})))
  const valid=values.filter(o=>o.value!=='-1').map(o=>{const y=o.text.match(/y (\d+)–(\d+)/);return {...o,size:y?Number(y[2])-Number(y[1]):0}}).sort((a,b)=>b.size-a.size)
  await select.selectOption(valid[0].value)
 }
}

test('tutorial guides real actions through the formal editor and actual save/export',async({page})=>{
 const root=mkdtempSync(path.join(tmpdir(),'titan-guided-course-'))
 try{
  await page.goto('/?integration=1');await page.getByRole('button',{name:'教程',exact:true}).click()
  const tutorialName='Guided course '+Date.now();await page.getByLabel('实验名称',{exact:true}).fill(tutorialName)
  const coach=page.getByRole('region',{name:'WB 分步教程'})
  await expect(coach).toBeVisible()
  await expect(page.getByRole('dialog',{name:'用真实图像熟悉当前流程'})).toHaveCount(0)
  const next=coach.getByRole('button',{name:'下一步',exact:true})
  await next.click();await expect(next).toBeDisabled()
  await drawRegion(page);await next.click()
  await expect(next).toBeDisabled()
  await page.getByRole('button',{name:'调整泳道',exact:true}).click()
  await page.getByRole('button',{name:'L1',exact:true}).click();await next.click()
  await expect(next).toBeDisabled()
  await page.getByRole('button',{name:'识别目标',exact:true}).click();await chooseMainPeaks(page);await next.click()
  const toolbar=page.locator('.lane-toolbar')
  await expect(toolbar.getByRole('button',{name:'调整峰区',exact:true})).toHaveCount(0)
  await expect(toolbar.getByRole('button',{name:'画背景',exact:true})).toHaveCount(0)
  await expect(next).toBeEnabled()
  await next.click()
  await expect(next).toBeDisabled()
  await page.getByRole('button',{name:'确认目标',exact:true}).click();await next.click()
  await page.getByRole('button',{name:'结果',exact:true}).click()
  const table=page.getByRole('table',{name:'泳道定量结果'})
  await expect(table.locator('tbody tr')).toHaveCount(9)
  await expect(table.locator('tbody tr').first()).toContainText('缺少参考')
  await page.screenshot({path:'artifacts/checkpoints/guided-wb-results.png',fullPage:true})
  await next.click();await page.getByRole('button',{name:'WB 组图',exact:true}).click()
  await page.getByRole('button',{name:'新建组图',exact:true}).first().click()
  await page.getByRole('button',{name:'确认本行裁剪',exact:true}).click()
  await page.evaluate(()=>{(window as any).__TAURI_INTERNALS__={invoke:async(c:string)=>{if(c==='plugin:dialog|save')return null;throw Error(c)}}})
  await page.getByRole('button',{name:'保存组图',exact:true}).click()
  await expect(page.getByText('请先保存实验',{exact:false})).toBeVisible()
  await expect(coach.getByRole('button',{name:'完成教程',exact:true})).toBeDisabled()
  const projectPath=path.join(root,'guided.titanwb'),destination=path.join(root,'export')
  await page.evaluate((dest:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async(c:string)=>{if(c==='plugin:dialog|save')return dest;throw Error(c)}}},projectPath)
  await page.getByRole('button',{name:'保存组图',exact:true}).click()
  await expect(page.getByRole('status').filter({hasText:'组图已保存'})).toBeVisible()
  await page.evaluate(()=>{(window as any).__TAURI_INTERNALS__={invoke:async(c:string)=>{if(c==='plugin:dialog|save')return null;throw Error(c)}}})
  await page.getByRole('button',{name:'导出组图',exact:true}).click()
  await expect(coach.getByRole('button',{name:'完成教程',exact:true})).toBeDisabled()
  await page.evaluate((dest:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async(c:string)=>{if(c==='plugin:dialog|save')return dest;throw Error(c)}}},destination)
  await page.getByRole('button',{name:'导出组图',exact:true}).click()
  await expect(coach.getByRole('button',{name:'完成教程',exact:true})).toBeEnabled()
  await coach.getByRole('button',{name:'完成教程',exact:true}).click()
  await expect(page.getByText('教程已完成',{exact:false})).toBeVisible()
  for(const file of ['figure.png','figure.pdf','figure.svg','source.json'])expect(readFileSync(path.join(destination,file)).length).toBeGreaterThan(0)
  const saved=JSON.parse(readFileSync(path.join(projectPath,'project.json'),'utf8'))
  expect(saved.example_case.mode).toBe('tutorial');expect(saved.rois).toHaveLength(9)
  expect(saved.rois.every((r:any)=>r.reference_id===null&&r.reviewed_revision===saved.revision)).toBe(true)
  await page.reload();await page.getByRole('button',{name:'打开分析 '+tutorialName,exact:true}).click()
  await expect(page.getByText('教程已完成',{exact:false})).toBeVisible()
 }finally{rmSync(root,{recursive:true,force:true})}
})

test('coaching exits and resumes without replacing the formal workspace at narrow widths',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'教程',exact:true}).click()
 const coach=page.getByRole('region',{name:'WB 分步教程'})
 await expect(coach).toBeVisible()
 await coach.getByRole('button',{name:'下一步',exact:true}).click()
 await expect(coach.getByRole('button',{name:'下一步',exact:true})).toBeDisabled()
 await page.getByRole('button',{name:'退出引导',exact:true}).click()
 await expect(coach).toHaveCount(0)
 await expect(page.locator('.wb-tutorial-highlight')).toHaveCount(0)
 await expect(page.getByLabel('泳道分析画布')).toBeVisible()
 await page.getByRole('button',{name:'继续教程',exact:true}).click()
 await expect(coach.getByText('框选条带区域',{exact:true})).toBeVisible()
 for(const width of [1000,640]){
  await page.setViewportSize({width,height:1000})
  await expect(coach.getByRole('button',{name:'下一步',exact:true})).toBeVisible()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 }
 await page.screenshot({path:'artifacts/checkpoints/guided-wb-narrow.png',fullPage:true})
})

test('a saved step never restores nonexistent unconfirmed peak suggestions',async({page})=>{
 await page.goto('/?integration=1')
 const p=await rpc(page,'reference_case',{mode:'tutorial'});p.name='Recovery '+p.id
 await rpc(page,'library_create_from_wb',{project:p})
 await page.evaluate((id:string)=>localStorage.setItem('titan-wb-tutorial-v1',JSON.stringify([{projectId:id,step:4,status:'active',updated:1}])),p.id)
 await page.reload();await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click()
 const coach=page.getByRole('region',{name:'WB 分步教程'})
 await page.getByRole('button',{name:'目标',exact:true}).click()
 await expect(coach.getByRole('button',{name:'下一步',exact:true})).toBeDisabled()
 await expect(coach.getByRole('button',{name:'返回识别步骤',exact:true})).toBeVisible()
 await coach.getByRole('button',{name:'返回识别步骤',exact:true}).click()
 await expect(coach.getByText('识别峰区',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'识别目标',exact:true}).click();await chooseMainPeaks(page)
 await expect(coach.getByRole('button',{name:'下一步',exact:true})).toBeEnabled()
})

test('lane adjustment proposals do not trap the guide at a missing identify button',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'教程',exact:true}).click()
 const coach=page.getByRole('region',{name:'WB 分步教程'}),next=coach.getByRole('button',{name:'下一步',exact:true})
 await next.click();await drawRegion(page);await next.click()
 await page.getByRole('button',{name:'调整泳道',exact:true}).click()
 await page.getByRole('button',{name:'L1',exact:true}).click()
 await page.getByLabel('泳道分析画布').focus();await page.keyboard.press('ArrowRight')
 await chooseMainPeaks(page)
 await next.click()
 await expect(coach.getByText('识别峰区',{exact:true})).toBeVisible()
 await expect(next).toBeEnabled()
})
