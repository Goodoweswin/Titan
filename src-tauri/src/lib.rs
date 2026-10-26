use serde_json::{json,Value};
use std::{process::Stdio,time::Duration};
use tokio::io::AsyncWriteExt;

struct Session { token:String }

fn decode_response(bytes:&[u8])->Result<Value,String>{
    let v:Value=serde_json::from_slice(bytes).map_err(|_|"计算引擎返回了无效数据".to_string())?;
    if v.get("ok").and_then(Value::as_bool)!=Some(true){return Err(v["error"].as_str().unwrap_or("计算失败").to_string())}
    Ok(v["data"].clone())
}

#[tauri::command]
async fn engine(mut request:Value,session:tauri::State<'_,Session>)->Result<Value,String>{
    if !request.is_object(){return Err("请求格式错误".into())}
    request["session"]=json!({"token":session.token,"pid":std::process::id()});
    let mut cmd;
    if cfg!(debug_assertions){
        let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        cmd=tokio::process::Command::new(root.join(if cfg!(target_os="windows") {".venv/Scripts/python.exe"} else {".venv/bin/python"}));
        cmd.arg(root.join("backend/entry.py"));
    }else{
        let exe=std::env::current_exe().map_err(|e|e.to_string())?;
        cmd=tokio::process::Command::new(exe.parent().ok_or("找不到引擎目录")?.join(if cfg!(target_os="windows") {"wb-engine.exe"} else {"wb-engine"}));
    }
    #[cfg(target_os="windows")]
    cmd.creation_flags(0x08000000); // CREATE_NO_WINDOW: retain piped JSON stdio.
    cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).kill_on_drop(true);
    let mut child=cmd.spawn().map_err(|e|format!("本地引擎启动失败：{e}"))?;
    let mut stdin=child.stdin.take().ok_or("引擎输入不可用")?;
    stdin.write_all(request.to_string().as_bytes()).await.map_err(|e|e.to_string())?;
    drop(stdin);
    let output=tokio::time::timeout(Duration::from_secs(60),child.wait_with_output()).await
        .map_err(|_|"本次计算超过60秒，请缩小批次后重试".to_string())?
        .map_err(|e|e.to_string())?;
    if !output.status.success(){return Err("本地计算进程异常退出，原项目未被替换".into())}
    decode_response(&output.stdout)
}

pub fn run(){
    tauri::Builder::default().manage(Session{token:uuid::Uuid::new_v4().to_string()})
      .plugin(tauri_plugin_dialog::init()).invoke_handler(tauri::generate_handler![engine])
      .run(tauri::generate_context!()).expect("Titan WB启动失败");
}

#[cfg(test)]
mod tests{
 use super::*;
 #[test]fn scientific_payload_is_preserved(){assert_eq!(decode_response(br#"{"ok":true,"data":{"signal":80}}"#).unwrap()["signal"],80)}
 #[test]fn errors_are_not_success(){assert!(decode_response(br#"{"ok":false,"error":"zero denominator"}"#).is_err());assert!(decode_response(b"not json").is_err())}
}
