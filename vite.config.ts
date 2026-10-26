import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import {spawn} from 'node:child_process'
import path from 'node:path'
const integration={name:'local-integration-engine',configureServer(server:any){
 if(process.env.TITAN_INTEGRATION!=='1')return
 server.middlewares.use('/test-engine',(req:any,res:any)=>{
  let body='';req.on('data',(chunk:any)=>{body+=chunk;if(body.length>20*1024*1024)req.destroy()})
  req.on('end',()=>{
   const child=spawn(path.resolve('.venv/bin/python'),[path.resolve('backend/entry.py')],{stdio:['pipe','pipe','pipe']})
   let output='';child.stdout.on('data',(b:any)=>output+=b)
   child.on('error',(e:any)=>{res.statusCode=500;res.end(JSON.stringify({ok:false,error:String(e)}))})
   child.on('close',()=>{res.setHeader('Content-Type','application/json');res.end(output||JSON.stringify({ok:false,error:'test engine exited'}))})
   try{const request=JSON.parse(body);request.session={pid:process.pid,token:'integration-test'};child.stdin.end(JSON.stringify(request))}catch{child.kill();res.end('{"ok":false,"error":"invalid JSON"}')}
  })
 })
}}
export default defineConfig({plugins:[react(),integration], clearScreen:false,
  server:{host:'127.0.0.1',port:1420,strictPort:true},
  build:{target:'es2022'}})
