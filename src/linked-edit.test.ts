import {it,expect} from 'vitest'
import {testProject} from './test-project'
import {editProject} from './state'
import {batchROIs,numberLanes} from './workflow'
function linked(){
 const p=testProject()
 p.lane_layouts=[{id:'layout',image_id:'im',membrane_id:'M1',window:[0,0,100,100],columns:[{lane_id:'L1',rect:[0,0,40,100]},{lane_id:'L2',rect:[40,0,90,100]}],excluded_regions:[],source_layout_id:null,confirmed_revision:0}]
 p.band_sets=(['target','reference'] as const).map(role=>({id:role,layout_id:'layout',analyte:role==='target'?'PROTEIN':'ACTIN',role,window:[0,0,100,100],reference_set_id:role==='target'?'reference':null,assignments:['1','2'].map(n=>({lane_id:'L'+n,roi_id:role+n,status:'accepted' as const}))}))
 for(const r of p.rois){r.band_set_id=r.role;r.lane_layout_id='layout'}
 return p
}
it('deleting a linked reference leaves a recoverable pending slot and clears dependent links',()=>{
 const p=linked(),q=editProject(p,d=>{d.rois=d.rois.filter(r=>r.id!=='reference1')})
 expect(q.band_sets[1].assignments[0]).toEqual({lane_id:'L1',roi_id:null,status:'pending'})
 expect(q.rois.find(r=>r.id==='target1')!.reference_id).toBeNull()
 expect(p.rois).toHaveLength(4)
})
it('rejects manual changes to linked identity or denominator atomically',()=>{
 const p=linked()
 for(const mutate of [(d:typeof p)=>{d.rois[0].analyte='changed'},(d:typeof p)=>{d.rois[0].lane_id='L2'},(d:typeof p)=>{d.rois[0].reference_id='reference2'}])expect(()=>editProject(p,mutate)).toThrow(/集合|内参|参考/)
 expect(p.rois[0].analyte).toBe('PROTEIN')
 expect(()=>numberLanes(p,['target1'],3)).toThrow(/泳道|身份/)
})
it('manual geometry edits remain available and copies become independent annotations',()=>{
 const p=linked(),q=editProject(p,d=>{d.rois[0].rect=[11,20,30,30]})
 expect(q.rois[0].reviewed_revision).toBeNull()
 batchROIs(p,['target1'],{type:'copy'})
 expect(p.rois.at(-1)!.band_set_id).toBeUndefined()
 expect(p.rois.at(-1)!.lane_layout_id).toBeUndefined()
})
