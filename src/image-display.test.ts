import {it,expect} from 'vitest'
import {displayStyle} from './image-display'
import {testProject} from './test-project'
import {editProject,retainResult} from './state'
it('only changes the display without invalidating measurements or review',()=>{
 const p=testProject(),result={project_id:p.id,input_revision:p.revision,measurements:[],normalized:[],biological:[],statistics:[]}
 const next=editProject(p,d=>{d.images[0].display_inverted=true})
 expect(next.rois.every(r=>r.reviewed_revision===next.revision)).toBe(true)
 expect(retainResult(p,next,result)?.input_revision).toBe(next.revision)
 expect(displayStyle(next.images[0])).toEqual({filter:'invert(1)'})
 expect(displayStyle(p.images[0])).toEqual({filter:'none'})
})
