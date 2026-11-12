import {test,expect,type Locator} from '@playwright/test'

// Check the rendered UI, so a hard-coded light surface in any module is caught.
async function readableDarkSurface(locator:Locator,dark=true){
 await expect(locator).toBeVisible()
 const luminance=(color:string)=>{
  const values=color.match(/[\d.]+/g)!.slice(0,3).map(Number).map(n=>{
   const c=n/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4
  })
  return values[0]*.2126+values[1]*.7152+values[2]*.0722
 }
 await expect.poll(async()=>{
  const colors=await locator.evaluate(el=>{
   const style=getComputedStyle(el)
   return {background:style.backgroundColor,text:style.color}
  })
  const background=luminance(colors.background),text=luminance(colors.text)
  return (!dark||background<.1)&&(Math.max(text,background)+.05)/(Math.min(text,background)+.05)>=4.5
 },{message:'Surface should follow system appearance with readable text'}).toBe(true)
}

test('sidebar and project menu follow light and dark appearance live',async({page})=>{
 await page.emulateMedia({colorScheme:'light'})
 await page.goto('/?integration=1')
 const sidebar=page.getByRole('complementary',{name:'Titan 导航',exact:true})
 await sidebar.getByRole('button',{name:'新建或打开',exact:true}).click()
 const surfaces=[sidebar,sidebar.locator('.library-search'),sidebar.locator('.nav.active'),sidebar.locator('.library-popup')]
 for(const colorScheme of ['light','dark','light'] as const){
  await page.emulateMedia({colorScheme})
  await expect(sidebar).toHaveCSS('color-scheme',colorScheme)
  for(const surface of surfaces){
   await readableDarkSurface(surface,colorScheme==='dark')
   if(colorScheme==='light')await expect.poll(async()=>surface.evaluate(el=>
    getComputedStyle(el).backgroundColor.match(/[\d.]+/g)!.slice(0,3).map(Number).every(value=>value>220)
   ),{message:'Sidebar surfaces must become light when the system switches to light appearance'}).toBe(true)
  }
 }
})

test('IF follows system appearance live without recoloring scientific images',async({page},testInfo)=>{
 await page.emulateMedia({colorScheme:'light'})
 await page.goto('/?integration=1')
 await page.getByRole('button',{name:'免疫荧光',exact:true}).click()
 await page.getByRole('button',{name:'体验 IF 合成示例',exact:true}).click()
 const image=page.getByRole('img',{name:'免疫荧光原始通道预览'})
 await expect(image).toBeVisible()
 const pixels=await image.getAttribute('href')
 await expect(page.locator('.if-settings')).toHaveCSS('background-color','rgb(255, 255, 255)')
 await page.emulateMedia({colorScheme:'dark'})
 await readableDarkSurface(page.locator('.app-header:visible'))
 await readableDarkSurface(page.locator('.if-content'))
 await readableDarkSurface(page.locator('.if-settings'))
 await readableDarkSurface(page.getByLabel('DAPI 显示上限'))
 await readableDarkSurface(page.getByRole('button',{name:'测量当前视野',exact:true}),false)
 expect(await image.getAttribute('href')).toBe(pixels)
 await expect(image).toHaveCSS('filter','none')
 await page.screenshot({path:testInfo.outputPath('IF-dark.png'),fullPage:true})
 await page.getByRole('button',{name:'测量当前视野',exact:true}).click()
 await expect(page.getByRole('status').filter({hasText:'任务已完成'})).toBeVisible({timeout:30000})
 await page.getByRole('button',{name:'IF 定量结果',exact:true}).click()
 await readableDarkSurface(page.locator('.if-results th').first())
 await page.getByRole('button',{name:'导出 IF 结果',exact:true}).click()
 await readableDarkSurface(page.locator('.if-shell .modal'))
 await page.emulateMedia({colorScheme:'light'})
 await expect(page.locator('.if-shell .modal')).toHaveCSS('background-color','rgb(255, 255, 255)')
})

test('statistics tables, dialogs and figure controls share night appearance',async({page},testInfo)=>{
 await page.emulateMedia({colorScheme:'dark'})
 await page.goto('/?integration=1')
 await readableDarkSurface(page.locator('.project-workspace'))
 await page.getByRole('button',{name:'统计与绘图',exact:true}).click()
 await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await readableDarkSurface(page.locator('.stats-content'))
 await readableDarkSurface(page.locator('.stats-grid th').first())
 await page.getByRole('button',{name:'导入 / 粘贴',exact:true}).click()
 await readableDarkSurface(page.locator('.stats-modal'))
 await readableDarkSurface(page.getByLabel('粘贴统计数据'))
 await page.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('navigation',{name:'统计工作区'}).getByRole('button',{name:'图形',exact:true}).click()
 const plot=page.getByRole('img',{name:'统计图预览'})
 await expect(plot).toBeVisible()
 const exportedColors=await plot.getAttribute('src')
 await readableDarkSurface(page.locator('.stats-inspector'))
 await expect(plot).toHaveCSS('filter','none')
 await page.screenshot({path:testInfo.outputPath('statistics-dark.png'),fullPage:true})
 await page.emulateMedia({colorScheme:'light'})
 expect(await plot.getAttribute('src')).toBe(exportedColors)
 await expect(page.locator('.stats-content')).toHaveCSS('background-color','rgb(250, 251, 253)')
})

test('WB workbench and guide use the shared night surfaces',async({page},testInfo)=>{
 await page.emulateMedia({colorScheme:'dark'})
 await page.goto('/?integration=1')
 await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await page.getByRole('button',{name:'体验合成示例',exact:true}).click()
 await readableDarkSurface(page.locator('.canvas-toolbar'))
 await readableDarkSurface(page.locator('.workspace-main .image-card'))
 await readableDarkSurface(page.locator('.asset.selected'))
 await readableDarkSurface(page.locator('.statusbar:visible'))
 await page.screenshot({path:testInfo.outputPath('WB-dark.png'),fullPage:true})
 await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await page.getByRole('button',{name:'图像操作指引',exact:true}).click()
 await readableDarkSurface(page.getByRole('dialog',{name:'WB 图像操作指引'}))
})

test('new-project dialogs keep readable controls outside the main shell',async({page})=>{
 await page.emulateMedia({colorScheme:'dark'})
 await page.goto('/?integration=1')
 const library=page.getByRole('navigation',{name:'实验项目库'})
 await library.getByRole('button',{name:'新建或打开',exact:true}).click()
 await library.getByRole('button',{name:'新建项目',exact:true}).click()
 const dialog=page.getByRole('dialog')
 await readableDarkSurface(dialog)
 await readableDarkSurface(dialog.getByLabel('名称',{exact:true}))
 await readableDarkSurface(dialog.getByRole('button',{name:'创建',exact:true}),false)
})


test('account center follows live appearance inside the shared shell',async({page})=>{
 await page.goto('/?integration=1');await page.locator('.account-trigger').click()
 const center=page.getByRole('region',{name:'账户',exact:true})
 for(const colorScheme of ['dark','light'] as const){
  await page.emulateMedia({colorScheme})
  await readableDarkSurface(center,colorScheme==='dark')
  await readableDarkSurface(page.getByRole('navigation',{name:'浏览导航',exact:true}),colorScheme==='dark')
  await expect(page.locator('.account-trigger')).toHaveAttribute('aria-current','page')
 }
})
