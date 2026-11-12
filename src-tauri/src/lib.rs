mod auth;
use serde_json::{json,Value};
use tauri::Manager;
use tauri_plugin_dialog::DialogExt;
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

// Shared startup boundary: account availability must not gate construction of
// the scientific session/worker. Only a proven duplicate owner returns Err.
struct StartupState { auth:auth::Auth, session:Session, worker:EngineWorker }
fn prepare_startup(account:Result<auth::Auth,&'static str>, library_root:std::path::PathBuf,
    program:std::path::PathBuf,args:Vec<std::ffi::OsString>)->Result<StartupState,&'static str>{
    Ok(StartupState { auth:account?, session:Session{token:uuid::Uuid::new_v4().to_string(),library_root},
        worker:EngineWorker::new(program,args) })
}

pub fn run(){
    tauri::Builder::default()
      .setup(|app| {
        let (program,args)=if cfg!(debug_assertions){
          let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
          (root.join(if cfg!(windows){".venv/Scripts/python.exe"}else{".venv/bin/python"}),vec![root.join("backend/entry.py").into_os_string()])
        }else{
          (app.path().resource_dir()?.join("engine/wb-engine").join(if cfg!(windows){"wb-engine.exe"}else{"wb-engine"}),vec![])
        };
        // A duplicate owner is refused before initialization. Account I/O failures
        // instead return an inert Auth so guest scientific initialization continues.
        let startup = match prepare_startup(
          auth::Auth::new(app.path().app_local_data_dir()?.join("accounts"), &app.config().identifier),
          app.path().app_local_data_dir()?.join("library"), program, args) {
          Ok(startup) => startup,
          Err(_) => {
            for window in app.webview_windows().values() { let _ = window.hide(); }
            let message = "此账户环境的 Titan 已在运行。请使用已打开的窗口，或退出该实例后再启动。";
            let handle = app.handle().clone();
            // Dialog callbacks keep the main event loop responsive. No account or
            // scientific state exists in this refused process.
            app.dialog().message(message).title("Titan 无法启动")
              .kind(tauri_plugin_dialog::MessageDialogKind::Error).show(move |_| handle.exit(1));
            return Ok(());
          }
        };
        app.manage(startup.auth);
        app.manage(startup.session);
        app.manage(startup.worker);Ok(())
      })
      .plugin(tauri_plugin_dialog::init()).invoke_handler(tauri::generate_handler![auth::auth_status, auth::auth_login, auth::auth_cancel, auth::auth_logout, auth::auth_update_profile, auth::auth_sessions, auth::auth_revoke_session, auth::auth_revoke_all, engine, if_volume::if_volume_read, library_files::library_open_file])
      .build(tauri::generate_context!()).expect("Titan WB启动失败")
      .run(|app,event|{if matches!(event,tauri::RunEvent::Exit){if let Some(worker) = app.try_state::<EngineWorker>() { tauri::async_runtime::block_on(worker.shutdown()); }}});
}

#[cfg(test)]
mod tests{
 use super::*;
 #[test]fn scientific_payload_is_preserved(){assert_eq!(decode_response(br#"{"ok":true,"data":{"signal":80}}"#).unwrap()["signal"],80)}
 #[test]fn errors_are_not_success(){assert!(decode_response(br#"{"ok":false,"error":"zero denominator"}"#).is_err());assert!(decode_response(b"not json").is_err())}
}
