import {describe,it,expect} from 'vitest'
import {testProject} from './test-project'
import type {AnalysisResult,Project} from './types'
import {activityCalendar,activityWeeks,activityTotals,activitySummary,localDay,newActivity,parseActivity,recordAnalysis} from './research-activity'

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
  expect(calendar).toHaveLength(364)
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

// Hand-checked Monday windows: current week 2026-12-28 → 2027-01-03,
// rolling 52-week window starts 2026-01-05.
describe('activity period views',()=>{
 const now=new Date(2027,0,1,0,30)
 it('keeps 52 local Monday weeks across a year and marks unmeasured days',()=>{
  const ledger={...newActivity(new Date(2026,11,30,23,30)),images:{a:'2026-12-30',b:'2027-01-01'},bands:{}}
  const cells=activityCalendar(ledger,'images',now)
  expect(cells).toHaveLength(364)
  expect(cells[0]).toMatchObject({day:'2026-01-05',count:null,untracked:true})
  expect(cells.at(-1)).toMatchObject({day:'2027-01-03',count:null,future:true})
  expect(cells.find(cell=>cell.day==='2026-12-31')).toMatchObject({count:0,untracked:false,future:false})
  expect(cells.find(cell=>cell.day==='2027-01-01')?.count).toBe(1)
  expect(localDay(now)).toBe('2027-01-01')
 })
 it('sums each week once and exposes partial start/current weeks',()=>{
  const ledger={...newActivity(new Date(2026,11,23,12)),images:{a:'2026-12-23',b:'2026-12-27',c:'2026-12-28',d:'2027-01-01'},bands:{a:'2027-01-01',b:'2027-01-01'}}
  const weeks=activityWeeks(ledger,'images',now)
  expect(weeks).toHaveLength(52)
  expect(weeks[0]).toMatchObject({start:'2026-01-05',end:'2026-01-11',count:null,trackedDays:0,untracked:true})
  expect(weeks.at(-2)).toMatchObject({start:'2026-12-21',end:'2026-12-27',count:2,trackedDays:5,partial:true})
  expect(weeks.at(-1)).toMatchObject({start:'2026-12-28',end:'2027-01-03',through:'2027-01-01',count:2,trackedDays:5,partial:true})
  expect(activityWeeks(ledger,'bands',now).at(-1)?.count).toBe(2)
 })
 it('distinguishes an empty first tracking day from untracked history',()=>{
  const ledger=newActivity(now),weeks=activityWeeks(ledger,'images',now)
  expect(weeks.at(-1)).toMatchObject({count:0,trackedDays:1,partial:true,untracked:false})
  expect(weeks.at(-2)?.count).toBeNull()
  expect(activityTotals(ledger,'images',now)).toEqual({count:0,activeDays:0,start:'2027-01-01',through:'2027-01-01'})
 })
 it('keeps lifetime totals outside the visible calendar and selects metric active days',()=>{
  const ledger={...newActivity(new Date(2024,0,1,12)),images:{old:'2024-01-01',a:'2026-12-30',b:'2026-12-30'},bands:{a:'2026-12-30',b:'2027-01-01'}}
  expect(activityTotals(ledger,'images',now)).toEqual({count:3,activeDays:2,start:'2024-01-01',through:'2027-01-01'})
  expect(activityTotals(ledger,'bands',now).activeDays).toBe(2)
  expect(activityCalendar(ledger,'images',now).reduce((sum,cell)=>sum+(cell.count??0),0)).toBe(2)
 })
 it('uses local calendar days rather than UTC dates around midnight and DST',()=>{
  const now=new Date(2026,2,9,0,15)
  const ledger=newActivity(new Date(2026,2,8,23,45))
  const cells=activityCalendar(ledger,'images',now)
  expect(cells[0].day).toBe('2025-03-17')
  expect(cells.at(-7)).toMatchObject({day:'2026-03-09',count:0,untracked:false})
  expect(activityTotals(ledger,'images',now).start).toBe('2026-03-08')
 })
})
