use serde_json::{json,Value};
use tauri::Manager;
mod engine_worker;
mod if_volume;
mod library_files;
use engine_worker::EngineWorker;

struct Session { token:String, library_root:std::path::PathBuf }

fn decode_response(bytes:&[u8])->Result<Value,String>{
    let v:Value=serde_json::from_slice(bytes).map_err(|_|"计算引擎返回了无效数据".to_string())?;
    if v.get("ok").and_then(Value::as_bool)!=Some(true){return Err(v["error"].as_str().unwrap_or("计算失败").to_string())}
    Ok(v["data"].clone())
}

#[tauri::command]
async fn engine(mut request:Value,session:tauri::State<'_,Session>,worker:tauri::State<'_,EngineWorker>)->Result<Value,String>{
    if !request.is_object(){return Err("请求格式错误".into())}
    request["session"]=json!({"token":session.token,"pid":std::process::id(),"library_root":session.library_root.to_string_lossy()});
    worker.request(request).await
}

pub fn run(){
    tauri::Builder::default()
      .setup(|app| {
        app.manage(Session{token:uuid::Uuid::new_v4().to_string(),library_root:app.path().app_local_data_dir()?.join("library")});
        let (program,args)=if cfg!(debug_assertions){
          let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
          (root.join(if cfg!(windows){".venv/Scripts/python.exe"}else{".venv/bin/python"}),vec![root.join("backend/entry.py").into_os_string()])
        }else{
          (app.path().resource_dir()?.join("engine/wb-engine").join(if cfg!(windows){"wb-engine.exe"}else{"wb-engine"}),vec![])
        };
        app.manage(EngineWorker::new(program,args));Ok(())
      })
      .plugin(tauri_plugin_dialog::init()).invoke_handler(tauri::generate_handler![engine, if_volume::if_volume_read, library_files::library_open_file])
      .build(tauri::generate_context!()).expect("Titan WB启动失败")
      .run(|app,event|{if matches!(event,tauri::RunEvent::Exit){tauri::async_runtime::block_on(app.state::<EngineWorker>().shutdown());}});
}

#[cfg(test)]
mod tests{
 use super::*;
 #[test]fn scientific_payload_is_preserved(){assert_eq!(decode_response(br#"{"ok":true,"data":{"signal":80}}"#).unwrap()["signal"],80)}
 #[test]fn errors_are_not_success(){assert!(decode_response(br#"{"ok":false,"error":"zero denominator"}"#).is_err());assert!(decode_response(b"not json").is_err())}
}
