// @vitest-environment jsdom
import {afterEach,beforeEach,it,expect,vi} from 'vitest'
import {act,createElement} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import AccountPage from './AccountPage'
import useResearchActivity from './useResearchActivity'
import {activityStorageKey,newActivity} from './research-activity'
import type {LibraryEntry} from './types'

let root:Root,container:HTMLDivElement
beforeEach(()=>{
 Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true})
 localStorage.clear();container=document.createElement('div');document.body.append(container);root=createRoot(container)
})
afterEach(()=>{act(()=>root.unmount());container.remove();vi.restoreAllMocks()})
const props=()=>({entries:[] as LibraryEntry[],libraryError:'',activity:newActivity(),activityError:'',opening:false,onBack:vi.fn(),onOpen:vi.fn(),onRetry:vi.fn()})

it('shows an honest guest state and login preparation without collecting credentials',()=>{
 const input=props();act(()=>root.render(createElement(AccountPage,input)))
 expect(document.activeElement).toBe(container.querySelector('h1'))
 expect(container.textContent).toContain('本地研究者')
 expect(container.textContent).toContain('登录后显示邮箱')
 expect(container.querySelectorAll('input')).toHaveLength(0)
 const button=Array.from(container.querySelectorAll('button')).find(button=>button.textContent==='登录 / 注册')!
 expect(container.querySelector<HTMLElement>('#account-login-info')!.hidden).toBe(true)
 act(()=>button.click())
 expect(container.querySelector<HTMLElement>('#account-login-info')!.hidden).toBe(false)
 expect(container.querySelector('#account-login-info')!.textContent).toContain('登录服务尚未开放')
 expect(container.querySelectorAll('.account-calendar [role=listitem]')).toHaveLength(140)
 expect(container.querySelectorAll('.account-metrics dd')).toHaveLength(5)
})

it('opens actual project entries and distinguishes unavailable statistics from zero',()=>{
 const input=props(),entry:LibraryEntry={entry_id:'one',project_id:'p',name:'实际实验',path:'/example.titanwb',last_opened:'2026-11-12',created_at:'2026-11-10',available:true,figures:[]}
 input.entries=[entry]
 act(()=>root.render(createElement(AccountPage,input)))
 act(()=>container.querySelector<HTMLButtonElement>('.account-project')!.click())
 expect(input.onOpen).toHaveBeenCalledWith(entry)
 act(()=>root.render(createElement(AccountPage,{...input,libraryError:'unavailable',activity:null,activityError:'记录无法读取'})))
 expect(container.querySelectorAll('.account-metrics dd')[0].textContent).toBe('—')
 expect(container.querySelectorAll('.account-metrics dd')[1].textContent).toBe('—')
 expect(container.textContent).toContain('记录无法读取')
 act(()=>Array.from(container.querySelectorAll('button')).find(button=>button.textContent==='重试')!.click())
 expect(input.onRetry).toHaveBeenCalledOnce()
})

it('preserves corrupt activity storage and exposes an error',()=>{
 localStorage.setItem(activityStorageKey,'{broken')
 function Probe(){const state=useResearchActivity(null,null);return createElement('div',null,state.error)}
 act(()=>root.render(createElement(Probe)))
 expect(container.textContent).toContain('暂不可用')
 expect(localStorage.getItem(activityStorageKey)).toBe('{broken')
})
