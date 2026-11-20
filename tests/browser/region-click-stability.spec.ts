import {test,expect} from '@playwright/test'

test('a region-tool click keeps the viewport and lane inspector stable',async({page})=>{
 await page.goto('/?integration=1');await page.getByRole('button',{name:'教程',exact:true}).click()
 const next=page.getByRole('region',{name:'WB 分步教程'}).getByRole('button',{name:'下一步',exact:true})
 await next.click();await page.getByRole('button',{name:'选择区域',exact:true}).click()
 const canvas=page.getByLabel('泳道分析画布')
 const before=await canvas.evaluate(e=>({view:e.getAttribute('viewBox'),rect:{y:e.getBoundingClientRect().y,height:e.getBoundingClientRect().height},scroll:Array.from(document.querySelectorAll('*')).filter(n=>n.scrollTop).map(n=>({tag:n.tagName,class:n.className,y:n.scrollTop}))}))
 await page.getByLabel('泳道 L1',{exact:true}).click()
 const after=await canvas.evaluate(e=>({view:e.getAttribute('viewBox'),rect:{y:e.getBoundingClientRect().y,height:e.getBoundingClientRect().height},scroll:Array.from(document.querySelectorAll('*')).filter(n=>n.scrollTop).map(n=>({tag:n.tagName,class:n.className,y:n.scrollTop})),selection:getSelection()?.toString()}))
 await expect(page.getByRole('heading',{name:'L1 · 灰度曲线',exact:true})).toHaveCount(0)
 expect(after.view).toBe(before.view);expect(after.rect).toEqual(before.rect);expect(after.scroll).toEqual(before.scroll)
 await expect(next).toBeDisabled()
})

test('clicking blank canvas keeps the page stationary while receiving keyboard focus',async({page})=>{
  await page.setViewportSize({width:1440,height:940})
  await page.goto('/?integration=1');await page.getByRole('button',{name:'教程',exact:true}).click()
  await page.getByRole('region',{name:'WB 分步教程'}).getByRole('button',{name:'下一步',exact:true}).click()
  await page.getByRole('button',{name:'选择区域',exact:true}).click()
  const canvas=page.getByLabel('泳道分析画布')
  const before=await canvas.boundingBox()
  // Blank image area isolates focus scrolling from lane selection and inspector changes.
  const point=await canvas.evaluate(e=>{const p=new DOMPoint(750,1150).matrixTransform((e as SVGSVGElement).getScreenCTM()!);return {x:p.x,y:p.y}})
  await page.mouse.click(point.x,point.y)
  const after=await canvas.boundingBox()
  expect(after).toEqual(before)
  await expect(canvas).toBeFocused()
})
