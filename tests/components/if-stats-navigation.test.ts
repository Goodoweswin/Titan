// @vitest-environment jsdom
import React, {act} from 'react'
import {createRoot} from 'react-dom/client'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import IFWorkspace from '../../src/if/IFWorkspace'
import {callEngine} from '../../src/bridge'
import type {IFProject} from '../../src/if/types'

vi.mock('../../src/bridge', () => ({callEngine: vi.fn()}))
vi.mock('@tauri-apps/plugin-dialog', () => ({open: vi.fn(), save: vi.fn()}))
;(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement, root: ReturnType<typeof createRoot>
let resolveSave: (project: IFProject) => void, rejectSave: (error: Error) => void
let saving: IFProject, onStats: ReturnType<typeof vi.fn>
const project = (id: string): IFProject => ({
  module: 'if', schema_version: 1, id, name: id, revision: 0, saved_revision: 0,
  project_path: `/test/${id}.titanif`, read_only: false, fields: [],
  figure: {field_ids: [], channel_ids: [], include_merge: true, crop: null, inset: null,
    width_mm: 85, dpi: 300, font_pt: 9, scale_bar_um: null, locked_ranges: {}},
})
const buttons = (name: string) => [...host.querySelectorAll('button')].filter(b => b.textContent === name)
async function click(name: string) {
  expect(buttons(name).length).toBeGreaterThan(0)
  await act(async () => {buttons(name)[0].click()})
}
async function editName() {
  await act(async () => {
    const input = host.querySelector('[aria-label="IF 实验名称"]') as HTMLInputElement
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '修改待保存')
    input.dispatchEvent(new Event('input', {bubbles: true}))
  })
}
beforeEach(async () => {
  vi.useFakeTimers()
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
  onStats = vi.fn()
  vi.mocked(callEngine).mockImplementation(async (command, payload: any = {}) => {
    if (command === 'library_list') return [] as any
    if (command === 'if_demo') return project('原项目') as any
    if (command === 'if_new') return project('新项目') as any
    if (command === 'if_release') return {} as any
    if (command === 'if_save') {
      saving = structuredClone(payload.project)
      return await new Promise<IFProject>((resolve, reject) => {resolveSave = resolve; rejectSave = reject}) as any
    }
    throw new Error(`Unexpected command: ${command}`)
  })
  await act(async () => root.render(React.createElement(IFWorkspace, {
    active: true, path: null, onWB: vi.fn(), onWBOpen: vi.fn(), onStats,
    registerClose: vi.fn(), onRefresh: vi.fn(),
  })))
  await click('体验 IF 合成示例'); await editName()
})
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.clearAllMocks()
})

it('blocks imports until the previous IF project is saved before switching', async () => {
  await click('新建 IF 实验')
  expect(buttons('导入 IF 视野').every(b => b.disabled)).toBe(true)
  expect(vi.mocked(callEngine).mock.calls.some(([command]) => command === 'if_new')).toBe(false)
  await act(async () => resolveSave({...saving, saved_revision: saving.revision}))
  expect((host.querySelector('[aria-label="IF 实验名称"]') as HTMLInputElement).value).toBe('新项目')
  expect(buttons('导入 IF 视野').every(b => !b.disabled)).toBe(true)
  expect(callEngine).toHaveBeenCalledWith('if_release', {path: '/test/原项目.titanif'})
})

it('preserves the edited IF project and cancels the switch if saving fails', async () => {
  await click('新建 IF 实验')
  await act(async () => rejectSave(new Error('disk unavailable')))
  expect(host.textContent).toContain('保存未完成，当前修改仍保留')
  expect((host.querySelector('[aria-label="IF 实验名称"]') as HTMLInputElement).value).toBe('修改待保存')
  expect(vi.mocked(callEngine).mock.calls.some(([command]) => command === 'if_new')).toBe(false)
  expect(buttons('导入 IF 视野').every(b => !b.disabled)).toBe(true)
})

it('waits for the pending IF save before entering the statistics workspace', async () => {
  await click('统计与绘图')
  expect(onStats).not.toHaveBeenCalled()
  await act(async () => resolveSave({...saving, saved_revision: saving.revision}))
  expect(saving.name).toBe('修改待保存')
  expect(onStats).toHaveBeenCalledTimes(1)
  expect(host.textContent).toContain('已保存')
})
