import {createAnalysis} from './library-actions'
import {test,expect} from '@playwright/test'
import {mkdtempSync,rmSync} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {execFileSync} from 'node:child_process'

let root:string,source:string
test.beforeAll(()=>{
 root=mkdtempSync(path.join(tmpdir(),'titan-pages-'));source=path.join(root,'多页.tif')
 execFileSync(path.resolve('.venv/bin/python'),['-c',`import sys,numpy as np,tifffile
with tifffile.TiffWriter(sys.argv[1]) as t:
 t.write(np.zeros((20,30),dtype=np.uint8),photometric='palette',colormap=np.vstack([np.arange(256,dtype=np.uint16)*256,np.zeros(256,dtype=np.uint16),np.zeros(256,dtype=np.uint16)]))
 a=np.full((24,32),12345,dtype=np.uint16);a[4:8,4:8]=54321
 t.write(a,photometric='minisblack')
 t.write(np.ones((24,32),dtype=np.uint16),photometric='minisblack')`,source])
})
test.afterAll(()=>rmSync(root,{recursive:true,force:true}))
async function start(page:any){
 await page.goto('/?integration=1')
 await createAnalysis(page,'wb')
 // Only the native file picker is replaced; inspection, preview and import use Python.
 await page.evaluate((file:string)=>{(window as any).__TAURI_INTERNALS__={invoke:async(command:string)=>{
  if(command==='plugin:dialog|open')return [file]
  throw new Error(`Unexpected native command: ${command}`)
 }}},source)
 await page.getByRole('button',{name:'导入图像',exact:true}).click()
}
test('choose raw grayscale pages from a mixed multipage TIFF',async({page})=>{
 await start(page)
 const dialog=page.getByRole('dialog',{name:'选择 TIFF 页面'})
 await expect(dialog).toBeVisible()
 await expect(dialog.getByRole('checkbox',{name:'导入第 1 页',exact:true})).toBeDisabled()
 await expect(dialog.getByRole('button',{name:'导入所选页面',exact:true})).toBeDisabled()
 await dialog.getByRole('button',{name:'预览第 2 页',exact:true}).click()
 await expect(dialog.getByRole('img',{name:'第 2 页预览',exact:true})).toBeVisible()
 await dialog.getByRole('checkbox',{name:'导入第 2 页',exact:true}).check()
 await page.screenshot({path:'artifacts/checkpoints/image-page-picker.png',fullPage:true})
 await dialog.getByRole('button',{name:'导入所选页面',exact:true}).click()
 await expect(dialog).not.toBeVisible()
 await expect(page.getByLabel('当前图像')).toContainText('多页.tif · 第 2 页')
 await expect(page.getByLabel('当前图像').locator('option')).toHaveCount(1)
 await expect(page.getByText('32 × 24 px · uint16',{exact:true})).toBeVisible()
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
