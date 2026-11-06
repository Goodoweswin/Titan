use crate::{EngineWorker, Session};
use serde_json::json;
use std::path::Path;

#[tauri::command]
pub async fn library_open_file(
    entry_id: String,
    artifact_id: Option<String>,
    reveal: bool,
    session: tauri::State<'_, Session>,
    worker: tauri::State<'_, EngineWorker>,
) -> Result<(), String> {
    if artifact_id.is_none() && !reveal {
        return Err("请选择已登记的导出文件".into());
    }
    let target = worker.request(json!({
        "command": "library_target",
        "payload": {"entry_id": entry_id, "artifact_id": artifact_id},
        "session": {
            "token": session.token,
            "pid": std::process::id(),
            "library_root": session.library_root.to_string_lossy()
        }
    })).await?;
    let path = target.as_str().ok_or("找不到已登记的文件")?;
    let path = Path::new(path);
    if !path.is_absolute() || !path.exists() {
        return Err("找不到已登记的文件".into());
    }
    open_in_system(path, reveal).await
}

async fn open_in_system(path: &Path, reveal: bool) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = tokio::process::Command::new("/usr/bin/open");
        if reveal && path.is_file() {
            command.arg("-R");
        }
        command.arg(path);
        command
    };
    #[cfg(target_os = "windows")]
    let mut command = {
        // Windows Explorer accepts a full Unicode path or a single /select argument.
        // Use the system copy, and pass the target as data without a shell.
        use std::{ffi::OsString, path::PathBuf};
        let windows = std::env::var_os("WINDIR").ok_or("无法定位系统文件管理器")?;
        let mut command = tokio::process::Command::new(PathBuf::from(windows).join("explorer.exe"));
        if reveal && path.is_file() {
            let mut arg = OsString::from("/select,");
            arg.push(path);
            command.arg(arg);
        } else {
            command.arg(path);
        }
        command
    };
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    let mut command = {
        let mut command = tokio::process::Command::new("xdg-open");
        let target = if reveal && path.is_file() {
            path.parent().unwrap_or(path)
        } else {
            path
        };
        command.arg(target);
        command
    };
    let status = command.status().await.map_err(|error| format!("无法打开文件：{error}"))?;
    // Explorer can return 1 after forwarding the request to an existing process.
    if status.success() || (cfg!(target_os = "windows") && status.code() == Some(1)) {
        Ok(())
    } else {
        Err("系统无法打开所选文件".into())
    }
}
