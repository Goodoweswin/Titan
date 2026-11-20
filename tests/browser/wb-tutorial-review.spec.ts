import {test,expect,type Page} from '@playwright/test'

async function rpc(page:Page,command:string,payload:object={}){
 const r=await (await page.request.post('/test-engine',{data:{command,payload}})).json()
 expect(r.ok,r.error).toBe(true);return r.data
}
async function drawRegion(page:Page,rect=[800,1210,2040,1370]){
 await page.getByRole('button',{name:'选择区域',exact:true}).click()
 const points=await page.getByLabel('泳道分析画布').evaluate((e,r)=>[[r[0],r[1]],[r[2],r[3]]].map(xy=>{const p=new DOMPoint(...xy).matrixTransform((e as SVGSVGElement).getScreenCTM()!);return [p.x,p.y]}),rect)
 await page.mouse.move(...points[0] as [number,number]);await page.mouse.down();await page.mouse.move(...points[1] as [number,number],{steps:4});await page.mouse.up()
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
const command=(request:any,name:string)=>request.url().endsWith('/test-engine')&&request.postDataJSON()?.command===name

test('undo and redo restore the current region action evidence',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'教程',exact:true}).click()
 const next=page.getByRole('region',{name:'WB 分步教程'}).getByRole('button',{name:'下一步',exact:true})
 await next.click();await drawRegion(page);await expect(next).toBeEnabled()
 await page.getByRole('button',{name:'撤销',exact:true}).click();await expect(next).toBeDisabled()
 await page.getByRole('button',{name:'重做',exact:true}).click();await expect(next).toBeEnabled()
})

for(const mode of ['pending','measured'])test(`${mode} lane adjustments propose and commit the newly drawn region`,async({page})=>{
 await page.goto('/?integration=1')
 if(mode==='pending'){
  await page.getByRole('button',{name:'教程',exact:true}).click()
  const next=page.getByRole('region',{name:'WB 分步教程'}).getByRole('button',{name:'下一步',exact:true})
  await next.click();await drawRegion(page);await next.click()
 }else{
  const p=await rpc(page,'reference_case',{mode:'annotated'});delete p.example_case;p.name='Measured region '+p.id
  await rpc(page,'library_create_from_wb',{project:p});await page.reload();await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click();await page.getByRole('button',{name:'目标',exact:true}).click()
  await drawRegion(page)
 }
 await page.getByRole('button',{name:'调整泳道',exact:true}).click();await page.getByRole('button',{name:'L1',exact:true}).click()
 const proposal=page.waitForRequest(r=>command(r,'propose_bands'),{timeout:5000})
 await page.getByLabel('泳道分析画布').focus();await page.keyboard.press('ArrowRight')
 const payload=(await proposal).postDataJSON().payload,p=payload.project,g=p.band_sets.find((g:any)=>g.id===payload.band_set_id),l=p.lane_layouts.find((l:any)=>l.id===g.layout_id)
 expect(g.window).toEqual([800,1210,2040,1370]);expect(l.window).toEqual(g.window)
 expect(l.columns.every((c:any)=>c.rect[1]===1210&&c.rect[3]===1370)).toBe(true)
 await chooseMainPeaks(page)
 const analysis=page.waitForRequest(r=>command(r,'analyze')&&r.postDataJSON().payload.project.rois.length===9,{timeout:5000})
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 const committed=(await analysis).postDataJSON().payload.project
 expect(committed.band_sets[0].window).toEqual(g.window)
 expect(committed.rois.every((r:any)=>r.rect[1]>=1210&&r.rect[3]<=1370&&r.reviewed_revision===committed.revision)).toBe(true)
})

test('a fresh remeasurement must be confirmed before the guide accepts older committed ROIs',async({page})=>{
 await page.goto('/?integration=1')
 const p=await rpc(page,'reference_case',{mode:'annotated'});p.example_case.mode='tutorial';p.name='Remeasure tutorial '+p.id
 p.rois.forEach((r:any)=>r.reviewed_revision=p.revision);p.lane_layouts[0].confirmed_revision=p.revision
 await rpc(page,'library_create_from_wb',{project:p})
 await page.evaluate((id:string)=>localStorage.setItem('titan-wb-tutorial-v1',JSON.stringify([{projectId:id,step:5,status:'active',updated:1}])),p.id)
 await page.reload();await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click();await page.getByRole('button',{name:'目标',exact:true}).click()
 const next=page.getByRole('region',{name:'WB 分步教程'}).getByRole('button',{name:'下一步',exact:true})
 await expect(next).toBeEnabled()
 await page.getByRole('button',{name:'重新识别',exact:true}).click();await chooseMainPeaks(page)
 await expect(next).toBeDisabled()
 await page.getByRole('button',{name:'确认目标',exact:true}).click();await expect(next).toBeEnabled()
})

for(const referenceCount of [1,2])test(`an existing unlinked target keeps its raw measurements with ${referenceCount} unrelated references`,async({page})=>{
 await page.goto('/?integration=1')
 const p=await rpc(page,'reference_case',{mode:'annotated'});delete p.example_case;p.name='Unlinked with refs '+p.id
 for(let i=1;i<=referenceCount;i++){
  const l={...structuredClone(p.lane_layouts[0]),id:'other-layout-'+i};p.lane_layouts.push(l)
  p.band_sets.push({id:'other-ref-'+i,layout_id:l.id,analyte:'Other reference '+i,role:'reference',window:l.window,reference_set_id:null,assignments:l.columns.map((c:any)=>({lane_id:c.lane_id,roi_id:null,status:'pending'}))})
 }
 await rpc(page,'library_create_from_wb',{project:p});await page.reload();await page.getByRole('button',{name:'打开分析 '+p.name,exact:true}).click();await page.getByRole('button',{name:'目标',exact:true}).click()
 const reference=page.getByRole('combobox',{name:'对应内参',exact:true})
 await expect(reference).toHaveValue('')
 await page.getByRole('button',{name:'重新识别',exact:true}).click();await chooseMainPeaks(page)
 const analysis=page.waitForRequest(r=>command(r,'analyze')&&r.postDataJSON().payload.project.revision>p.revision)
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 const committed=(await analysis).postDataJSON().payload.project
 expect(committed.band_sets.find((g:any)=>g.role==='target').reference_set_id).toBeNull()
 expect(committed.rois.filter((r:any)=>r.role==='target').every((r:any)=>r.reference_id===null)).toBe(true)
 await expect(reference).toHaveValue('')
 await reference.selectOption('other-ref-1');await expect(reference).toHaveValue('other-ref-1')
 await expect(page.getByText('对应内参已切换，请重新识别目标后确认。')).toBeVisible()
})
