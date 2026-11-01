import {test,expect} from '@playwright/test'

async function rpc(page:any,command:string,payload:object={}){
 const response=await page.request.post('/test-engine',{data:{command,payload}}),envelope=await response.json()
 expect(envelope.ok,envelope.error).toBe(true);return envelope.data
}
async function openResults(page:any){
 await page.goto('/?integration=1')
 const created=await rpc(page,'library_create',{name:'结果界面验收 '+Date.now()});let p=await rpc(page,'demo')
 delete p.demo;p.synthetic=true;p.id=created.project.id;p.name=created.project.name;p.project_path=created.project.project_path;p.saved_revision=0
 const layout={id:'ui-layout',image_id:p.images[0].id,membrane_id:'M1',window:[0,0,520,160],columns:p.lanes.map((l:any)=>{const r=p.rois.find((r:any)=>r.lane_id===l.id);return {lane_id:l.id,rect:[r.rect[0],0,r.rect[2],160]}}),excluded_regions:[],source_layout_id:null,confirmed_revision:p.revision}
 p.lane_layouts=[layout]
 p.band_sets=['reference','target'].map(role=>({id:role,layout_id:layout.id,analyte:role==='target'?'TARGET':'Loading control',role,window:role==='target'?[0,20,520,80]:[0,80,520,140],reference_set_id:role==='target'?'reference':null,assignments:p.lanes.map((l:any)=>({lane_id:l.id,roi_id:p.rois.find((r:any)=>r.lane_id===l.id&&r.role===role).id,status:'accepted'}))}))
 p.rois.forEach((r:any)=>{r.band_set_id=r.role;r.lane_layout_id=layout.id})
 p=await rpc(page,'save_project',{project:p,path:p.project_path,expected_revision:0});await rpc(page,'library_register',{path:p.project_path})
 await page.reload();await page.getByRole('button',{name:'打开项目 '+p.name,exact:true}).click()
 await page.getByRole('button',{name:'结果',exact:true}).click()
 return p
}

test('results tabs preserve chart drafts and sample edits while extra columns stay lossless',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
 const p=await openResults(page)
 await expect(page.getByRole('table',{name:'泳道定量结果',exact:true})).toBeVisible()
 await page.getByRole('tab',{name:'样本设置',exact:true}).click()
 await expect(page.getByRole('table',{name:'样本设置',exact:true}).locator('tbody tr')).toHaveCount(p.lanes.length)
 await expect(page.getByLabel('批量组别',{exact:true})).not.toBeVisible()
 await expect(page.getByLabel('膜 L1',{exact:true})).not.toBeVisible()
 await page.getByRole('button',{name:'更多列',exact:true}).click()
 await expect(page.getByLabel('膜 L1',{exact:true})).toHaveValue('M1')
 await page.getByLabel('pair_id L1',{exact:true}).fill('P1')
 await page.getByRole('button',{name:'收起扩展列',exact:true}).click()
 await page.getByLabel('选择泳道 L1',{exact:true}).check()
 await page.getByLabel('批量组别',{exact:true}).fill('vehicle')
 await page.getByRole('button',{name:'填写组别',exact:true}).click()
 await expect(page.getByLabel('group L1',{exact:true})).toHaveValue('vehicle')
 await expect(page.getByLabel('group L2',{exact:true})).toHaveValue('vehicle')
 await expect(page.getByLabel('group L3',{exact:true})).toHaveValue(p.samples[1].group)
 await page.getByRole('tab',{name:'定量结果',exact:true}).click()
 await expect(page.getByRole('table',{name:'泳道定量结果',exact:true})).toBeVisible()
 await page.getByRole('tab',{name:'样本设置',exact:true}).click()
 await page.getByRole('button',{name:'更多列',exact:true}).click()
 await expect(page.getByLabel('膜 L1',{exact:true})).toHaveValue('M1')
 await expect(page.getByLabel('pair_id L1',{exact:true})).toHaveValue('P1')
 await page.getByRole('tab',{name:'统计与图表',exact:true}).click()
 await page.getByLabel('图形类型',{exact:true}).selectOption('scatter')
 await page.getByRole('tab',{name:'样本设置',exact:true}).click()
 await page.getByRole('tab',{name:'统计与图表',exact:true}).click()
 await expect(page.getByLabel('图形类型',{exact:true})).toHaveValue('scatter')
 expect(errors).toEqual([])
})

test('sample paste validates before applying and keyboard navigation remains available at narrow widths',async({page})=>{
 await openResults(page)
 await page.getByRole('tab',{name:'样本设置',exact:true}).click()
 await page.getByRole('button',{name:'粘贴样本表',exact:true}).click()
 await page.getByLabel('样本表 TSV',{exact:true}).fill('not-a-lane\tS1\tB1\tchanged\t\tM1')
 await page.getByRole('button',{name:'应用样本表',exact:true}).click()
 await expect(page.getByRole('status').filter({hasText:/未知|泳道/}).first()).toBeVisible()
 await expect(page.getByLabel('group L1',{exact:true})).toHaveValue('control')
 await page.getByLabel('样本表 TSV',{exact:true}).fill('L1\tS1\tB1\tvehicle\t\tM1')
 await page.getByRole('button',{name:'应用样本表',exact:true}).click()
 await expect(page.getByLabel('group L1',{exact:true})).toHaveValue('vehicle')
 await page.getByRole('button',{name:'粘贴样本表',exact:true}).click()
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
 await page.getByRole('tab',{name:'样本设置',exact:true}).focus()
 await page.keyboard.press('ArrowRight')
 await expect(page.getByRole('tab',{name:'统计与图表',exact:true})).toHaveAttribute('aria-selected','true')
 await page.getByRole('button',{name:'核对样本设计',exact:true}).click()
 await expect(page.getByRole('tab',{name:'样本设置',exact:true})).toHaveAttribute('aria-selected','true')
 await expect(page.getByRole('tab',{name:'样本设置',exact:true})).toBeFocused()
})
