import {it,expect} from 'vitest'
import {testProject} from './test-project'
import {acceptLaneLayout,createBandSet,alignLaneLayout,acceptBandAssignments,copyLaneLayout,linkReferenceSet,applyPreparedDraft} from './lane-workflow'
import type {LaneProposal} from './types'
it('uses explicit candidate identity, never the filtered candidate index',()=>{
 const p=testProject()
 const proposal:LaneProposal={project_id:p.id,input_revision:p.revision,image_id:'im',window:[0,0,100,100],columns:[{proposal_id:'a',rect:[0,0,30,100],confidence:'high',reasons:[]},{proposal_id:'b',rect:[50,0,80,100],confidence:'high',reasons:[]}],expected_count:2,requires_review:false}
 const id=acceptLaneLayout(p,proposal,{b:'L2'})
 expect(p.lane_layouts.find(l=>l.id===id)?.columns.map(c=>c.lane_id)).toEqual(['L2'])
 expect(p.lanes.map(l=>l.sample_id)).toEqual(['S1','S2'])
})
it('prepared measurements preserve a save completed while proposals were open',()=>{
 const p=testProject(),draft=structuredClone(p)
 p.project_path='/saved.titanwb';p.saved_revision=p.revision;p.images[0].path='/saved.titanwb/originals/im.tif'
 applyPreparedDraft(p,draft,draft.revision)
 expect(p.project_path).toBe('/saved.titanwb');expect(p.images[0].path).toBe('/saved.titanwb/originals/im.tif')
})
it('copies lane positions to a crop without copying source-image exclusion rectangles',()=>{
 const p=testProject();p.images.push({...p.images[0],id:'crop',height:20})
 p.lane_layouts.push({id:'source',image_id:'im',membrane_id:'M1',window:[0,0,100,100],columns:[{lane_id:'L1',rect:[10,0,30,100]}],excluded_regions:[[0,90,100,100]],source_layout_id:null,confirmed_revision:0})
 const id=copyLaneLayout(p,'source','crop'),layout=p.lane_layouts.find(l=>l.id===id)!
 expect(layout.columns[0].rect).toEqual([10,0,30,20]);expect(layout.excluded_regions).toEqual([])
})
it('keeps empty lane slots and reuses reference identity for another target image',()=>{
 const p=testProject();p.rois=[]
 const proposal:LaneProposal={project_id:p.id,input_revision:p.revision,image_id:'im',window:[0,0,100,100],columns:[{proposal_id:'a',rect:[0,0,30,100],confidence:'high',reasons:[]},{proposal_id:'b',rect:[50,0,80,100],confidence:'high',reasons:[]}],expected_count:2,requires_review:false}
 const layout=acceptLaneLayout(p,proposal,{a:'L1',b:'L2'})
 const ref=createBandSet(p,layout,'ACTIN','reference')
 acceptBandAssignments(p,ref,[{lane_id:'L1',rect:[0,10,30,20],backgrounds:[[0,2,30,5]]},{lane_id:'L2',status:'not_detected'}])
 const other=copyLaneLayout(p,layout,'im')
 const target=createBandSet(p,other,'AKT','target',ref)
 acceptBandAssignments(p,target,[{lane_id:'L1',rect:[0,40,30,50],backgrounds:[[0,32,30,35]]},{lane_id:'L2',status:'not_detected'}])
 linkReferenceSet(p,target,ref)
 const t=p.rois.find(r=>r.role==='target')!,r=p.rois.find(r=>r.role==='reference')!
 expect(t.reference_id).toBe(r.id)
 expect(p.band_sets.find(g=>g.id===target)?.assignments[1]).toMatchObject({lane_id:'L2',roi_id:null,status:'not_detected'})
 const before=structuredClone(p)
 expect(()=>createBandSet(p,other,'AKT','target',ref)).toThrow(/已有/)
 expect(p).toEqual(before)
 expect(()=>alignLaneLayout(p,other,{dx:200,dy:0,scaleX:1,anchorX:0})).toThrow()
 expect(p).toEqual(before)
})
