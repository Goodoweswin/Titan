import {test,expect} from '@playwright/test'
import {execFileSync} from 'node:child_process'
import path from 'node:path'
async function rpc(page:any,command:string,payload:object={}){const body=await(await page.request.post('/test-engine',{data:{command,payload}})).json();expect(body.ok,body.error).toBe(true);return body.data}
test('IF synthetic workflow measures original data, preserves display edits and reopens saved projects',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'免疫荧光',exact:true}).click({timeout:3000})
 await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click();await expect(page.getByLabel('IF 实验名称')).toBeVisible()
 await page.getByLabel('IF 实验名称').fill('IF 浏览器验收 '+Date.now())
 await expect(page.getByRole('img',{name:'免疫荧光原始通道预览'})).toBeVisible()
 await page.getByRole('button',{name:'测量当前视野',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'任务已完成'})).toBeVisible({timeout:30000})
 await page.getByRole('button',{name:'IF 定量结果',exact:true}).click();await expect(page.locator('.if-results tbody tr').first()).toBeVisible()
 const before=await page.locator('.if-results tbody').innerText();await page.getByRole('button',{name:'图像与分析',exact:true}).click()
 await page.getByLabel('DAPI 显示上限').fill('250');await page.getByRole('button',{name:'IF 定量结果',exact:true}).click();expect(await page.locator('.if-results tbody').innerText()).toBe(before)
 await page.getByRole('navigation',{name:'IF 实验视图',exact:true}).getByRole('button',{name:'IF 论文组图',exact:true}).click();await expect(page.getByRole('img',{name:'IF 论文组图预览'})).toBeVisible()
 await page.getByRole('button',{name:'保存 IF 实验',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'实验已保存'})).toBeVisible()
 const name=await page.getByLabel('IF 实验名称').inputValue();await page.reload();await page.getByRole('button',{name:'打开项目 '+name,exact:true}).click();await expect(page.getByLabel('IF 实验名称')).toHaveValue(name)
 await expect(page.getByRole('img',{name:'免疫荧光原始通道预览'})).toBeVisible();await page.screenshot({path:'artifacts/immunofluorescence/workspace.png',fullPage:true})
})
test('original-coordinate ROI drawing remains independent of display scale',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'免疫荧光',exact:true}).click();await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click()
 const canvas=page.getByLabel('IF 原始坐标画布'),box=(await canvas.boundingBox())!;await page.getByLabel('区域工具').selectOption('rectangle');await page.mouse.move(box.x+box.width*.2,box.y+box.height*.2);await page.mouse.down();await page.mouse.move(box.x+box.width*.4,box.y+box.height*.4);await page.mouse.up()
 await expect(page.locator('.if-roi-list li')).toHaveCount(3)
 await page.getByRole('button',{name:'保存 IF 实验',exact:true}).click();const entries=await rpc(page,'library_list');const latest=entries.find((e:any)=>e.module==='if');const p=await rpc(page,'if_open',{path:latest.path});const roi=p.fields[0].rois.at(-1);expect(roi.points[0][0]).toBeCloseTo(p.fields[0].width*.2,0);expect(roi.points[1][1]).toBeCloseTo(p.fields[0].height*.4,0)
})

