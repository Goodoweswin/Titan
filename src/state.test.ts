import {describe,it,expect} from 'vitest'
import {createProject,editProject,screenToImage,commitResult,mergeSaved,restoreHistory,acceptReview,mergeImported,retainResult} from './state'
import {testProject} from './test-project'
describe('project identity',()=>{
 it('starts at a clean independent revision',()=>{
  const a=createProject('实验一'), b=createProject('实验二')
  expect(a.revision).toBe(0);expect(a.schema_version).toBe(1)
  expect(a.id).not.toBe(b.id);expect(a.rois).toEqual([])
 })
 it('rejects an empty experiment name',()=>{expect(()=>createProject('  ')).toThrow()})
})
describe('persistence races and history',()=>{
 it('late save preserves a newer edit and advances only the disk baseline',()=>{
  const base=createProject('a');const edited=editProject(base,p=>p.name='newer')
  const saved={...base,project_path:'/p.titanwb',saved_revision:0}
  const merged=mergeSaved(edited,saved)!
  expect(merged.name).toBe('newer');expect(merged.revision).toBe(1)
  expect(merged.saved_revision).toBe(0);expect(merged.project_path).toBe('/p.titanwb')
 })
 it('late save cannot replace a different current project',()=>{
  const current=createProject('b'),saved=createProject('a')
  expect(mergeSaved(current,saved)).toBe(current)
 })
 it('undo keeps the latest disk revision and path after a save',()=>{
  const old=createProject('old'),current={...editProject(old,p=>p.name='new'),saved_revision:1,project_path:'/p.titanwb'}
  const undone=restoreHistory(current,old)
  expect(undone.saved_revision).toBe(1);expect(undone.project_path).toBe('/p.titanwb');expect(undone.revision).toBe(2)
 })
 it('late review cannot restore approval after an ROI or settings edit',()=>{
  const base=createProject('a'),checked={...base,revision:1},newer=editProject(base,p=>p.name='edited')
  expect(acceptReview(newer,base,checked)).toBeNull()
 })
 it('late import adds assets without overwriting newer metadata',()=>{
  const base=createProject('a'),newer=editProject(base,p=>p.name='newer')
  const incoming={...base,images:[{id:'image',name:'tif'} as any]}
  const merged=mergeImported(newer,base,incoming)!
  expect(merged.name).toBe('newer');expect(merged.images).toHaveLength(1)
 })
})
describe('edits and async revision boundaries',()=>{
 it('invalidates review on every analytical edit without mutating history',()=>{
  const p=testProject()
  const q=editProject(p,x=>{x.rois[0].rect=[11,20,31,30]})
  expect(q.revision).toBe(1);expect(q.rois[0].reviewed_revision).toBeNull()
  expect(p.rois[0].reviewed_revision).toBe(0)
 })
 it('maps identical pixels at two zoom levels to identical raw coordinates',()=>{
  expect(screenToImage([10,20,30,40],100,100,100,100)).toEqual([10,20,30,40])
  expect(screenToImage([20,40,60,80],200,200,100,100)).toEqual([10,20,30,40])
 })
 it('rejects a late result for old revision or a different project',()=>{
  const p=createProject('a');p.revision=4
  expect(commitResult(p,{project_id:p.id,input_revision:3} as any)).toBeNull()
  expect(commitResult(p,{project_id:'other',input_revision:4} as any)).toBeNull()
 })
})

describe('scoped review and result validity',()=>{
 it('keeps reviews after rename and rebases an eligible result for export',()=>{
  const p=testProject(),next=editProject(p,d=>{d.name='renamed'})
  expect(next.rois.map(r=>r.reviewed_revision)).toEqual([1,1,1,1])
  const result={project_id:p.id,input_revision:0,measurements:[],normalized:[],biological:[],statistics:[]}
  expect(retainResult(p,next,result)?.input_revision).toBe(1)
  expect(result.input_revision).toBe(0)
 })
 it('settings require recalculation but preserve all image reviews',()=>{
  const p=testProject(),next=editProject(p,d=>{d.settings.control_group='treated'})
  expect(next.rois.map(r=>r.reviewed_revision)).toEqual([1,1,1,1])
  expect(retainResult(p,next,{project_id:p.id,input_revision:0} as any)).toBeNull()
 })
 it('reference edits invalidate dependent target and leave the other lane approved',()=>{
  const p=testProject(),next=editProject(p,d=>{d.rois[1].rect=[11,60,31,70]})
  expect(next.rois.map(r=>r.reviewed_revision)).toEqual([null,null,1,1])
 })
 it('sample edits only require review of the affected lane',()=>{
  const p=testProject(),next=editProject(p,d=>{d.samples[0].bio_id='B3'})
  expect(next.rois.map(r=>r.reviewed_revision)).toEqual([null,null,1,1])
 })
 it('image calibration edits invalidate all dependent ROIs',()=>{
  const p=testProject(),next=editProject(p,d=>{d.images[0].ceiling=65535})
  expect(next.rois.every(r=>r.reviewed_revision===null)).toBe(true)
 })
 it('undo does not resurrect invalid approval, but preserves unaffected lanes',()=>{
  const p=testProject(),next=editProject(p,d=>{d.rois[0].rect=[11,20,31,30]})
  const undo=restoreHistory(next,p)
  expect(undo.rois.map(r=>r.reviewed_revision)).toEqual([null,2,2,2])
 })
 it('never promotes a stale or foreign result on rename',()=>{
  const p=testProject(),next=editProject(p,d=>{d.name='new'})
  expect(retainResult(p,next,{project_id:'other',input_revision:0} as any)).toBeNull()
  expect(retainResult(p,next,{project_id:p.id,input_revision:8} as any)).toBeNull()
 })
})
