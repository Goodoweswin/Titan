import type {Page} from '@playwright/test'

export async function createAnalysis(page:Page, module:'wb'|'if'|'stats', waitForCreation=true, name?:string){
 const library=page.getByRole('navigation',{name:'实验项目库'})
 await library.getByRole('button',{name:'新建或打开',exact:true}).click()
 await page.getByRole('menu').getByRole('menuitem',{name:module==='wb'?'新建 WB 分析':module==='if'?'新建 IF 分析':'新建统计分析',exact:true}).click()
 const dialog=page.getByRole('dialog')
 await dialog.getByLabel('名称',{exact:true}).fill(name??(module==='wb'?'未命名实验':module==='if'?'未命名 IF 实验':'未命名统计项目'))
 await dialog.getByRole('button',{name:'创建',exact:true}).click()
 if(waitForCreation)await dialog.waitFor({state:'hidden'})
}
