import {test,expect,type Page} from '@playwright/test'
import {mkdtemp,writeFile,unlink,rm} from 'node:fs/promises'
import {tmpdir} from 'node:os'
import {join} from 'node:path'

async function rpc(page:Page,command:string,payload:object={}){
 const response=await page.request.post('/test-engine',{data:{command,payload}})
 const result=await response.json()
 expect(result.ok,result.error).toBe(true)
 return result.data
}
function pathPrompt(page:Page,path:string){page.once('dialog',dialog=>dialog.accept(path))}

test('a project owns its materials across tools and moves independently of an analysis',async({page})=>{
 const dir=await mkdtemp(join(tmpdir(),'titan-project-ui-'))
 try{
  const material=join(dir,'signal.csv'),bundle=join(dir,'experiment.titanproject')
  await writeFile(material,'Control,Treated\n1,2\n3,5\n')
  const name='资料与分析 '+Date.now()
  await page.goto('/?integration=1')
  await page.getByRole('main').getByRole('button',{name:'新建项目',exact:true}).click()
  await page.getByRole('dialog').getByLabel('名称',{exact:true}).fill(name)
  await page.getByRole('dialog').getByRole('button',{name:'创建',exact:true}).click()
  await expect(page.getByRole('heading',{name,exact:true})).toBeVisible()

  pathPrompt(page,material)
  await page.getByRole('button',{name:'添加资料',exact:true}).click()
  await expect(page.getByText('signal.csv',{exact:true})).toBeVisible()
  await page.screenshot({path:'artifacts/project-workspace.png',animations:'disabled'})
  await unlink(material)

  await page.getByRole('button',{name:'Western blot',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Western blot',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'免疫荧光',exact:true}).click()
  await expect(page.getByRole('heading',{name:'免疫荧光',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'3D 查看（原型）',exact:true}).click()
  const volume=page.getByRole('dialog',{name:'免疫荧光 3D 查看'})
  await volume.getByRole('button',{name:'关闭 3D 查看'}).click()
  await page.getByRole('button',{name:'导入 IF 视野',exact:true}).click()
  await page.getByRole('button',{name:'关闭导入',exact:true}).click()
  const project=()=>page.getByRole('button',{name:'打开项目 '+name,exact:true})
  await project().click()
  await expect(page.getByText('signal.csv',{exact:true})).toBeVisible()
  await expect(page.getByText('这个项目还没有分析。',{exact:true})).toBeVisible()

  await page.getByRole('main').getByRole('button',{name:'新建分析',exact:true}).click()
  await page.getByRole('dialog').getByRole('button',{name:'新建 WB 分析',exact:true}).click()
  await expect(page.getByLabel('归属项目')).toHaveValue((await rpc(page,'library_workspace')).projects.find((p:any)=>p.name===name).id)
  await page.getByRole('dialog').getByLabel('名称',{exact:true}).fill(name+' WB')
  await page.getByRole('dialog').getByRole('button',{name:'创建',exact:true}).click()
  await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue(name+' WB')
  await project().click()
  await expect(page.getByRole('main').getByRole('button',{name:'打开分析 '+name+' WB',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'分析菜单 '+name+' WB',exact:true}).click()
  await page.getByRole('button',{name:'移出项目',exact:true}).click()
  await page.getByRole('dialog').getByRole('button',{name:'移出',exact:true}).click()
  await expect(page.getByText('这个项目还没有分析。',{exact:true})).toBeVisible()

  pathPrompt(page,bundle)
  await page.getByRole('button',{name:'导出项目包',exact:true}).click()
  await expect(page.getByRole('status').filter({hasText:'项目包已导出'})).toBeVisible()
  pathPrompt(page,bundle)
  await page.getByRole('button',{name:'新建或打开',exact:true}).click()
  await page.getByRole('button',{name:'打开项目包',exact:true}).click()
  await expect.poll(async()=>(await rpc(page,'library_workspace')).projects.filter((p:any)=>p.name===name).length).toBe(2)
  await expect(page.getByText('signal.csv',{exact:true})).toBeVisible()
 }finally{await rm(dir,{recursive:true,force:true})}
})

test('project table copies remain usable and tool TIFF import saves only after page selection',async({page})=>{
 const dir=await mkdtemp(join(tmpdir(),'titan-tool-ui-'))
 try{
  const table=join(dir,'copied-data.csv')
  await writeFile(table,'Control,Treated\n1,2\n3,5\n')
  await page.goto('/?integration=1')
  const name='使用资料 '+Date.now()
  const project=await rpc(page,'library_create_collection',{name})
  await rpc(page,'library_material_add',{collection_id:project.id,paths:[table]})
  await unlink(table)
  await page.reload()
  await page.getByRole('button',{name:'打开项目 '+name,exact:true}).click()
  await page.getByLabel('选择资料 copied-data.csv').check()
  await page.getByLabel('分析工具').selectOption('stats')
  await page.getByRole('button',{name:'用所选资料新建分析'}).click()
  const dialog=page.getByRole('dialog',{name:'导入统计数据'})
  await dialog.getByRole('button',{name:'预览数据'}).click()
  await expect(dialog.getByRole('status')).toContainText('2 组，2 行')
  await dialog.getByRole('button',{name:'确认并创建分析'}).click()
  await expect(page.getByLabel('统计项目名称')).toHaveValue('copied-data')
  const state=await rpc(page,'library_workspace')
  expect(state.entries.find((entry:any)=>entry.name==='copied-data')?.collection_id).toBe(project.id)

  const demo=await rpc(page,'demo')
  const image=demo.images[0].path
  const tiff=join(dir,'two-pages.tif')
  const {execFileSync}=await import('node:child_process')
  execFileSync('.venv/bin/python',['-c','from PIL import Image; import sys; a=Image.open(sys.argv[1]); a.save(sys.argv[2],save_all=True,append_images=[a.copy()])',image,tiff])
  await page.getByRole('button',{name:'Western blot',exact:true}).click()
  pathPrompt(page,tiff)
  await page.getByRole('button',{name:'导入图像',exact:true}).click()
  const picker=page.getByRole('dialog',{name:'选择 TIFF 页面'})
  await picker.getByRole('button',{name:'跳过此文件'}).click()
  await expect(picker).toBeHidden()
  expect((await rpc(page,'library_workspace')).entries.some((entry:any)=>entry.name==='two-pages')).toBe(false)

  pathPrompt(page,tiff)
  await page.getByRole('button',{name:'导入图像',exact:true}).click()
  await picker.getByLabel('导入第 2 页').check()
  await picker.getByRole('button',{name:'导入所选页面'}).click()
  await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue('two-pages')
  const final=await rpc(page,'library_workspace')
  const wb=final.entries.find((entry:any)=>entry.name==='two-pages')
  expect(wb.collection_id).toBe(null)
  const saved=await rpc(page,'open_project',{path:wb.path,read_only:true})
  expect(saved.images.map((a:any)=>a.page_index)).toEqual([1])
  expect(final.projects.find((item:any)=>item.id===project.id).materials).toHaveLength(1)
 }finally{await rm(dir,{recursive:true,force:true})}
})

test('opening a damaged WB analysis from Home offers its backup recovery',async({page})=>{
 const dir=await mkdtemp(join(tmpdir(),'titan-recover-ui-'))
 try{
  const path=join(dir,'backup.titanwb'),name='恢复备份 '+Date.now()
  await page.goto('/?integration=1')
  const draft=await rpc(page,'new_project',{name})
  const saved=await rpc(page,'save_project',{project:draft,path})
  await rpc(page,'save_project',{project:{...saved,revision:1,name:'损坏前'},path,expected_revision:0})
  await writeFile(join(path,'project.json'),'{invalid')
  pathPrompt(page,path)
  await page.getByRole('button',{name:'新建或打开',exact:true}).click()
  await page.getByRole('button',{name:'打开已有分析',exact:true}).click()
  page.once('dialog',dialog=>dialog.accept())
  await page.getByRole('button',{name:'尝试恢复项目',exact:true}).click()
  await expect(page.getByLabel('实验名称',{exact:true})).toHaveValue(name)
  expect((await rpc(page,'library_workspace')).entries.find((entry:any)=>entry.name===name)?.path).toContain('-恢复-')
 }finally{await rm(dir,{recursive:true,force:true})}
})
