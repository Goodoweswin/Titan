// @vitest-environment jsdom
import {act, createElement, StrictMode} from 'react'
import {createRoot} from 'react-dom/client'
import {afterEach, beforeEach, expect, test, vi} from 'vitest'
import {callEngine} from '../bridge'
import ImportDialog from './ImportDialog'
import type {IFInspection} from './types'

vi.mock('../bridge', () => ({callEngine: vi.fn()}))
vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)

const inspection:IFInspection = {
  name:'field.tif', size_bytes:512, series:[{
    index:0, axes:'YX', shape:[16,20], dtype:'uint16', width:20, height:16,
    channel_count:1, channel_names:['DAPI'], pixel_size_um:null,
    quantitative:true, requires_axes_mapping:false,
  }],
}
const container = document.createElement('div')
let root:ReturnType<typeof createRoot>

beforeEach(() => {
  document.body.append(container)
  root = createRoot(container)
  vi.mocked(callEngine).mockResolvedValue(inspection)
})
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.resetAllMocks()
})

function button(label:string) {
  const match = [...container.querySelectorAll('button')].find(button => button.textContent === label)
  if (!match) throw new Error(`Missing button ${label}`)
  return match
}
function fill(label:string, value:string) {
  const input = container.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)!
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value)
  input.dispatchEvent(new Event('input', {bubbles:true}))
}

test('inspects initial files and retains selections after a failed submission', async () => {
  let rejectImport!:(error:Error) => void
  const onImport = vi.fn(() => new Promise<void>((_, reject) => {rejectImport = reject}))
  await act(async () => {
    root.render(createElement(StrictMode, null, createElement(ImportDialog, {
      initialPaths:['/images/field.tif'], onClose:()=>{}, onImport,
    })))
  })
  expect(container.querySelector('legend')?.textContent).toBe('field.tif')
  expect(container.querySelector('textarea')?.value).toBe('/images/field.tif')
  expect(callEngine).toHaveBeenCalledExactlyOnceWith('if_inspect', {path:'/images/field.tif'})

  for (const [label, value] of [['样本编号','S1'],['生物学样本编号','B1'],['实验分组','control'],['采集批次','batch1']]) {
    await act(async () => fill(label, value))
  }
  await act(async () => container.querySelector<HTMLInputElement>('.if-confirm input')!.click())
  const submit = button('确认并导入视野')
  expect(submit.disabled).toBe(false)

  await act(async () => submit.click())
  expect(submit.disabled).toBe(true)
  expect(onImport).toHaveBeenCalledExactlyOnceWith([{
    path:'/images/field.tif', series_index:0, indexers:{}, axes_override:null, channel_indices:[0],
  }], expect.objectContaining({sample_id:'S1', bio_id:'B1'}))

  await act(async () => rejectImport(new Error('原图已改变')))
  expect(container.querySelector('[role="dialog"]')).not.toBeNull()
  expect(container.querySelector('[role="alert"]')?.textContent).toContain('原图已改变')
  expect(container.querySelector<HTMLInputElement>('input[aria-label="样本编号"]')?.value).toBe('S1')
  expect(submit.disabled).toBe(false)
})
