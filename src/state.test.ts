import {describe,it,expect} from 'vitest'
import {createProject,editProject,screenToImage,commitResult} from './state'
describe('project identity',()=>{
 it('starts at a clean independent revision',()=>{
  const a=createProject('实验一'), b=createProject('实验二')
  expect(a.revision).toBe(0);expect(a.schema_version).toBe(1)
  expect(a.id).not.toBe(b.id);expect(a.rois).toEqual([])
 })
 it('rejects an empty experiment name',()=>{expect(()=>createProject('  ')).toThrow()})
})
describe('edits and async revision boundaries',()=>{
 it('invalidates review on every analytical edit without mutating history',()=>{
  const p=createProject('a');p.rois=[{id:'r',reviewed_revision:0} as any]
  const q=editProject(p,x=>{x.name='b'})
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
