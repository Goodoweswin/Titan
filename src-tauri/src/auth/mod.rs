mod callback;
mod client;
mod config;
mod oauth;
mod storage;
mod types;
pub use client::Auth;
use types::{DeviceSession, Snapshot};
#[tauri::command]
pub async fn auth_status(auth: tauri::State<'_, Auth>) -> Result<Snapshot, ()> {
    Ok(auth.status().await)
}
#[tauri::command(rename_all = "camelCase")]
pub async fn auth_login(
    auth: tauri::State<'_, Auth>,
    memory_only: bool,
    switch_account: bool,
) -> Result<Snapshot, ()> {
    Ok(auth.login(memory_only, switch_account).await)
}
#[tauri::command]
pub fn auth_cancel(auth: tauri::State<'_, Auth>) -> Snapshot {
    auth.cancel()
}
#[tauri::command]
pub async fn auth_logout(auth: tauri::State<'_, Auth>) -> Result<Snapshot, ()> {
    Ok(auth.logout().await)
}
#[tauri::command]
pub async fn auth_update_profile(
    auth: tauri::State<'_, Auth>,
    name: String,
) -> Result<Snapshot, ()> {
    Ok(auth.update_profile(name).await)
}
#[tauri::command]
pub async fn auth_sessions(auth: tauri::State<'_, Auth>) -> Result<Vec<DeviceSession>, String> {
    auth.sessions().await
}
#[tauri::command]
pub async fn auth_revoke_session(auth: tauri::State<'_, Auth>, id: String) -> Result<Snapshot, ()> {
    Ok(auth.revoke_session(id).await)
}
#[tauri::command]
pub async fn auth_revoke_all(auth: tauri::State<'_, Auth>) -> Result<Snapshot, ()> {
    Ok(auth.revoke_all().await)
}
