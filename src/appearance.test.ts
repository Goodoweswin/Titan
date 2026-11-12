// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,createElement} from 'react'
import {createRoot,type Root} from 'react-dom/client'
import {readInterfaceColor,saveInterfaceColor} from './appearance'
import SettingsDialog from './SettingsDialog'

let root:Root|undefined
beforeEach(()=>{
 localStorage.clear()
 document.documentElement.removeAttribute('data-interface-color')
 Object.assign(globalThis,{IS_REACT_ACT_ENVIRONMENT:true})
})
afterEach(()=>{if(root)act(()=>root!.unmount());root=undefined;document.body.innerHTML='';vi.restoreAllMocks()})

it('restores a known color and rejects stale or invalid preferences',()=>{
 expect(readInterfaceColor()).toBe('neutral')
 expect(saveInterfaceColor('green')).toBe(true)
 expect(document.documentElement.dataset.interfaceColor).toBe('green')
 expect(readInterfaceColor()).toBe('green')
 localStorage.setItem('titan-interface-color','obsolete')
 expect(readInterfaceColor()).toBe('neutral')
})

it('still applies a session color when storage is unavailable',()=>{
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('Unavailable')})
 expect(saveInterfaceColor('rose')).toBe(false)
 expect(document.documentElement.dataset.interfaceColor).toBe('rose')
 vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new Error('Unavailable')})
 expect(readInterfaceColor()).toBe('neutral')
})

it('offers color and size controls, resets both, and closes via the dialog lifecycle',()=>{
 // jsdom does not implement the native modal lifecycle; browser focus/Escape
 // behavior is covered by tests/browser/settings.spec.ts.
 HTMLDialogElement.prototype.showModal=function(){this.open=true}
 HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new Event('close'))}
 const container=document.createElement('div');document.body.append(container);root=createRoot(container)
 const onColor=vi.fn(),onTextSize=vi.fn(),onClose=vi.fn()
 act(()=>root!.render(createElement(SettingsDialog,{color:'blue',onColor,textSize:'standard',onTextSize,persisted:false,onClose})))
 expect(container.querySelector('dialog')!.open).toBe(true)
 expect(container.querySelectorAll('input[type=radio]')).toHaveLength(5)
 expect(container.querySelector<HTMLInputElement>('input[value=blue]')!.checked).toBe(true)
 act(()=>container.querySelector<HTMLInputElement>('input[value=violet]')!.click())
 expect(onColor).toHaveBeenLastCalledWith('violet')
 act(()=>{const select=container.querySelector('select')!;select.value='large';select.dispatchEvent(new Event('change',{bubbles:true}))})
 expect(onTextSize).toHaveBeenLastCalledWith('large')
 expect(container.querySelector('[role=status]')!.textContent).toContain('无法保存')
 act(()=>Array.from(container.querySelectorAll('button')).find(button=>button.textContent==='恢复默认')!.click())
 expect(onColor).toHaveBeenLastCalledWith('neutral')
 expect(onTextSize).toHaveBeenLastCalledWith('standard')
 act(()=>container.querySelector<HTMLButtonElement>('[aria-label="关闭设置"]')!.click())
 expect(onClose).toHaveBeenCalledOnce()
})
