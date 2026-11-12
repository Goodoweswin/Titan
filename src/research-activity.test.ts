import {describe,it,expect} from 'vitest'
import {testProject} from './test-project'
import type {AnalysisResult,Project} from './types'
import {activityCalendar,activitySummary,newActivity,parseActivity,recordAnalysis} from './research-activity'

const date=(day:number)=>new Date(2026,10,day,12)
function resultFor(project:Project):AnalysisResult {
 return {project_id:project.id,input_revision:project.revision,measurements:project.rois.map(roi=>({...roi,area_px:200,raw_sum:1000,background_mean:2,corrected_sum:600,clipped_fraction:0,flags:[]})),normalized:[],biological:[],statistics:[]}
}
describe('local research activity',()=>{
 it('deduplicates repeat calculations, revisions and copies of a scientific project',()=>{
  const project=testProject(),result=resultFor(project)
  const first=recordAnalysis(newActivity(date(10)),project,result,date(10))
  expect(activitySummary(first,date(10))).toMatchObject({images:1,bands:4,days:1,streak:1})
  expect(recordAnalysis(first,project,result,date(11))).toBe(first)
  const copy={...project,project_path:'/copy.titanwb',revision:1}
  expect(recordAnalysis(first,copy,resultFor(copy),date(11))).toBe(first)
  copy.rois=[...copy.rois,{...copy.rois[0],id:'new-roi'}]
  const second=recordAnalysis(first,copy,resultFor(copy),date(11))
  expect(activitySummary(second,date(12))).toMatchObject({images:1,bands:5,days:2,streak:2,monthBands:5})
  expect(activitySummary(second,date(13)).streak).toBe(0)
 })
 it('ignores stale results, synthetic examples and failed measurements',()=>{
  const project=testProject(),result=resultFor(project),empty=newActivity(date(10))
  expect(recordAnalysis(empty,project,{...result,input_revision:99})).toBe(empty)
  expect(recordAnalysis(empty,project,{...result,project_id:'other'})).toBe(empty)
  expect(recordAnalysis(empty,Object.assign({...project},{synthetic:true}),result)).toBe(empty)
  expect(recordAnalysis(empty,Object.assign({...project},{demo:true}),result)).toBe(empty)
  result.measurements=result.measurements.map(row=>({...row,corrected_sum:NaN}))
  expect(recordAnalysis(empty,project,result)).toBe(empty)
 })
 it('counts multi-page images separately and does not infer historical activity',()=>{
  const project=testProject();project.images.push({...project.images[0],id:'page2',page_index:1})
  project.rois.push({...project.rois[0],id:'page2-roi',image_id:'page2'})
  const ledger=recordAnalysis(newActivity(date(10)),project,resultFor(project),date(10))
  expect(activitySummary(ledger,date(10)).images).toBe(2)
  const calendar=activityCalendar(ledger,'bands',date(12))
  expect(calendar).toHaveLength(140)
  expect(calendar.find(cell=>cell.day==='2026-11-10')?.count).toBe(5)
  expect(calendar.find(cell=>cell.day==='2026-11-09')?.untracked).toBe(true)
  expect(calendar.find(cell=>cell.day==='2026-11-13')?.future).toBe(true)
 })
 it('rejects malformed persisted history instead of treating it as zero',()=>{
  const activity=newActivity(date(10))
  expect(parseActivity(JSON.stringify(activity))).toEqual(activity)
  expect(()=>parseActivity('{bad')).toThrow()
  expect(()=>parseActivity(JSON.stringify({...activity,version:2}))).toThrow()
  expect(()=>parseActivity(JSON.stringify({...activity,bands:{a:42}}))).toThrow()
  expect(()=>parseActivity(JSON.stringify({...activity,images:[]}))).toThrow()
 })
})