test('nuclear segmentation requires confirmation and manual mask revisions persist',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'免疫荧光',exact:true}).click();await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click()
 await page.getByLabel('IF 分析模式').selectOption('nuclei');await expect(page.getByRole('button',{name:'测量当前视野',exact:true})).toBeDisabled()
 await page.getByRole('button',{name:'分割细胞核',exact:true}).click();await expect(page.getByRole('button',{name:'确认分割',exact:true})).toBeEnabled({timeout:30000});await expect(page.locator('.if-nucleus-label')).toHaveCount(9)
 await page.getByRole('button',{name:'确认分割',exact:true}).click();await page.getByRole('button',{name:'测量当前视野',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'任务已完成'})).toBeVisible({timeout:30000})
 await page.getByRole('button',{name:'IF 定量结果',exact:true}).click();await page.getByRole('button',{name:'对象（9）',exact:true}).click();await expect(page.locator('.if-results tbody tr')).toHaveCount(9)
 await page.getByRole('button',{name:'图像与分析',exact:true}).click();await page.locator('.if-nucleus-label').first().click();await page.getByRole('button',{name:'删除所选核',exact:true}).click();await expect(page.locator('.if-nucleus-label')).toHaveCount(8,{timeout:30000});await expect(page.getByRole('button',{name:'测量当前视野',exact:true})).toBeDisabled()
 await page.getByRole('button',{name:'撤销核编辑',exact:true}).click();await expect(page.locator('.if-nucleus-label')).toHaveCount(9);await expect(page.getByRole('button',{name:'测量当前视野',exact:true})).toBeDisabled();await page.getByRole('button',{name:'确认分割',exact:true}).click();await page.locator('.if-nucleus-label').first().click();await page.getByRole('button',{name:'删除所选核',exact:true}).click();await expect(page.locator('.if-nucleus-label')).toHaveCount(8,{timeout:30000});await page.getByLabel('区域工具').selectOption('add');const canvas=page.getByLabel('IF 原始坐标画布'),box=(await canvas.boundingBox())!;await page.mouse.move(box.x+box.width*50/256,box.y+box.height*50/256);await page.mouse.down();await page.mouse.move(box.x+box.width*80/256,box.y+box.height*80/256);await page.mouse.up();await expect(page.locator('.if-nucleus-label')).toHaveCount(9,{timeout:30000})
 await page.getByRole('button',{name:'确认分割',exact:true}).click();await page.getByRole('button',{name:'保存 IF 实验',exact:true}).click();const name=await page.getByLabel('IF 实验名称').inputValue();await page.reload();await page.getByRole('button',{name:'打开项目 '+name,exact:true}).first().click();await expect(page.locator('.if-nucleus-label')).toHaveCount(9)
})
test('cancel rejects a real completed job response arriving late',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'免疫荧光',exact:true}).click();await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click()
 let release:()=>void=()=>{};let observed:()=>void=()=>{};const completed=new Promise<void>(resolve=>observed=resolve),held=new Promise<void>(resolve=>release=resolve)
 await page.route('**/test-engine',async route=>{if(route.request().postDataJSON().command!=='if_job_status'){await route.continue();return}const response=await route.fetch();const body=await response.json();if(body.ok&&body.data.status==='completed'){observed();await held}await route.fulfill({response,json:body})})
 await page.getByRole('button',{name:'测量当前视野',exact:true}).click();await completed;await page.getByRole('button',{name:'取消 IF 任务',exact:true}).click();release();await expect(page.getByRole('status').filter({hasText:'任务已取消'})).toBeVisible()
 await page.getByRole('button',{name:'IF 定量结果',exact:true}).click();await expect(page.getByText('还没有有效测量结果',{exact:true})).toBeVisible();await expect(page.locator('.if-results tbody tr')).toHaveCount(0)
})

test('explicit metadata import and batch biological summaries export through the UI',async({page},testInfo)=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'免疫荧光',exact:true}).click();await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click()
 await page.getByRole('button',{name:'批量测量',exact:true}).click();await page.getByRole('button',{name:'开始批量测量',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'任务已完成'})).toBeVisible({timeout:30000})
 await page.getByRole('button',{name:'IF 定量结果',exact:true}).click();await expect(page.locator('.if-results tbody tr')).toHaveCount(6);await page.getByRole('button',{name:'生物学样本（6）',exact:true}).click();await expect(page.locator('.if-results tbody tr')).toHaveCount(6)
 await page.getByRole('button',{name:'导出 IF 结果',exact:true}).click();await page.getByLabel('IF 导出路径').fill(testInfo.outputPath('IF-results'));await page.getByRole('button',{name:'确认导出',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'已导出'})).toBeVisible({timeout:30000})
 const entries=await rpc(page,'library_list'),p=await rpc(page,'if_open',{path:entries.find((e:any)=>e.module==='if').path}),source=p.fields[0].channels[0].source.path
 await page.getByLabel('IF 实验名称').fill('待保存的免疫荧光实验')
 let releaseSave!:()=>void
 const holdSave=new Promise<void>(resolve=>{releaseSave=resolve})
 await page.route('**/test-engine',async route=>{
  if(route.request().postDataJSON().command==='if_save')await holdSave
  await route.continue()
 })
 const saving=page.waitForRequest(request=>request.url().endsWith('/test-engine')&&request.postDataJSON().command==='if_save')
 await page.getByRole('button',{name:'新建 IF 实验',exact:true}).click()
 await saving
 const importButton=page.getByRole('button',{name:'导入 IF 视野',exact:true}).first()
 try{await expect(importButton).toBeDisabled()}finally{releaseSave()}
 await expect(page.getByLabel('IF 实验名称')).toHaveValue('未命名 IF 实验')
 await importButton.click();await page.getByLabel('IF 原始文件路径').fill(source);await page.getByRole('button',{name:'读取图像信息',exact:true}).click();await expect(page.getByLabel('维度轴 1')).toHaveValue('CYX')
 await page.getByLabel('样本编号',{exact:true}).fill('S-import');await page.getByLabel('生物学样本编号',{exact:true}).fill('B-import');await page.getByLabel('实验分组',{exact:true}).fill('control');await page.getByLabel('采集批次',{exact:true}).fill('batch-import');await expect(page.getByRole('button',{name:'确认并导入视野',exact:true})).toBeDisabled();await page.getByText('已确认所选文件属于同一视野，通道对应及 Z / T 平面正确',{exact:true}).click();await page.getByRole('button',{name:'确认并导入视野',exact:true}).click();await expect(page.getByRole('img',{name:'免疫荧光原始通道预览'})).toBeVisible({timeout:30000});await expect(page.getByLabel('当前生物学样本编号')).toHaveValue('B-import')
 await page.setViewportSize({width:720,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'artifacts/immunofluorescence/import-720.png',fullPage:true})
})

