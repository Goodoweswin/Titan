import {test,expect, type Page} from '@playwright/test'
import {mkdtempSync,rmSync,readFileSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {execFileSync} from 'node:child_process'
let root:string,file:string,targetFile:string,portraitFile:string,wideFile:string
test.beforeAll(()=>{
 root=mkdtempSync(path.join(tmpdir(),'titan-edit-'));file=path.join(root,'lanes.tif')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
a=np.full((120,240),1000,dtype=np.uint16)
for x in [40,80,120,160,200]:a[30:40,x-10:x+10]=3000
tifffile.imwrite(sys.argv[1],a)`,file])
 targetFile=path.join(root,'target-crop.tif')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
a=np.full((260,480),1000,dtype=np.uint16)
for x in [84,132,180,228,276]:a[195:207,x-12:x+12]=5000
tifffile.imwrite(sys.argv[1],a)`,targetFile])
 portraitFile=path.join(root,'portrait.tif');wideFile=path.join(root,'wide.tif')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
a=np.full((1000,100),1000,dtype=np.uint16)
tifffile.imwrite(sys.argv[1],a);tifffile.imwrite(sys.argv[2],a.T)`,portraitFile,wideFile])
})
test.afterAll(()=>rmSync(root,{recursive:true,force:true}))
async function drag(page:Page,a:number[],b:number[]){
 const svg=page.getByLabel('泳道分析画布'),bounds=(await svg.boundingBox())!,v=(await svg.getAttribute('viewBox'))!.split(' ').map(Number)
 const at=(p:number[])=>[bounds.x+(p[0]-v[0])/v[2]*bounds.width,bounds.y+(p[1]-v[1])/v[3]*bounds.height]
 const from=at(a),to=at(b);await page.mouse.move(...from as [number,number]);await page.mouse.down();await page.mouse.move(...to as [number,number],{steps:4});await page.mouse.up()
}
async function setup(page:Page){
 await page.goto('/?integration=1');await page.getByRole('button',{name:'新建实验',exact:true}).first().click()
 await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async()=>[source]}},file)
 await page.getByRole('button',{name:'导入图像',exact:true}).click();await expect(page.getByLabel('当前图像')).toContainText('lanes.tif')
 await drag(page,[20,20],[220,50]);await page.getByRole('button',{name:'识别泳道',exact:true}).click()
 await page.getByRole('button',{name:'确认内参',exact:true}).click();await expect(page.getByText('内参已确认',{exact:true})).toBeVisible()
}
async function box(page:Page,label:string){return page.getByLabel(label,{exact:true}).evaluate(e=>['x','y','width','height'].map(k=>Number(e.getAttribute(k))))}
test('image view zoom and Space pan preserve original region coordinates',async({page})=>{
 await setup(page)
 const card=page.locator('.lane-canvas-card'),canvas=page.getByLabel('泳道分析画布')
 await expect(card.getByRole('button',{name:'放大图像',exact:true})).toBeVisible({timeout:2000})
 await page.getByRole('button',{name:'选择区域',exact:true}).click()
 const original=await box(page,'识别区域')
 await card.getByRole('button',{name:'放大图像',exact:true}).click()
 const before=(await canvas.getAttribute('viewBox'))!.split(' ').map(Number),bounds=(await canvas.boundingBox())!
 await canvas.focus();await page.keyboard.down('Space')
 await page.mouse.move(bounds.x+bounds.width*.55,bounds.y+bounds.height*.55);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width*.55+25,bounds.y+bounds.height*.55+10,{steps:4});await page.mouse.up()
 // Holding Space across successive drags must never fall back to region drawing.
 await page.mouse.move(bounds.x+bounds.width*.55,bounds.y+bounds.height*.55);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width*.55+10,bounds.y+bounds.height*.55,{steps:3});await page.mouse.up();await page.keyboard.up('Space')
 const after=(await canvas.getAttribute('viewBox'))!.split(' ').map(Number)
 expect(after[0]).toBeLessThan(before[0]);expect(after[1]).toBeLessThan(before[1]);expect(await box(page,'识别区域')).toEqual(original)
 await drag(page,[100,28],[130,42])
 await expect.poll(()=>box(page,'识别区域')).toEqual([100,28,30,14])
 await page.getByRole('button',{name:'查看全图',exact:true}).click()
 await expect(canvas).toHaveAttribute('viewBox','0 0 240 120')
})

test('rotation preview zooms at the pointer and pans without moving level guides or changing the angle',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())})
 await setup(page);await page.getByRole('button',{name:'旋转校正',exact:true}).click()
 const dialog=page.getByRole('dialog',{name:'旋转校正'}),canvas=dialog.getByLabel('旋转校正画布')
 await expect(dialog.getByRole('button',{name:'放大图像',exact:true})).toBeVisible({timeout:2000})
 await dialog.getByLabel('旋转角度',{exact:true}).fill('5')
 const b=(await canvas.boundingBox())!,pointer=[b.x+b.width*.7,b.y+b.height*.7].map(Math.round)
 const atPointer=()=>canvas.evaluate((e,xy)=>{const p=new DOMPoint(...xy).matrixTransform((e as SVGSVGElement).getScreenCTM()!.inverse());return [p.x,p.y]},pointer)
 const anchor=await atPointer(),before=(await canvas.getAttribute('viewBox'))!.split(' ').map(Number)
 await page.mouse.move(pointer[0],pointer[1]);await page.mouse.wheel(0,-350)
 await expect.poll(async()=>Number((await canvas.getAttribute('viewBox'))!.split(' ')[2])).toBeLessThan(before[2])
 const same=await atPointer();expect(same[0]).toBeCloseTo(anchor[0],3);expect(same[1]).toBeCloseTo(anchor[1],3)
 const zoomed=await canvas.getAttribute('viewBox')
 await page.mouse.down({button:'middle'});await page.mouse.move(pointer[0]+30,pointer[1]+15,{steps:3});await page.mouse.up({button:'middle'})
 await expect(canvas).not.toHaveAttribute('viewBox',zoomed!)
 await expect(dialog.getByRole('slider',{name:'水平参考线',exact:true})).toHaveAttribute('aria-valuenow','50')
 await expect(dialog.getByRole('slider',{name:'垂直参考线',exact:true})).toHaveAttribute('aria-valuenow','50')
 await expect(dialog.getByLabel('旋转角度',{exact:true})).toHaveValue('5')
 await dialog.screenshot({path:'artifacts/image-viewport/rotation-zoom.png'})
 await dialog.getByRole('button',{name:'适合窗口',exact:true}).click()
 const fitted=(await canvas.getAttribute('viewBox'))!.split(' ').map(Number);expect(fitted[2]).toBeGreaterThan(240)
 await page.setViewportSize({width:390,height:844})
 expect(await dialog.evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBe(true)
 await dialog.screenshot({path:'artifacts/image-viewport/rotation-narrow.png'})
 await dialog.getByRole('button',{name:'取消',exact:true}).click()
 await expect(page.getByLabel('当前图像').locator('option')).toHaveCount(1)
 expect(errors).toEqual([])
})

test('rotated portrait and wide image fits never reverse the zoom buttons',async({page})=>{
 for(const source of [portraitFile,wideFile]){
  await page.goto('/?integration=1');await page.getByRole('button',{name:'新建实验',exact:true}).first().click()
  await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async()=>[source]}},source)
  await page.getByRole('button',{name:'导入图像',exact:true}).click()
  await page.getByRole('button',{name:'旋转校正',exact:true}).click()
  const dialog=page.getByRole('dialog',{name:'旋转校正'}),canvas=dialog.getByLabel('旋转校正画布')
  await dialog.getByLabel('旋转角度',{exact:true}).fill('90');await dialog.getByRole('button',{name:'适合窗口',exact:true}).click()
  const fitted=Number((await canvas.getAttribute('viewBox'))!.split(' ')[2])
  await dialog.getByRole('button',{name:'缩小图像',exact:true}).click()
  expect(Number((await canvas.getAttribute('viewBox'))!.split(' ')[2])).toBeGreaterThan(fitted)
  await dialog.getByRole('button',{name:'适合窗口',exact:true}).click();await dialog.getByRole('button',{name:'放大图像',exact:true}).click()
  expect(Number((await canvas.getAttribute('viewBox'))!.split(' ')[2])).toBeLessThan(fitted)
  await dialog.getByRole('button',{name:'取消',exact:true}).click()
 }
})

test('Space released after leaving a guide never leaves image panning stuck',async({page})=>{
 await setup(page);await page.getByRole('button',{name:'旋转校正',exact:true}).click()
 const dialog=page.getByRole('dialog',{name:'旋转校正'}),horizontal=dialog.getByRole('slider',{name:'水平参考线',exact:true}),canvas=dialog.getByLabel('旋转校正画布')
 await horizontal.focus();await page.keyboard.down('Space');await dialog.getByLabel('旋转角度',{exact:true}).click();await page.keyboard.up('Space')
 const before=await canvas.getAttribute('viewBox'),bounds=(await page.locator('.rotation-preview').boundingBox())!,h=(await horizontal.boundingBox())!
 await page.mouse.move(h.x+h.width*.25,h.y+h.height/2);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width*.25,bounds.y+bounds.height*.7);await page.mouse.up()
 await expect(horizontal).toHaveAttribute('aria-valuenow','70');await expect(canvas).toHaveAttribute('viewBox',before!)
})

test('lane mode ignores blank drags and drags confirmed lanes through their peak overlay',async({page})=>{
 await setup(page);const region=await box(page,'识别区域');const lane=await box(page,'泳道 L2'),peak=await box(page,'峰区 L2'),other=await box(page,'峰区 L3')
 let selections=0;await page.route('**/test-engine',async route=>{if(route.request().postDataJSON().command==='detect_lanes')selections++;await route.continue()})
 await drag(page,[22,22],[25,24]);expect(await box(page,'识别区域')).toEqual(region);await expect(page.getByRole('button',{name:'添加目标',exact:true})).toBeVisible()
 await drag(page,[peak[0]+peak[2]/2,peak[1]+peak[3]/2],[peak[0]+peak[2]/2+2,peak[1]+peak[3]/2])
 await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+2)
 expect(await box(page,'峰区 L3')).toEqual(other);expect(selections).toBe(0)
 await expect(page.getByRole('button',{name:'确认内参',exact:true})).toBeVisible()
 await page.locator('.lane-canvas-card').screenshot({path:'artifacts/lane-editing/lane-controls.png'})
 await page.getByTitle('撤销',{exact:true}).click();expect(await box(page,'泳道 L2')).toEqual(lane)
 await page.getByTitle('重做',{exact:true}).click();expect((await box(page,'泳道 L2'))[0]).toBe(lane[0]+2)
 await page.getByRole('button',{name:'确认内参',exact:true}).click()
 await page.getByTitle('撤销',{exact:true}).click();expect(await box(page,'泳道 L2')).toEqual(lane)
})
test('both lane boundaries and keyboard nudges work without changing other lane peaks',async({page})=>{
 await setup(page);await page.getByRole('button',{name:'L2',exact:true}).click()
 const lane=await box(page,'泳道 L2'),other=await box(page,'峰区 L3')
 await drag(page,[lane[0],lane[1]+lane[3]/2],[lane[0]+2,lane[1]+lane[3]/2])
 await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+2)
 expect((await box(page,'泳道 L2'))[2]).toBe(lane[2]-2)
 const canvas=page.getByLabel('泳道分析画布');await canvas.focus();await page.keyboard.press('ArrowLeft')
 await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+1)
 await page.keyboard.press('Shift+ArrowRight');await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+11)
 expect(await box(page,'峰区 L3')).toEqual(other)
 await page.keyboard.press('Control+z');await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+1)
 await page.keyboard.press('Control+Shift+z');await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+11)
})
test('region selection is reversible without undoing the imported image',async({page})=>{
 await setup(page);await page.getByRole('button',{name:'选择区域',exact:true}).click();await drag(page,[22,22],[215,48])
 await page.getByTitle('撤销',{exact:true}).click();await expect(page.getByText('内参已确认',{exact:true})).toBeVisible();await expect(page.getByLabel('当前图像')).toContainText('lanes.tif')
})
test('rotation keeps the original and requires explicit lane identity mapping on the corrected reference',async({page})=>{
 await setup(page);const oldImage=await page.getByLabel('当前图像').inputValue()
 await page.getByRole('button',{name:'旋转校正',exact:true}).click()
 await page.getByLabel('旋转角度',{exact:true}).fill('-2')
 await page.getByRole('button',{name:'应用校正',exact:true}).click()
 await expect(page.getByLabel('当前图像')).not.toHaveValue(oldImage)
 await expect(page.getByLabel('当前图像').locator('option')).toHaveCount(2)
 await page.getByRole('button',{name:'查看全图',exact:true}).click();await drag(page,[15,20],[225,60])
 await page.getByRole('button',{name:'识别泳道',exact:true}).click()
 await expect(page.getByText('核对泳道对应',{exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'确认泳道对应',exact:true})).toBeDisabled()
 for(let i=1;i<=5;i++)await page.getByLabel(`候选 ${i} 对应泳道`,{exact:true}).selectOption(`L${i}`)
 await page.getByRole('button',{name:'确认泳道对应',exact:true}).click()
 await expect(page.getByRole('button',{name:'确认内参',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'确认内参',exact:true}).click()
 await expect(page.getByText('内参已确认',{exact:true})).toBeVisible()
 await page.getByTitle('撤销',{exact:true}).click()
 // Undo confirmation restores the previous reference, never a silently remapped one.
 await expect(page.getByLabel('当前图像')).toHaveValue(oldImage)
 await expect(page.getByLabel('泳道 L1',{exact:true})).toBeVisible()
})
test('undo during recognition discards its late result and redo can finish recognition',async({page})=>{
 await setup(page)
 let release!:()=>void,entered!:()=>void,once=true;const gate=new Promise<void>(r=>release=r),started=new Promise<void>(r=>entered=r)
 await page.route('**/test-engine',async route=>{if(once&&route.request().postDataJSON().command==='propose_bands'){once=false;entered();await gate}await route.continue()})
 await page.getByRole('button',{name:'重新识别',exact:true}).click();await started
 await page.getByTitle('撤销',{exact:true}).click();release()
 await expect(page.getByText('内参已确认',{exact:true})).toBeVisible()
 await page.getByTitle('重做',{exact:true}).click()
 await expect(page.getByRole('button',{name:'确认内参',exact:true})).toBeVisible()
})

test('rotation guides stay level while rotating and can be moved to the bands',async({page})=>{
 await setup(page);await page.getByRole('button',{name:'旋转校正',exact:true}).click()
 const horizontal=page.getByRole('slider',{name:'水平参考线',exact:true}),vertical=page.getByRole('slider',{name:'垂直参考线',exact:true})
 await expect(horizontal).toBeVisible();await expect(vertical).toBeVisible()
 await page.getByLabel('旋转角度',{exact:true}).fill('5')
 const preview=page.locator('.rotation-preview'),bounds=(await preview.boundingBox())!
 const h=(await horizontal.boundingBox())!
 await page.mouse.move(h.x+h.width*.25,h.y+h.height/2);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width*.25,bounds.y+bounds.height*.7);await page.mouse.up()
 await expect(horizontal).toHaveAttribute('aria-valuenow','70')
 await vertical.focus();await page.keyboard.press('ArrowRight');await expect(vertical).toHaveAttribute('aria-valuenow','51')
 await page.getByRole('button',{name:'参考线居中',exact:true}).click();await expect(horizontal).toHaveAttribute('aria-valuenow','50')
 await page.locator('.rotation-dialog').screenshot({path:'artifacts/target-parity/rotation-guides.png'})
 await page.getByRole('checkbox',{name:'显示参考线',exact:true}).uncheck();await expect(horizontal).toHaveCount(0)
})
test('target import selects the new crop and offers the same visible handles and undo as reference',async({page})=>{
 await setup(page);await page.getByRole('button',{name:'添加目标',exact:true}).click()
 await expect(page.getByRole('button',{name:'选择区域',exact:true})).toHaveAttribute('aria-pressed','true')
 await page.getByLabel('目标名称',{exact:true}).fill('AKT')
 await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async()=>[source]}},targetFile)
 await page.getByRole('button',{name:'导入目标图像',exact:true}).click()
 await expect(page.getByLabel('当前图像')).toContainText('target-crop.tif')
 await drag(page,[60,180],[300,230]);await page.getByRole('button',{name:'识别目标',exact:true}).click()
 await expect(page.getByRole('button',{name:'确认目标',exact:true})).toBeVisible()
 const lane=await box(page,'泳道 L2');expect(lane[1]).toBe(180);expect(lane[3]).toBe(50)
 await page.getByRole('button',{name:'L2',exact:true}).click()
 const handle=page.getByLabel('调整泳道左边界',{exact:true}),bounds=(await handle.boundingBox())!,canvas=(await page.getByLabel('泳道分析画布').boundingBox())!
 expect(bounds.y).toBeGreaterThan(canvas.y);expect(bounds.y+bounds.height).toBeLessThan(canvas.y+canvas.height)
 await page.locator('.lane-workspace').screenshot({path:'artifacts/target-parity/target-controls.png'})
 await drag(page,[lane[0],205],[lane[0]+2,205]);await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+2)
 await page.getByTitle('撤销',{exact:true}).click();expect(await box(page,'泳道 L2')).toEqual(lane)
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 const peak=await box(page,'峰区 L2');await drag(page,[peak[0]+peak[2]/2,peak[1]+peak[3]/2],[peak[0]+peak[2]/2+2,peak[1]+peak[3]/2])
 await expect.poll(async()=>(await box(page,'泳道 L2'))[0]).toBe(lane[0]+2)
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 await page.getByRole('button',{name:'重新识别泳道位置',exact:true}).click()
 await expect(page.getByText('核对目标泳道对应',{exact:true})).toBeVisible()
 for(let i=1;i<=5;i++)await page.getByLabel(`候选 ${i} 对应泳道`,{exact:true}).selectOption(`L${i}`)
 await page.getByRole('button',{name:'确认泳道对应',exact:true}).click()
 await page.getByRole('button',{name:'确认目标',exact:true}).click();await expect(page.getByText('目标已确认',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'选择区域',exact:true}).click();await drag(page,[60,215],[300,245])
 await page.getByRole('button',{name:'重新识别',exact:true}).click()
 await expect(page.getByText('L1 · 未检出',{exact:true})).toBeVisible()
 expect((await box(page,'泳道 L1'))[1]).toBe(215)
})

test('re-identifying a confirmed target uses the newly selected reference',async({page})=>{
 const projectPath=path.join(root,'two-references.titanwb')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys
from titan_wb.models import new_project
from titan_wb.images import import_image
from titan_wb.projects import save_project,release_project
p=import_image(new_project('two references'),sys.argv[1]);im=p['images'][0]['id'];rev=p['revision']
p['samples']=[dict(id=f'S{i}',bio_id=f'B{i}',group='control',pair_id='',kind='biological',pool_id='') for i in range(1,6)]
p['lanes']=[dict(id=f'L{i}',sample_id=f'S{i}',membrane_id='M1',technical_id='1') for i in range(1,6)]
for n in [1,2]:
 lid=f'layout{n}';sid=f'ref{n}';name=f'REF{n}';cols=[];assignments=[]
 for i,x in enumerate([40,80,120,160,200],1):
  cols.append(dict(lane_id=f'L{i}',rect=[x-12,20,x+12,50]));rid=f'r{n}-{i}'
  p['rois'].append(dict(id=rid,image_id=im,lane_id=f'L{i}',analyte=name,role='reference',rect=[x-12,30,x+12,40],backgrounds=[[x-12,20,x+12,24]],reference_id=None,reviewed_revision=rev,lane_layout_id=lid,band_set_id=sid))
  assignments.append(dict(lane_id=f'L{i}',roi_id=rid,status='accepted'))
 p['lane_layouts'].append(dict(id=lid,image_id=im,membrane_id='M1',window=[20,20,220,50],columns=cols,excluded_regions=[],source_layout_id=None,confirmed_revision=rev))
 p['band_sets'].append(dict(id=sid,layout_id=lid,analyte=name,role='reference',window=[20,20,220,50],reference_set_id=None,assignments=assignments))
session=dict(pid=0,token='fixture');save_project(p,sys.argv[2],None,session);release_project(sys.argv[2],session)`,file,projectPath],{env:{...process.env,PYTHONPATH:path.resolve('backend')}})
 await page.goto('/?integration=1')
 await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async()=>source}},projectPath)
 await page.getByRole('button',{name:'打开项目',exact:true}).first().click()
 await page.getByRole('button',{name:'添加目标',exact:true}).click();await page.getByLabel('目标名称',{exact:true}).fill('AKT')
 await page.getByRole('button',{name:'选择区域',exact:true}).click();await drag(page,[20,20],[220,50]);await page.getByRole('button',{name:'识别目标',exact:true}).click();await page.getByRole('button',{name:'确认目标',exact:true}).click()
 await page.getByLabel('对应内参',{exact:true}).selectOption('ref2')
 await page.getByRole('button',{name:'重新识别',exact:true}).click();await expect(page.getByRole('button',{name:'调整泳道',exact:true})).toBeEnabled();await page.getByRole('button',{name:'确认目标',exact:true}).click()
 await page.getByRole('button',{name:'保存实验',exact:true}).click()
 await expect(page.getByText('实验已保存；保存期间的新修改仍保留。',{exact:true})).toBeVisible()
 const saved=JSON.parse(readFileSync(path.join(projectPath,'project.json'),'utf8'))
 expect(saved.band_sets.find((g:any)=>g.role==='target').reference_set_id).toBe('ref2')
 await page.getByTitle('撤销',{exact:true}).click();await expect(page.getByLabel('对应内参',{exact:true})).toHaveValue('ref1')
 await page.getByTitle('重做',{exact:true}).click();await expect(page.getByLabel('对应内参',{exact:true})).toHaveValue('ref2')
})
