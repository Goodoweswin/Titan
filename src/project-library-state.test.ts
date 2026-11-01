import {it,expect} from 'vitest'
import {testProject} from './test-project'
import {editProject,mergeImported,acceptReview} from './state'
import {mergeSavedFrom,sameProjectContext} from './project-library-state'
it('a late save cannot retarget another copy with the same scientific ID',()=>{
 const base={...testProject(),project_path:'/A.titanwb'},other={...base,project_path:'/B.titanwb'}
 const saved={...base,saved_revision:base.revision}
 expect(mergeSavedFrom(other,base,saved)).toBe(other)
 expect(sameProjectContext(base,other)).toBe(false)
 const newer=editProject(base,p=>{p.name='newer'})
 const moved=mergeSavedFrom(newer,base,{...saved,project_path:'/C.titanwb'})!
 expect(moved.project_path).toBe('/C.titanwb');expect(moved.name).toBe('newer');expect(moved.saved_revision).toBe(0)
})
it('late imports and reviews cannot cross a same-ID copy switch',()=>{
 const base={...testProject(),project_path:'/A.titanwb'},other={...base,project_path:'/B.titanwb'}
 const imported={...base,images:[...base.images,{...base.images[0],id:'new'}]}
 expect(mergeImported(other,base,imported)).toBe(other)
 expect(acceptReview(other,base,base)).toBeNull()
})
