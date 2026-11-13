// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import ProjectLibrary from '../../src/ProjectLibrary'
import {ActionMenuProvider,useActionMenu} from '../../src/ActionMenu'
import type {LibraryEntry} from '../../src/types'

;(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
let host:HTMLDivElement,root:Root
const opened=vi.fn()
const entry:LibraryEntry={entry_id:'analysis',project_id:'project',name:'Analysis',path:'/synthetic/analysis',last_opened:'before',created_at:'before',available:true,figures:[],resume:{view:'workspace'}}
function CellTrigger(){
 const {openMenu}=useActionMenu()
 return React.createElement('button',{id:'cell',onClick:(event:React.MouseEvent<HTMLButtonElement>)=>openMenu({id:'cell:stats:row:group',label:'Cell actions',origin:event.currentTarget,position:{x:10,y:10},items:[{id:'exclude',label:'Exclude',onSelect:()=>{}}]})},'Cell')
}
async function render(value=entry){await act(async()=>root.render(React.createElement(ActionMenuProvider,null,
 React.createElement(CellTrigger),React.createElement(ProjectLibrary,{entries:[value],projects:[],activeFigure:'',error:'',onProject:()=>{},onOpenBundle:()=>{},onOpen:opened,onRelocate:()=>{},onRetry:()=>{},onDialog:()=>{},onOpenFile:()=>{},onPin:()=>{},onArtifact:()=>{},onReveal:()=>{}}))))}
async function click(selector:string){await act(async()=>(host.querySelector(selector) as HTMLButtonElement).click())}
const menu=()=>document.querySelector('[role=menu]')
beforeEach(async()=>{opened.mockClear();host=document.createElement('div');document.body.append(host);root=createRoot(host);await render()})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})

it('keeps a library menu through resume metadata refresh and opens the latest resume',async()=>{
 await click('[aria-label="分析菜单 Analysis"]');expect(menu()).not.toBeNull()
 const refreshed={...entry,last_opened:'after',resume:{view:'results' as const}}
 await render(refreshed);expect(menu()).not.toBeNull()
 await act(async()=>(menu()!.querySelector('[data-action-id="open"]') as HTMLButtonElement).click())
 expect(opened).toHaveBeenCalledWith(refreshed)
})
it('does not dismiss a statistics cell menu when unrelated library entries refresh',async()=>{
 await click('#cell');await render({...entry,name:'Renamed analysis'})
 expect(menu()?.getAttribute('aria-label')).toBe('Cell actions')
})
it('still invalidates a library menu when its target changes',async()=>{
 await click('[aria-label="分析菜单 Analysis"]')
 await render({...entry,name:'Renamed analysis'})
 expect(menu()).toBeNull();expect(opened).not.toHaveBeenCalled()
})
