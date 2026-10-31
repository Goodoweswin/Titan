import {describe,it,expect} from 'vitest'
import {testProject} from './test-project'
import * as workflow from './workflow'

describe('batch annotation transactions',()=>{
 it('moves ROIs and their backgrounds together in original pixels',()=>{
  const p=testProject();workflow.batchROIs(p,['target1','target2'],{type:'move',dx:2,dy:-1})
  expect(p.rois[0].rect).toEqual([12,19,32,29]);expect(p.rois[0].backgrounds).toEqual([[12,13,32,16]])
  expect(p.rois[2].rect).toEqual([52,19,72,29]);expect(p.rois[1].rect).toEqual([10,60,30,70])
 })
 it('rejects the entire batch if one ROI or background leaves the image',()=>{
  const p=testProject(),before=structuredClone(p)
  expect(()=>workflow.batchROIs(p,['target1','target2'],{type:'move',dx:40,dy:0})).toThrow()
  expect(p).toEqual(before)
 })
 it('copies a ROI to a fresh lane without falsely carrying reference or approval',()=>{
  const p=testProject();workflow.batchROIs(p,['target1'],{type:'copy'})
  const copy=p.rois.at(-1)!
  expect(copy.id).not.toBe('target1');expect(copy.lane_id).toBe('L3');expect(copy.reference_id).toBeNull();expect(copy.reviewed_revision).toBeNull()
  expect(p.samples.at(-1)?.bio_id).toBe('B3')
 })
 it('sets selected ROI sizes and clears backgrounds for deliberate review',()=>{
  const p=testProject();workflow.batchROIs(p,['target1','target2'],{type:'size',width:22,height:11})
  expect(p.rois[0].rect).toEqual([10,20,32,31]);expect(p.rois[2].rect).toEqual([50,20,72,31]);expect(p.rois[0].backgrounds).toEqual([])
 })
 it('generates local backgrounds only where they do not intersect any band',()=>{
  const p=testProject();p.rois[1].rect=[10,14,30,18]
  workflow.batchROIs(p,['target1'],{type:'background'})
  expect(p.rois[0].backgrounds).toEqual([[10,33,30,36]])
 })
 it('only fills unambiguous same-lane references and preserves explicit assignments',()=>{
  const p=testProject();p.rois[0].reference_id=null;p.rois[2].reference_id=null
  p.rois.push({...p.rois[3],id:'other',analyte:'TUBULIN'})
  expect(workflow.matchReferences(p)).toEqual({matched:1,ambiguous:1})
  expect(p.rois[0].reference_id).toBe('reference1');expect(p.rois[2].reference_id).toBeNull()
 })
 it('refuses read-only batch changes',()=>{
  const p=testProject();p.read_only=true
  expect(()=>workflow.batchROIs(p,['target1'],{type:'background'})).toThrow()
 })
})
describe('sample paste',()=>{
 it('accepts spreadsheet TSV including new shared sample IDs',()=>{
  const p=testProject()
  workflow.pasteSamples(p,'泳道\t样本ID\t生物学ID\t组别\t配对ID\t膜编号\nL1\tshared\tmouse-1\tdrug\t\tM2\nL2\tshared\tmouse-1\tdrug\t\tM2')
  expect(p.lanes.map(l=>l.sample_id)).toEqual(['shared','shared'])
  expect(p.samples.find(s=>s.id==='shared')).toMatchObject({bio_id:'mouse-1',group:'drug',pair_id:''})
 })
 it.each([
  'L1\tS1\tB1\tdrug\t\tM1\nL9\tS2\tB2\tdrug\t\tM1',
  'L1\tshared\tB1\tdrug\t\tM1\nL2\tshared\tB2\tdrug\t\tM1',
  'L1\tS1\t\tdrug\t\tM1',
  'L1\tS1\tB1\tdrug\t\tM1\nL1\tS1\tB1\tdrug\t\tM1',
 ])('rejects invalid rows without partial mutation: %s',text=>{
  const p=testProject(),before=structuredClone(p)
  expect(()=>workflow.pasteSamples(p,text)).toThrow();expect(p).toEqual(before)
 })
})
describe('quality navigation',()=>{
 it('identifies missing backgrounds/reference without duplicating stale result flags',()=>{
  const p=testProject();p.rois[0].backgrounds=[];p.rois[0].reference_id=null;p.rois[0].reviewed_revision=null
  const issues=workflow.projectIssues(p,null)
  expect(issues.filter(i=>i.roiId==='target1').map(i=>i.code)).toEqual(['missing_background','missing_reference','review_required'])
 })
 it('routes reference flags to the reference ROI',()=>{
  const p=testProject()
  const issues=workflow.projectIssues(p,{project_id:p.id,input_revision:0,measurements:[],normalized:[{id:'target1',flags:['reference:signal_clipped']}],biological:[],statistics:[]} as any)
  expect(issues.find(i=>i.code==='signal_clipped')?.roiId).toBe('reference1')
 })
})

