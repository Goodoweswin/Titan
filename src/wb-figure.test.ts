import {describe,it,expect} from 'vitest'
import {resetWbStyle,proposedLabels,cropRect,defaultWbSettings,rebindWbSources,type WbDocument} from './wb-figure'
import {testProject} from './test-project'

describe('WB assembly display state',()=>{
 it('style reset keeps rows, crops, labels, marker coordinates and order',()=>{
  const doc={name:'my figure',rows:[{id:'b',crop:[1,2,20,30],markers:[{text:'75',y:8}]}],labels:[{text:'Ctrl',x:.3}],settings:{width_mm:100}} as unknown as WbDocument
  const reset=resetWbStyle(doc)
  expect(reset.settings).toEqual(defaultWbSettings)
  expect(reset.rows).toEqual(doc.rows);expect(reset.labels).toEqual(doc.labels);expect(reset.name).toBe(doc.name)
 })
 it('drag crops stay within the frame and cover an integer continuous rectangle',()=>{
  expect(cropRect([110,-2],[15,24],100,60)).toEqual([15,0,100,24])
  expect(cropRect([3,3],[3,3],100,60)).toBeNull()
 })
 it('save-as keeps a draft and rebinds both active and archived image sources',()=>{
  const project=testProject();project.project_path='/copy.titanwb';project.images[0].path='/copy.titanwb/originals/im.tif'
  const doc={rows:[{source:{...project.images[0],path:'/old.titanwb/originals/im.tif'}},{source:{id:'removed',sha256:'old',path:'/old.titanwb/originals/removed.png'}}]} as unknown as WbDocument
  const rebound=rebindWbSources(doc,project,'/old.titanwb')
  expect(rebound.rows.map(r=>r.source.path)).toEqual(['/copy.titanwb/originals/im.tif','/copy.titanwb/originals/removed.png'])
  expect(doc.rows[1].source.path).toBe('/old.titanwb/originals/removed.png')
 })
 it('lane labels follow source positions rather than fabricated equal spacing',()=>{
  const project=testProject()
  project.samples=[{id:'s1',name:'Ctrl',bio_id:'b1',group:'C',pair_id:'',kind:'biological',pool_id:''},{id:'s2',name:'Drug',bio_id:'b2',group:'D',pair_id:'',kind:'biological',pool_id:''}]
  project.lanes=[{id:'L1',sample_id:'s1',membrane_id:'m',technical_id:''},{id:'L2',sample_id:'s2',membrane_id:'m',technical_id:''}]
  project.lane_layouts=[{id:'l',image_id:'im',membrane_id:'m',window:[0,0,100,60],columns:[{lane_id:'L1',rect:[10,0,20,60]},{lane_id:'L2',rect:[70,0,90,60]}],excluded_regions:[],source_layout_id:null,confirmed_revision:0}]
  const row={layout_id:'l',crop:[0,0,100,20]} as any
  expect(proposedLabels(project,[row])).toEqual({labels:[{text:'Ctrl',x:.15},{text:'Drug',x:.8}],warning:''})
  expect(proposedLabels(project,[row,{...row,crop:[0,0,90,20]}]).warning).toContain('核对')
 })
})