test('multi-series import resets plane selectors and adopts selected-series calibration',async({page},testInfo)=>{
 const source=testInfo.outputPath('multi-series.ome.tif');execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
with tifffile.TiffWriter(sys.argv[1],ome=True) as t:
 t.write(np.ones((16,20),dtype=np.uint16),photometric='minisblack',metadata={'axes':'YX','PhysicalSizeX':.5,'PhysicalSizeY':.5})
 t.write(np.ones((2,24,32),dtype=np.uint16)*2000,photometric='minisblack',metadata={'axes':'ZYX','PhysicalSizeX':.75,'PhysicalSizeY':.8})`,source])
 await page.goto('/?integration=1');await page.getByRole('button',{name:'免疫荧光',exact:true}).click();await page.getByRole('button',{name:'新建 IF 实验',exact:true}).first().click();await page.getByRole('button',{name:'导入 IF 视野',exact:true}).first().click()
 await page.getByLabel('IF 原始文件路径').fill(source);await page.getByRole('button',{name:'读取图像信息',exact:true}).click();await page.getByLabel('图像序列').selectOption('1',{timeout:5000});await page.getByLabel('样本编号',{exact:true}).fill('S-series');await page.getByLabel('生物学样本编号',{exact:true}).fill('B-series');await page.getByLabel('实验分组',{exact:true}).fill('control');await page.getByLabel('采集批次',{exact:true}).fill('series');await page.getByText('已确认所选文件属于同一视野，通道对应及 Z / T 平面正确',{exact:true}).click()
 const selectedCalibration=await page.getByLabel('X 像素尺寸（µm，可空）',{exact:true}).inputValue();const submitted=page.waitForRequest(r=>r.url().endsWith('/test-engine')&&r.postDataJSON().command==='if_start_job');await page.getByRole('button',{name:'确认并导入视野',exact:true}).click();expect((await submitted).postDataJSON().payload.options.selections[0].indexers).toEqual({Z:0});expect(Number(selectedCalibration)).toBe(.75)
 await expect(page.getByRole('img',{name:'免疫荧光原始通道预览'})).toBeVisible({timeout:30000});await expect(page.getByText('32 × 24 px · 0.75 × 0.8 µm/px',{exact:true})).toBeVisible()
})

test('dense masks remain editable beyond the centroid annotation limit',async({page},testInfo)=>{
 await page.goto('/?integration=1');const p=await rpc(page,'if_demo');p.name='Dense mask '+Date.now();p.fields=p.fields.slice(0,1);p.fields[0].recipe.mode='nuclei'
 const maskPath=testInfo.outputPath('dense-labels.tif');p.fields[0].mask=JSON.parse(execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,json,hashlib,numpy as np,tifffile
from titan_if.models import segmentation_signature
labels=np.repeat(np.repeat(np.arange(1,4097,dtype=np.uint32).reshape(64,64),4,axis=0),4,axis=1)
tifffile.imwrite(sys.argv[1],labels,photometric='minisblack')
print(json.dumps({'path':sys.argv[1],'sha256':hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(),'version':1,'confirmed':True,'segmentation_signature':segmentation_signature(json.loads(sys.argv[2])),'history':[]}))`,maskPath,JSON.stringify(p.fields[0])],{env:{...process.env,PYTHONPATH:path.resolve('backend')},encoding:'utf8'}));p.revision++;await rpc(page,'if_save',{project:p,expected_revision:p.saved_revision});await page.reload();await page.getByRole('button',{name:'打开项目 '+p.name,exact:true}).click();await expect(page.locator('.if-nucleus-label')).toHaveCount(3000,{timeout:30000})
 const canvas=page.getByLabel('IF 原始坐标画布');await canvas.scrollIntoViewIfNeeded();const box=(await canvas.boundingBox())!;await page.mouse.click(box.x+box.width*174/256,box.y+box.height*218/256);await expect(page.locator('.if-mask-actions')).toContainText('已选 1 个');await page.getByRole('button',{name:'删除所选核',exact:true}).click();await expect(page.locator('.if-mask-actions')).toContainText('4095',{timeout:30000})
})
