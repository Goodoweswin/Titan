// @vitest-environment jsdom
import React,{act,useState} from 'react'
import {createRoot} from 'react-dom/client'
import {afterEach,beforeEach,expect,it} from 'vitest'
import {ActionMenuProvider,useActionMenu} from '../../src/ActionMenu'

;(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
let host:HTMLDivElement,root:ReturnType<typeof createRoot>
function Harness({hidden=false}:{hidden?:boolean}){
 const {openMenu}=useActionMenu(),[chosen,setChosen]=useState('none')
 return React.createElement(React.Fragment,null,
  ...(!hidden?['one','two'].map(owner=>React.createElement('button',{key:owner,id:owner,
   onContextMenu:(event:React.MouseEvent<HTMLButtonElement>)=>{
    event.preventDefault();openMenu({origin:event.currentTarget,position:{x:20,y:20},label:owner,
     items:[{id:'first',label:'打开',onSelect:()=>setChosen(owner+':first')},
      {id:'disabled',label:'不可用',disabled:true,onSelect:()=>setChosen('invalid')},
      {id:'last',label:'管理',onSelect:()=>setChosen(owner+':last')}]
    })
   }},owner)):[]),React.createElement('output',null,chosen))
}
async function render(hidden=false){await act(async()=>root.render(React.createElement(ActionMenuProvider,null,React.createElement(Harness,{hidden}))))}
async function open(owner='one'){await act(async()=>document.getElementById(owner)!.dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,button:2})))}
async function key(value:string){await act(async()=>document.activeElement!.dispatchEvent(new KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true})))}
const menu=()=>document.querySelector('[role=menu]')
const output=()=>host.querySelector('output')!.textContent
beforeEach(async()=>{host=document.createElement('div');document.body.append(host);root=createRoot(host);await render()})
afterEach(async()=>{await act(async()=>root.unmount());host.remove()})

it('opening and cancelling never execute an action and restore trigger focus',async()=>{
 await open();expect(menu()).not.toBeNull();expect(output()).toBe('none')
 await key('Escape');expect(menu()).toBeNull();expect(output()).toBe('none');expect(document.activeElement?.id).toBe('one')
 await open();await act(async()=>document.body.dispatchEvent(new MouseEvent('pointerdown',{bubbles:true})))
 expect(menu()).toBeNull();expect(output()).toBe('none')
})

it('keyboard navigation skips disabled actions and invokes the chosen action once',async()=>{
 await open();expect(document.activeElement?.textContent).toBe('打开')
 await key('ArrowDown');expect(document.activeElement?.textContent).toBe('管理')
 await key('Enter');expect(output()).toBe('one:last');expect(menu()).toBeNull();expect(document.activeElement?.id).toBe('one')
})

it('a second context menu replaces the target instead of running an old action',async()=>{
 await open();await open('two');expect(document.querySelectorAll('[role=menu]')).toHaveLength(1)
 expect(menu()?.getAttribute('aria-label')).toBe('two')
 await key('Enter');expect(output()).toBe('two:first')
})

it('removing the trigger invalidates its open menu',async()=>{
 await open();await render(true);expect(menu()).toBeNull();expect(output()).toBe('none')
})

it('outside scrolling window resizing and window blur dismiss without edits',async()=>{
 for(const [target,type] of [[document,'scroll'],[window,'resize'],[window,'blur']] as const){
  await open();await act(async()=>target.dispatchEvent(new Event(type)))
  expect(menu()).toBeNull();expect(output()).toBe('none')
 }
})
