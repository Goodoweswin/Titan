import {describe,it,expect} from 'vitest'
import {createHistory,recordLocation,historyTarget,moveHistory,type WorkspaceLocation} from './workspace-navigation'

const home:WorkspaceLocation={kind:'home'}
const project:WorkspaceLocation={kind:'project',id:'p1'}
const analysis:WorkspaceLocation={kind:'analysis',module:'if',projectId:'a1',entryId:'entry1',path:'/a.titanif',view:'analysis',resourceId:'field1'}

describe('workspace browsing history',()=>{
 it('deduplicates a location while retaining updated titles and paths',()=>{
  let h=recordLocation(createHistory(home),analysis)
  h=recordLocation(h,{...analysis,name:'renamed',path:'/moved.titanif'})
  expect(h.entries).toHaveLength(2)
  expect(h.entries[1]).toMatchObject({path:'/moved.titanif',name:'renamed'})
 })
 it('records steps and resources without storing analysis data',()=>{
  let h=recordLocation(createHistory(home),analysis)
  h=recordLocation(h,{...analysis,view:'results'})
  h=recordLocation(h,{...analysis,resourceId:'field2'})
  expect(h.entries).toHaveLength(4)
  expect(historyTarget(h,-1)?.location).toMatchObject({view:'results',resourceId:'field1'})
  expect(historyTarget(h,1)).toBeNull()
 })
 it('keeps separately registered copies with the same project ID distinct',()=>{
  const copy={...analysis,entryId:'copy',path:'/copy.titanif'}
  const h=recordLocation(recordLocation(createHistory(home),analysis),copy)
  expect(h.entries).toHaveLength(3)
  expect(historyTarget(h,-1)?.location).toMatchObject({entryId:'entry1',path:'/a.titanif'})
 })
 it('adopts the first saved identity without adding a fake navigation step',()=>{
  const draft={...analysis,path:null,entryId:undefined}
  let h=recordLocation(recordLocation(createHistory(home),draft),{...draft,view:'results'})
  h=recordLocation(h,{...analysis,view:'results'})
  expect(h.entries).toHaveLength(3)
  expect(historyTarget(h,-1)?.location).toMatchObject({path:'/a.titanif',entryId:'entry1',view:'analysis'})
 })
 it('resolves empty-analysis visits to the first live resource without adding a data-import step',()=>{
  const empty={...analysis,resourceId:undefined}
  let h=recordLocation(recordLocation(createHistory(home),empty),{...empty,view:'results'})
  h=recordLocation(h,{...analysis,view:'results'})
  expect(h.entries).toHaveLength(3)
  expect(historyTarget(h,-1)?.location).toMatchObject({view:'analysis',resourceId:'field1'})
 })
 it('moves the cursor only after a completed navigation and truncates a new branch',()=>{
  const original=recordLocation(recordLocation(createHistory(home),project),analysis)
  const target=historyTarget(original,-1)!
  // Looking up a destination cannot commit a cancelled save/leave operation.
  expect(original.index).toBe(2)
  const back=moveHistory(original,target.index)
  expect(historyTarget(back,1)?.location).toEqual(analysis)
  const branched=recordLocation(back,{kind:'tool',tool:'stats'})
  expect(branched.entries).toEqual([home,project,{kind:'tool',tool:'stats'}])
  expect(historyTarget(branched,1)).toBeNull()
 })
})
