import {createAnalysis} from './library-actions'
import {test,expect} from '@playwright/test'
import {mkdtempSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {execFileSync} from 'node:child_process'

let root:string,source:string,paired:string,damaged:string,grayPng:string
test.beforeAll(()=>{
 root=mkdtempSync(path.join(tmpdir(),'titan-pages-'));source=path.join(root,'多页.tif')
 paired=path.join(root,'自动位深.tif');grayPng=path.join(root,'灰度RGB.png')
 damaged=path.join(root,'默认页损坏.tif')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
with tifffile.TiffWriter(sys.argv[1]) as t:
 t.write(np.zeros((20,30),dtype=np.uint8),photometric='palette',colormap=np.vstack([np.arange(256,dtype=np.uint16)*256,np.zeros(256,dtype=np.uint16),np.zeros(256,dtype=np.uint16)]))
 a=np.full((24,32),12345,dtype=np.uint16);a[4:8,4:8]=54321
 t.write(a,photometric='minisblack')
 t.write(np.ones((24,32),dtype=np.uint16),photometric='minisblack')
with tifffile.TiffWriter(sys.argv[2]) as t:
 t.write(np.ones((24,32),dtype=np.uint8),photometric='minisblack')
 t.write(np.full((24,32),12345,dtype=np.uint16),photometric='minisblack')
from PIL import Image
Image.new('RGB',(32,24),(45,45,45)).save(sys.argv[3])
import struct
from pathlib import Path
with tifffile.TiffFile(sys.argv[2]) as t:
 tag=t.pages[0].tags['StripOffsets']
 offset,order=tag.valueoffset,t.byteorder
 raw=bytearray(Path(sys.argv[2]).read_bytes())
struct.pack_into(order+'I',raw,offset,len(raw)+50)
Path(sys.argv[4]).write_bytes(raw)`,source,paired,grayPng,damaged])
})
test.afterAll(()=>rmSync(root,{recursive:true,force:true}))
async function start(page:any,input=source){
 await page.goto('/?integration=1')
 await createAnalysis(page,'wb')
 // Only the native file picker is replaced; inspection, preview and import use Python.
 await page.evaluate((file:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async(command:string)=>{
  if(command==='plugin:dialog|open')return [file]
  throw new Error(`Unexpected native command: ${command}`)
 }}},input)
 await page.getByRole('button',{name:'导入图像',exact:true}).click()
}

test('imports the first TIFF page at its original bit depth without a success banner',async({page})=>{
 await start(page,paired)
 await expect(page.getByLabel('当前图像')).toContainText('自动位深.tif · 第 1 页')
 await expect(page.getByLabel('当前图像').locator('option')).toHaveCount(1)
 await expect(page.getByRole('dialog',{name:'选择 TIFF 页面'})).toBeHidden()
 await expect(page.getByText('32 × 24 px · uint8',{exact:true})).toBeVisible()
 await expect(page.locator('.notice').filter({hasText:/自动导入第|确认极性与编码上界/})).toHaveCount(0)
})

test('imports a PNG saved as equal RGB channels',async({page})=>{
 await start(page,grayPng)
 await expect(page.getByLabel('当前图像')).toContainText('灰度RGB.png')
 await expect(page.getByRole('dialog',{name:'选择 TIFF 页面'})).toBeHidden()
 await expect(page.getByText('32 × 24 px · uint8',{exact:true})).toBeVisible()
})

test('offers other TIFF pages only when the first page cannot be decoded',async({page})=>{
 await start(page,damaged)
 const picker=page.getByRole('dialog',{name:'选择 TIFF 页面'})
 await expect(picker.getByRole('checkbox',{name:'导入第 1 页',exact:true})).toBeDisabled()
 await picker.getByRole('checkbox',{name:'导入第 2 页',exact:true}).check()
 await picker.getByRole('button',{name:'导入所选页面',exact:true}).click()
 await expect(page.getByLabel('当前图像')).toContainText('默认页损坏.tif · 第 2 页')
})
test('choose raw grayscale pages from a mixed multipage TIFF',async({page})=>{
 await start(page)
 const dialog=page.getByRole('dialog',{name:'选择 TIFF 页面'})
 await expect(dialog).toBeVisible()
 await expect(dialog.getByRole('checkbox',{name:'导入第 1 页',exact:true})).toBeDisabled()
 await expect(dialog.getByRole('button',{name:'导入所选页面',exact:true})).toBeDisabled()
 const secondPage=dialog.getByRole('checkbox',{name:'导入第 2 页',exact:true})
 // The card's lower-right padding must work, not just its state indicator.
 const box=(await secondPage.boundingBox())!
 await page.mouse.click(box.x+box.width-18,box.y+box.height-18)
 await expect(secondPage).toBeChecked()
 await expect(dialog.getByRole('img',{name:'第 2 页预览',exact:true})).toBeVisible()
 await page.screenshot({path:'artifacts/checkpoints/image-page-picker.png',fullPage:true})
 await dialog.getByRole('button',{name:'导入所选页面',exact:true}).click()
 await expect(dialog).not.toBeVisible()
 await expect(page.getByLabel('当前图像')).toContainText('多页.tif · 第 2 页')
 await expect(page.getByLabel('当前图像').locator('option')).toHaveCount(1)
 await expect(page.getByText('32 × 24 px · uint16',{exact:true})).toBeVisible()
})
test('page cards toggle once from any area and support keyboard selection',async({page},testInfo)=>{
 await page.emulateMedia({colorScheme:'dark'})
 await start(page)
 const dialog=page.getByRole('dialog',{name:'选择 TIFF 页面'})
 const secondPage=dialog.getByRole('checkbox',{name:'导入第 2 页',exact:true})
 const thirdPage=dialog.getByRole('checkbox',{name:'导入第 3 页',exact:true})
 const box=(await secondPage.boundingBox())!
 expect(box.height).toBeGreaterThanOrEqual(100)
 await secondPage.click()
 await expect(secondPage).toBeChecked()
 await secondPage.click()
 await expect(secondPage).not.toBeChecked()
 await expect(dialog.getByRole('button',{name:'导入所选页面',exact:true})).toBeDisabled()
 await secondPage.focus()
 await page.keyboard.press('Space')
 await expect(secondPage).toBeChecked()
 await thirdPage.focus()
 await page.keyboard.press('Enter')
 await expect(thirdPage).toBeChecked()
 await expect(secondPage).toBeChecked()
 await expect(dialog.getByRole('img',{name:'第 3 页预览',exact:true})).toBeVisible()
 await page.keyboard.press('Enter')
 await expect(thirdPage).not.toBeChecked()
 await expect(secondPage).toBeChecked()
 await page.screenshot({path:testInfo.outputPath('page-cards-dark.png'),fullPage:true})
})
test('cancel and Escape leave the project unchanged; all valid pages can be selected',async({page})=>{
 await start(page)
 await expect(page.getByRole('dialog',{name:'选择 TIFF 页面'})).toBeVisible()
 await page.keyboard.press('Escape')
 await expect(page.getByRole('dialog')).not.toBeVisible()
 await expect(page.getByText('0 张原始图像',{exact:false})).toBeVisible()
 await page.getByRole('button',{name:'导入图像',exact:true}).click()
 const dialog=page.getByRole('dialog',{name:'选择 TIFF 页面'})
 await dialog.getByRole('button',{name:'全选可用页',exact:true}).click()
 await dialog.getByRole('button',{name:'导入所选页面',exact:true}).click()
 await expect(page.getByLabel('当前图像').locator('option')).toHaveCount(2)
})