describe('lane numbering',()=>{
 it('renumbers selected lanes in visual order and preserves reference links',()=>{
  const p=testProject();workflow.numberLanes(p,['target2','target1'],3)
  expect(p.lanes.map(l=>l.id)).toEqual(['L3','L4'])
  expect(p.rois.map(r=>r.lane_id)).toEqual(['L3','L3','L4','L4'])
  expect(p.rois[0].reference_id).toBe('reference1')
 })
 it('rejects collisions with unselected lanes without partial mutation',()=>{
  const p=testProject(),before=structuredClone(p)
  expect(()=>workflow.numberLanes(p,['target1'],2)).toThrow('冲突');expect(p).toEqual(before)
 })
})

describe('candidate creation after numbering and unambiguous provenance',()=>{
 it('allocates unused lane and sample identities after continuous numbering',()=>{
  const p=testProject();workflow.numberLanes(p,['target1','target2'],3)
  workflow.appendCandidates(p,'im',[[1,1,5,5],[10,1,15,5],[20,1,25,5]],'NEW','target')
  expect(p.lanes.map(l=>l.id)).toEqual(['L3','L4','L5'])
  expect(p.rois.at(-1)?.lane_id).toBe('L5')
 })
 it('treats plus signs in a real membrane name literally',()=>{
  const p=testProject();p.lanes[0].membrane_id='M1+M2'
  expect(workflow.sourceROIs(p,'S1','PROTEIN','M1+M2').map(r=>r.id)).toEqual(['target1'])
 })
 it('uses explicit merged block membership for source provenance',()=>{
  const p=testProject();p.lanes[1].sample_id='S1';p.lanes[1].membrane_id='M2'
  p.settings.normalization_mode='ibc';p.settings.analysis_blocks=[{id:'combined',membrane_ids:['M1','M2'],pooled_reference_id:'pool',merge_same_sample:true}]
  expect(workflow.sourceROIs(p,'S1','PROTEIN','combined').map(r=>r.id)).toEqual(['target1','target2'])
 })
})

describe('quality flag source routing',()=>{
 it('routes ordinary and nested IBC reference flags to the actual source',()=>{
  const p=testProject();p.settings.ibc_by_membrane={M1:{PROTEIN:'target2'}}
  expect(workflow.flagSource(p,'target1','reference:signal_clipped')).toEqual({roiId:'reference1',code:'signal_clipped'})
  expect(workflow.flagSource(p,'target1','ibc:reference:signal_clipped')).toEqual({roiId:'reference2',code:'signal_clipped'})
 })
})

it('excluding the first candidate preserves the second candidate lane mapping',()=>{
 const p=testProject()
 workflow.appendCandidates(p,'im',[[1,1,5,5],[50,1,55,5]],'NEW','target',[1])
 expect(p.rois.filter(r=>r.analyte==='NEW').map(r=>r.lane_id)).toEqual(['L2'])
})
