use serde_json::{json, Value};
use std::{ffi::OsString, path::PathBuf, process::Stdio, sync::atomic::{AtomicU64,Ordering}, time::Duration};
use tokio::{io::{AsyncBufReadExt,AsyncWriteExt,BufReader},process::{Child,ChildStdin,ChildStdout},sync::{Mutex,Semaphore}};

const LIMIT:usize=20*1024*1024;
struct Process { child:Child,input:ChildStdin,output:BufReader<ChildStdout> }
pub struct EngineWorker {
    program:PathBuf,args:Vec<OsString>,process:Mutex<Option<Process>>,
    slots:Semaphore,next_id:AtomicU64,timeout:Duration,
}
impl EngineWorker {
    pub fn new(program:PathBuf,args:Vec<OsString>)->Self {
        Self{program,args,process:Mutex::new(None),slots:Semaphore::new(32),next_id:AtomicU64::new(1),timeout:Duration::from_secs(60)}
    }
    pub async fn request(&self,mut request:Value)->Result<Value,String>{
        let _slot=self.slots.try_acquire().map_err(|_|"等待中的操作太多，请稍后再试".to_string())?;
        let mut guard=self.process.lock().await;
        if guard.is_none(){
            let mut child=tokio::process::Command::new(&self.program);
            child.args(&self.args).arg("--stdio-server").stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::inherit()).kill_on_drop(true);
            #[cfg(target_os="windows")]
            child.creation_flags(0x08000000);
            let mut child=child.spawn().map_err(|e|format!("本地引擎启动失败：{e}"))?;
            let input=child.stdin.take().ok_or("引擎输入不可用")?;
            let output=BufReader::new(child.stdout.take().ok_or("引擎输出不可用")?);
            *guard=Some(Process{child,input,output});
        }
        let id=self.next_id.fetch_add(1,Ordering::Relaxed);
        request["request_id"]=json!(id);
        let mut encoded=serde_json::to_vec(&request).map_err(|e|e.to_string())?;
        if encoded.len()>LIMIT{return Err("请求过大，请减少图像数量".into())}
        encoded.push(b'\n');
        let p=guard.as_mut().unwrap();
        let result=tokio::time::timeout(self.timeout,async {
            p.input.write_all(&encoded).await.map_err(|e|e.to_string())?;
            p.input.flush().await.map_err(|e|e.to_string())?;
            let bytes=read_frame(&mut p.output).await?;
            let response:Value=serde_json::from_slice(&bytes).map_err(|_|"计算引擎返回了无效数据".to_string())?;
            if response["request_id"]!=json!(id){return Err("引擎响应顺序异常，请重试当前操作".into())}
            Ok(response)
        }).await.map_err(|_|"本次操作超过60秒，请重试；未自动重复保存或导出".to_string()).and_then(|v|v);
        match result {
            Ok(response)=>{
                if response["ok"]!=true{return Err(response["error"].as_str().unwrap_or("计算失败").into())}
                Ok(response["data"].clone())
            },
            Err(error)=>{if let Some(mut p)=guard.take(){let _=p.child.kill().await;let _=p.child.wait().await;}Err(error)}
        }
    }
    pub async fn shutdown(&self){
        if let Some(mut p)=self.process.lock().await.take(){let _=p.child.kill().await;let _=p.child.wait().await;}
    }
}
async fn read_frame(reader:&mut BufReader<ChildStdout>)->Result<Vec<u8>,String>{
    let mut output=Vec::new();
    loop {
        let buf=reader.fill_buf().await.map_err(|e|e.to_string())?;
        if buf.is_empty(){return Err("本地引擎已退出，请重新执行当前操作".into())}
        let end=buf.iter().position(|b|*b==b'\n');let n=end.map_or(buf.len(),|i|i+1);
        if output.len()+n>LIMIT+1{return Err("引擎返回数据过大".into())}
        output.extend_from_slice(&buf[..n]);reader.consume(n);
        if end.is_some(){return Ok(output)}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn worker()->EngineWorker {
        let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        EngineWorker::new(root.join(if cfg!(windows){".venv/Scripts/python.exe"}else{".venv/bin/python"}),vec![root.join("backend/entry.py").into_os_string()])
    }
    #[tokio::test]async fn reuses_process_after_domain_error(){
        let w=worker();let a=w.request(json!({"command":"health"})).await.unwrap();
        assert!(w.request(json!({"command":"unknown"})).await.is_err());
        let b=w.request(json!({"command":"health"})).await.unwrap();assert_eq!(a["worker_pid"],b["worker_pid"]);
        w.shutdown().await;assert!(w.process.lock().await.is_none());
    }
    #[tokio::test]async fn restarts_after_process_exit(){
        let w=worker();let a=w.request(json!({"command":"health"})).await.unwrap();
        {let mut g=w.process.lock().await;g.as_mut().unwrap().child.kill().await.unwrap();}
        assert!(w.request(json!({"command":"health"})).await.is_err());
        let b=w.request(json!({"command":"health"})).await.unwrap();assert_ne!(a["worker_pid"],b["worker_pid"]);w.shutdown().await;
    }
    #[tokio::test]async fn wrong_response_id_is_rejected(){
        let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let w=EngineWorker::new(root.join(if cfg!(windows){".venv/Scripts/python.exe"}else{".venv/bin/python"}),vec!["-u".into(),"-c".into(),"import sys;sys.stdin.readline();print('{\"request_id\":999,\"ok\":true,\"data\":1}')".into()]);
        assert!(w.request(json!({"command":"health"})).await.unwrap_err().contains("顺序"));assert!(w.process.lock().await.is_none());
    }
    #[tokio::test]async fn timeout_resets_worker(){
        let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        let mut w=EngineWorker::new(root.join(if cfg!(windows){".venv/Scripts/python.exe"}else{".venv/bin/python"}),vec!["-c".into(),"import time;time.sleep(10)".into()]);w.timeout=Duration::from_millis(50);
        assert!(w.request(json!({"command":"health"})).await.is_err());assert!(w.process.lock().await.is_none());
    }
    #[tokio::test]async fn linked_wb_result_can_be_saved_after_round_trip(){
        let root=std::env::temp_dir().join(format!("titan-linked-wb-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir_all(&root).unwrap();
        let session=json!({"pid":std::process::id(),"token":"linked-wb-round-trip","library_root":root.join("library")});
        let w=worker();
        let demo=w.request(json!({"command":"demo","session":session})).await.unwrap();
        let wb=w.request(json!({"command":"save_project","payload":{"project":demo,"path":root.join("source.titanwb"),"expected_revision":null},"session":session})).await.unwrap();
        let catalog=w.request(json!({"command":"stats_source_catalog","payload":{"path":wb["project_path"]},"session":session})).await.unwrap();
        let mut stats=w.request(json!({"command":"stats_from_source","payload":{"path":wb["project_path"],"keys":[catalog["choices"][0]["key"]],"expected_signature":catalog["signature"],"confirmed":true},"session":session})).await.unwrap();
        stats["name"]=json!("Renamed without changing source values");
        stats["revision"]=json!(stats["revision"].as_u64().unwrap()+1);
        let result=w.request(json!({"command":"stats_save","payload":{"project":stats},"session":session})).await;
        w.shutdown().await;std::fs::remove_dir_all(root).unwrap();
        assert!(result.is_ok(),"{:?}",result);
    }
}
