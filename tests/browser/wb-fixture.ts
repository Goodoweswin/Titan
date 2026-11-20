import {expect,type Page} from '@playwright/test'

/** Load scientific regression data through the ordinary project library. */
export async function openSyntheticWbFixture(page:Page){
 const fromTool=await page.getByRole('heading',{name:'Western blot',exact:true}).isVisible()
 async function rpc(command:string,payload:object={}){
  const response=await page.request.post('/test-engine',{data:{command,payload}})
  const result=await response.json()
  expect(result.ok,result.error).toBe(true)
  return result.data
 }
 const project=await rpc('demo')
 project.name='WB regression '+project.id
 await rpc('library_create_from_wb',{project})
 await page.reload()
 if(fromTool)await page.getByRole('button',{name:'Western blot',exact:true}).click()
 await page.getByRole('button',{name:'打开分析 '+project.name,exact:true}).click()
 await expect(page.getByLabel('原图条带工作台')).toBeVisible()
}
