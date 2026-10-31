import {test,expect} from '@playwright/test'
import {mkdtempSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {execFileSync} from 'node:child_process'
let root:string,file:string
test.beforeAll(()=>{
 root=mkdtempSync(path.join(tmpdir(),'titan-lanes-'));file=path.join(root,'lanes.tif')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
a=np.full((120,240),1000,dtype=np.uint16)
for x in [40,80,120,160,200]:
 a[30:40,x-10:x+10]=3000
 if x!=120:a[75:85,x-10:x+10]=5000
tifffile.imwrite(sys.argv[1],a,photometric='minisblack')`,file])
})
test.afterAll(()=>rmSync(root,{recursive:true,force:true}))
async function region(page:any,box:number[]){
 const svg=page.getByLabel('泳道分析画布');const bounds=(await svg.boundingBox())!
 const view=(await svg.getAttribute('viewBox'))!.split(' ').map(Number)
 const x=(v:number)=>bounds.x+(v-view[0])/view[2]*bounds.width,y=(v:number)=>bounds.y+(v-view[1])/view[3]*bounds.height
 await page.getByRole('button',{name:'选择区域',exact:true}).click()
 await page.mouse.move(x(box[0]),y(box[1]));await page.mouse.down();await page.mouse.move(x(box[2]),y(box[3]));await page.mouse.up()
}
test('reference first workflow preserves missing target slot and simple three-stage UI',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'新建实验',exact:true}).first().click()
 await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async(c:string)=>{if(c==='plugin:dialog|open')return [source];throw Error(c)}}},file)
 await page.getByRole('button',{name:'导入图像',exact:true}).click()
 await expect(page.getByRole('button',{name:'内参',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'目标',exact:true})).toBeVisible()
 await expect(page.getByRole('button',{name:'结果',exact:true})).toBeVisible()
 await region(page,[20,20,220,50])
 await page.getByRole('button',{name:'识别泳道',exact:true}).click()
 await expect(page.getByText('5 条泳道',{exact:true})).toBeVisible()
 await expect(page.getByTestId('task-panel').locator('input:visible,select:visible,textarea:visible')).toHaveCount(3)
 await page.getByRole('button',{name:'L1',exact:true}).click()
 await page.getByLabel('样本名称').fill('样本 A')
 await page.getByRole('button',{name:'确认内参',exact:true}).click()
 await expect(page.getByText('内参已确认',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'目标',exact:true}).click()
 await page.getByLabel('目标名称').fill('AKT')
 await page.getByRole('button',{name:'查看全图',exact:true}).click()
 await region(page,[20,65,220,95])
 await page.getByRole('button',{name:'识别目标',exact:true}).click()
 await expect(page.getByText('L3 · 未检出',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 await page.getByRole('button',{name:'结果',exact:true}).click()
 await expect(page.getByRole('table',{name:'泳道定量结果'})).toBeVisible()
 const rows=page.getByRole('table',{name:'泳道定量结果'}).locator('tbody tr')
 await expect(rows).toHaveCount(5)
 await expect(rows.nth(0)).toContainText('L1 / 样本 A')
 await expect(rows.nth(2)).toContainText('未检出')
 await expect(rows.nth(3)).toContainText('2')
 await page.screenshot({path:'artifacts/checkpoints/lane-results.png',fullPage:true})
 await page.getByRole('button',{name:'目标',exact:true}).click()
 await page.getByRole('button',{name:'添加下一个目标',exact:true}).click()
 await page.getByLabel('目标名称').fill('ERK')
 await page.getByRole('button',{name:'查看全图',exact:true}).click()
 await region(page,[20,65,220,95])
 await page.getByRole('button',{name:'识别目标',exact:true}).click()
 await page.getByRole('button',{name:'确认目标',exact:true}).click()
 await page.getByRole('button',{name:'显示反色',exact:true}).click()
 await page.getByRole('button',{name:'结果',exact:true}).click()
 await expect(rows).toHaveCount(10)
 await expect(rows.nth(8)).toContainText('L4 / S4')
 await expect(rows.nth(8)).toContainText('2')
 await expect(rows.nth(7)).toContainText('未检出')
})

test('cancelled lane recognition cannot add late suggestions',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'新建实验',exact:true}).first().click()
 await page.evaluate((source:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async()=>[source]}},file)
 await page.getByRole('button',{name:'导入图像',exact:true}).click()
 await expect(page.getByLabel('当前图像')).toContainText('lanes.tif')
 await region(page,[20,20,220,50])
 let release!:()=>void,entered!:()=>void;const gate=new Promise<void>(r=>release=r),started=new Promise<void>(r=>entered=r)
 await page.route('**/test-engine',async route=>{if(route.request().postDataJSON().command==='detect_lanes'){entered();await gate}await route.continue()})
 await page.getByRole('button',{name:'识别泳道',exact:true}).click();await started
 await page.getByRole('button',{name:'取消识别',exact:true}).click();release()
 await expect(page.getByRole('button',{name:'识别泳道',exact:true})).toBeEnabled()
 await expect(page.getByRole('button',{name:'确认内参',exact:true})).toHaveCount(0)
 await expect(page.getByText('0 个条带区域',{exact:false})).toBeVisible()
})
