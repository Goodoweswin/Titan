import {it,expect} from 'vitest'
import {testProject} from './test-project'
import {editProject,retainResult} from './state'
import {defaultFigureSettings,defaultPlotSettings} from './figure-settings'
it('publication colors axes and sizes are display metadata preserving approved results',()=>{
 const p=testProject(),result={project_id:p.id,input_revision:p.revision,measurements:[],normalized:[],biological:[],statistics:[]}
 const next=editProject(p,d=>{d.figure_settings={...defaultFigureSettings(),colors:{control:'#F1D21B'},y_max:4};d.plot_settings={...defaultPlotSettings,font_size:14}})
 expect(next.rois.every(r=>r.reviewed_revision===next.revision)).toBe(true)
 expect(retainResult(p,next,result)?.input_revision).toBe(next.revision)
 expect(p.figure_settings).toBeUndefined()
})
it('default figure maps and lists are independent drafts',()=>{
 const a=defaultFigureSettings(),b=defaultFigureSettings();a.colors.A='#112233';a.group_order.push('A')
 expect(b.colors).toEqual({});expect(b.group_order).toEqual([])
})
