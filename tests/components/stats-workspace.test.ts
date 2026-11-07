// @vitest-environment jsdom
import React,{act} from 'react'
import {createRoot} from 'react-dom/client'
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {execFileSync} from 'node:child_process'
import {mkdtempSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import StatsWorkspace,{type StatsLibraryActions} from '../../src/stats/StatsWorkspace'
const python=path.resolve(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python')
let folder=''
vi.mock('../../src/bridge',()=>({callEngine:vi.fn()}))
import {callEngine} from '../../src/bridge'
import type {DatasetSource} from '../../src/stats/types'
import type {LibraryEntry} from '../../src/types'
vi.mock('@tauri-apps/plugin-dialog',()=>({open:vi.fn(),save:vi.fn()}))
;(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true
if(!HTMLDialogElement.prototype.showModal)HTMLDialogElement.prototype.showModal=function(){this.open=true}

let actions:StatsLibraryActions
let host:HTMLDivElement,root:ReturnType<typeof createRoot>
const click=async(label:string)=>{const btn=[...host.querySelectorAll('button')].find(b=>b.textContent===label);expect(btn, label).toBeTruthy();await act(async()=>{btn!.click()})}
const input=async(label:string,value:string)=>{const el=host.querySelector(`[aria-label="${label}"]`) as HTMLInputElement;expect(el,label).toBeTruthy();await act(async()=>{Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype,'value')!.set!.call(el,value);el.dispatchEvent(new Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}))})}
beforeEach(()=>{folder=mkdtempSync(path.join(tmpdir(),'titan-stats-component-'));host=document.createElement('div');document.body.append(host);root=createRoot(host);vi.mocked(callEngine).mockImplementation(async(command,payload={})=>{const output=execFileSync(python,[path.resolve('backend/entry.py')],{input:JSON.stringify({command,payload,session:{pid:process.pid,token:'component',library_root:folder}}),encoding:'utf8',maxBuffer:20*1024*1024});const result=JSON.parse(output);if(!result.ok)throw new Error(result.error);return result.data})})
afterEach(async()=>{await act(async()=>root.unmount());host.remove();rmSync(folder,{recursive:true,force:true});vi.clearAllMocks()})
async function mount(entries:LibraryEntry[]=[],onSource:(source:DatasetSource)=>void=()=>{},requestSource=false){
 await act(async()=>root.render(React.createElement(StatsWorkspace,{
  active:true,libraryBusy:false,onSource,registerClose:()=>{},sourceRequest:requestSource?{request:1,forceNew:true}:undefined,
  registerLibrary:value=>{actions=value},
  library:{entries,projects:[],error:'',refresh:vi.fn(),remember:vi.fn(),resume:vi.fn(),change:vi.fn()},
  sidebarSlot:null,reportView:vi.fn(),membership:null,beforeSourceImport:async()=>()=>{},onSourceCreated:vi.fn(),onExported:vi.fn(),
 })))
}
it('runs the real engine from table import through inference, stale detection, frozen figure and reload',async()=>{
 await mount();await act(async()=>{await actions.create({name:'独立统计'})});await click('导入 / 粘贴')
 await input('粘贴统计数据','Control\tTreatment A\tTreatment B\n1\t2\t4\n2\t3\t5\n3\t4\t6')
 await click('预览粘贴数据');expect(host.textContent).toContain('3 行 / Control、Treatment A、Treatment B')
 await click('添加数据表');await click('设置统计分析');await input('统计方法','anova');await input('统计比较范围','all')
 const checkbox=host.querySelector('[aria-label="确认独立单位"]') as HTMLInputElement
 await act(async()=>checkbox.click());await click('运行分析');expect(host.textContent).toContain('总体检验：F = 7，P = 0.027')
 await click('查看图形');await input('统计标注','p');await input('宽度 mm','60');await input('高度 mm','50')
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,600))})
 expect(host.querySelector('img[alt="统计图预览"]')).toBeTruthy();await click('保存图形快照');await click('保存')
 await click('数据表');await input('数值 1 1','17');await click('统计分析');expect(host.textContent).toContain('数据或设置已改变')
 await click('保存');const entries=await callEngine<any[]>('library_list');expect(entries[0].module).toBe('stats')
 const saved=await callEngine<any>('stats_open',{path:entries[0].path});expect(saved.figures).toHaveLength(1);expect(saved.figures[0].dataset.rows[0].values[saved.figures[0].dataset.groups[0].id]).toBe('1')
 await act(async()=>{await actions.open(entries[0].path,{view:'figure',artifact_id:'stats:'+saved.figures[0].id})})
 expect(host.textContent).toContain('导入数据 · 图 1')
},120000)

it('reads saved IF sample results, detects source changes and preserves frozen figures on refresh',async()=>{
 const sourcePath=execFileSync(python,['-c',`
import json,sys
from titan_if.service import _demo
from titan_if.analysis import measure_field
from titan_if.projects import save_project
s=json.loads(sys.argv[1]);p=_demo(s)
for f in p['fields']:f['result']=measure_field(f)
p['revision']+=1;p=save_project(p,p['project_path'],p['saved_revision'],s)
print(p['project_path'])`,JSON.stringify({pid:process.pid,token:'component',library_root:folder})],{encoding:'utf8',env:{...process.env,PYTHONPATH:path.resolve('backend'),PYTHONUTF8:'1'}}).trim()
 const onSource=vi.fn()
 await mount(await callEngine<LibraryEntry[]>('library_list'),onSource,true)
 await input('结果来源项目',sourcePath)
 expect(host.textContent).toContain('control: n=3 · treated: n=3')
 const select=host.querySelector('[aria-label="选择指标 Marker · 原始平均强度 · synthetic"]') as HTMLInputElement
 await act(async()=>select.click())
 expect(button('读取所选结果').disabled).toBe(true)
 await act(async()=>(host.querySelector('[aria-label="确认来源统计单位"]') as HTMLInputElement).click())
 await click('读取所选结果')
 expect(host.textContent).toContain('IF 来源：')
 expect((host.querySelector('[aria-label="数值 1 1"]') as HTMLInputElement).disabled).toBe(true)
 await click('统计分析');await click('运行分析');await click('查看图形')
 await act(async()=>{await new Promise(resolve=>setTimeout(resolve,600))})
 expect(host.querySelector('img[alt="统计图预览"]')).toBeTruthy()
 await click('保存图形快照');await click('保存')
 const entries=await callEngine<any[]>('library_list'),statsPath=entries.find(e=>e.module==='stats').path
 const before=await callEngine<any>('stats_open',{path:statsPath})
 const source=await callEngine<any>('if_open',{path:sourcePath});source.fields[0].bio_id='new-sample-id';source.revision++
 await callEngine('if_save',{project:source,expected_revision:source.saved_revision})
 await click('检查来源更新');expect(host.textContent).toContain('来源已变化')
 await click('用当前 IF 更新');await click('统计分析')
 expect(host.textContent).toContain('数据或设置已改变')
 const after=await callEngine<any>('stats_open',{path:statsPath})
 expect(after.figures).toEqual(before.figures)
 expect(after.datasets[0].rows[0].label).toBe('new-sample-id')
 await click('返回 IF');expect(onSource).toHaveBeenCalledWith(expect.objectContaining({path:sourcePath,kind:'if',entry_id:expect.any(String)}))
 function button(label:string){return [...host.querySelectorAll('button')].find(b=>b.textContent===label)!}
},120000)
