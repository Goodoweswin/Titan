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
afterEach(()=>{act(()=>root.unmount());container.remove();vi.restoreAllMocks();vi.useRealTimers()})
const props=()=>({entries:[] as LibraryEntry[],libraryError:'',activity:newActivity(),activityError:'',opening:false,onBack:vi.fn(),onOpen:vi.fn(),onRetry:vi.fn()})

it('shows an honest guest state and login preparation without collecting credentials',()=>{
 const input=props();act(()=>root.render(createElement(AccountPage,input)))
 expect(document.activeElement).toBe(container.querySelector('h1'))
 expect(container.textContent).toContain('本地研究者')
 expect(container.textContent).toContain('登录后显示邮箱')
 expect(container.querySelectorAll('input')).toHaveLength(0)
 const button=Array.from(container.querySelectorAll('button')).find(button=>button.textContent==='登录账户')!
 expect(container.querySelector<HTMLElement>('#account-login-info')!.hidden).toBe(true)
 act(()=>button.click())
 expect(container.querySelector<HTMLElement>('#account-login-info')!.hidden).toBe(false)
 expect(container.querySelector('#account-login-info')!.textContent).toContain('登录服务尚未开放')
 expect(container.querySelectorAll('.account-calendar [role=listitem]')).toHaveLength(364)
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

it('switches daily, weekly and lifetime views while preserving selected metric',()=>{
 vi.useFakeTimers();vi.setSystemTime(new Date(2027,0,1,12))
 const input=props();input.activity={...newActivity(new Date(2024,0,1,12)),images:{old:'2024-01-01',current:'2027-01-01'},bands:{a:'2027-01-01',b:'2027-01-01',c:'2027-01-01'}}
 act(()=>root.render(createElement(AccountPage,input)))
 const click=(label:string)=>act(()=>Array.from(container.querySelectorAll('button')).find(button=>button.textContent===label)!.click())
 expect(container.querySelectorAll('.account-calendar [role=listitem]')).toHaveLength(364)
 click('条带数');click('每周')
 expect(container.querySelectorAll('.account-calendar [role=listitem]')).toHaveLength(52)
 expect(container.querySelector('.account-calendar [role=listitem]:last-child')?.getAttribute('aria-label')).toContain('3 条新增条带')
 expect(container.textContent).toContain('每格一周')
 click('累计总量')
 expect(container.querySelector('.account-activity-total')?.textContent).toContain('3条')
 expect(container.textContent).toContain('1 天有新增条带')
 click('图像数')
 expect(container.querySelector('.account-activity-total')?.textContent).toContain('2张')
 click('每日')
 expect(container.querySelector('.account-calendar [role=listitem]:last-child')?.getAttribute('aria-label')).toContain('尚未到来')
 vi.useRealTimers()
})

// Administrator approval never means that an email has been verified.
it.each([false,true])('shows email verification badge only for actual verified=%s',emailVerified=>{
 const input=props()
 act(()=>root.render(createElement(AccountPage,{...input,profile:{name:'Managed User',email:'managed@example.org',createdAt:'2026-11-12',emailVerified,administratorApproved:true} as any})))
 expect(container.textContent).toContain('Managed User')
 expect(container.querySelector('[aria-label="邮箱已验证"]')!==null).toBe(emailVerified)
})
