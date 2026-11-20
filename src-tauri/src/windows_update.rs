use serde::Serialize;
use serde_json::{json, Value};
use std::time::Duration;
use tauri::{ipc::Channel, AppHandle, State};
use tauri_plugin_updater::{Update, UpdaterExt};
use tokio::sync::Mutex;

use crate::engine_worker::EngineWorker;

pub const SUPPORTED: bool = cfg!(all(target_os = "windows", target_arch = "x86_64"));

#[derive(Default)]
pub struct WindowsUpdates(Mutex<Option<Candidate>>);

struct Candidate {
    update: Update,
    downloaded: Option<Vec<u8>>,
}

#[derive(Serialize)]
pub struct UpdateMetadata {
    version: String,
    body: Option<String>,
}

#[tauri::command]
pub async fn check_windows_update(
    app: AppHandle,
    state: State<'_, WindowsUpdates>,
) -> Result<Option<UpdateMetadata>, String> {
    if !SUPPORTED {
        return Err("此平台不支持 Windows 更新".into());
    }
    let mut candidate = state.0.lock().await;
    *candidate = None;
    // The plugin's default callback hides the window and clears webview resources
    // before launching the installer. Titan has a separate save and shutdown guard.
    // Leave the window and download intact if the OS rejects the installer launch.
    let updater = app
        .updater_builder()
        .on_before_exit(|| {})
        .restart_after_install(true)
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|error| error.to_string())?;
    let Some(update) = updater.check().await.map_err(|error| error.to_string())? else {
        return Ok(None);
    };
    let metadata = UpdateMetadata {
        version: update.version.clone(),
        body: update.body.clone(),
    };
    *candidate = Some(Candidate {
        update,
        downloaded: None,
    });
    Ok(Some(metadata))
}

#[tauri::command]
pub async fn download_windows_update(
    state: State<'_, WindowsUpdates>,
    version: String,
    on_event: Channel<Value>,
) -> Result<(), String> {
    let mut candidate = state.0.lock().await;
    let entry = candidate
        .as_mut()
        .filter(|candidate| candidate.update.version == version)
        .ok_or("更新已变更，请重新检查")?;
    entry.update.timeout = Some(Duration::from_secs(600));
    let mut first_chunk = true;
    let downloaded = entry
        .update
        .download(
            |chunk_length, content_length| {
                if first_chunk {
                    first_chunk = false;
                    let _ = on_event.send(
                        json!({"event": "Started", "data": {"contentLength": content_length}}),
                    );
                }
                let _ = on_event
                    .send(json!({"event": "Progress", "data": {"chunkLength": chunk_length}}));
            },
            || {},
        )
        .await
        .map_err(|error| error.to_string())?;
    entry.downloaded = Some(downloaded);
    Ok(())
}

#[tauri::command]
pub async fn install_windows_update(
    state: State<'_, WindowsUpdates>,
    worker: State<'_, EngineWorker>,
    version: String,
) -> Result<(), String> {
    if !worker.is_paused_for_update() {
        return Err("请先保存当前工作并暂停本地引擎".into());
    }
    let candidate = state.0.lock().await;
    let entry = candidate
        .as_ref()
        .filter(|candidate| candidate.update.version == version)
        .ok_or("更新已变更，请重新检查")?;
    let downloaded = entry.downloaded.as_ref().ok_or("请先下载更新")?;
    // Tauri rechecks the signature and exits only after the installer launches.
    entry
        .update
        .install(downloaded)
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub async fn clear_windows_update(
    state: State<'_, WindowsUpdates>,
    version: String,
) -> Result<(), String> {
    let mut candidate = state.0.lock().await;
    if candidate
        .as_ref()
        .is_some_and(|entry| entry.update.version == version)
    {
        *candidate = None;
    }
    Ok(())
}
