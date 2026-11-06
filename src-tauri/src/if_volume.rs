use crate::Session;
use serde_json::Value;
use std::fs::{self, File};
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;
use tauri::ipc::Response;

const MAX_CHUNK: u64 = 4 * 1024 * 1024;
const MAX_VOLUME: u64 = 64 * 1024 * 1024;

fn read_chunk(root: &Path, token: &str, pid: u32, job_id: &str, offset: u64, length: u64) -> Result<Vec<u8>, String> {
    if job_id.len() != 32 || !job_id.bytes().all(|ch| ch.is_ascii_digit() || (b'a'..=b'f').contains(&ch)) {
        return Err("3D 任务编号无效".into());
    }
    if length == 0 || length > MAX_CHUNK {
        return Err("3D 数据读取范围无效".into());
    }
    let root = root.join("if-jobs").canonicalize().map_err(|_| "3D 任务目录不存在")?;
    let expected = root.join(job_id);
    let directory = expected.canonicalize().map_err(|_| "3D 任务已关闭")?;
    if expected != directory || directory.join(".cancel").exists() {
        return Err("3D 任务已关闭".into());
    }
    let load_json = |name: &str| -> Result<Value, String> {
        let path = directory.join(name);
        let bytes = fs::read(path).map_err(|_| "无法读取 3D 任务")?;
        serde_json::from_slice(&bytes).map_err(|_| "3D 任务状态无效".into())
    };
    let request = load_json("request.json")?;
    if request["owner"]["token"].as_str() != Some(token)
        || request["owner"]["pid"].as_u64() != Some(u64::from(pid))
        || request["operation"] != "volume"
    {
        return Err("无法读取此会话之外的 3D 任务".into());
    }
    let status = load_json("status.json")?;
    if status["status"] != "completed" {
        return Err("3D 数据尚未就绪".into());
    }
    let size = status["volume"]["bytes"].as_u64().ok_or("3D 数据大小无效")?;
    if size > MAX_VOLUME || offset.checked_add(length).filter(|end| *end <= size).is_none() {
        return Err("3D 数据读取范围无效".into());
    }
    let path = directory.join("volume.raw");
    if fs::symlink_metadata(&path).map_err(|_| "3D 数据已释放")?.file_type().is_symlink() {
        return Err("3D 数据位置无效".into());
    }
    let mut file = File::open(path).map_err(|_| "3D 数据已释放")?;
    if file.metadata().map_err(|_| "无法确认 3D 数据大小")?.len() != size {
        return Err("3D 数据大小与预期不符".into());
    }
    let mut buffer = vec![0; length as usize];
    file.seek(SeekFrom::Start(offset)).and_then(|_| file.read_exact(&mut buffer))
        .map_err(|_| "3D 数据读取中断")?;
    Ok(buffer)
}

#[tauri::command]
pub async fn if_volume_read(session: tauri::State<'_, Session>, job_id: String, offset: u64, length: u64) -> Result<Response, String> {
    let root = session.library_root.clone();
    let token = session.token.clone();
    tauri::async_runtime::spawn_blocking(move || {
        read_chunk(&root, &token, std::process::id(), &job_id, offset, length).map(Response::new)
    }).await.map_err(|error| error.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn reads_only_owned_completed_volume_and_bounded_ranges() {
        let root = std::env::temp_dir().join(uuid::Uuid::new_v4().simple().to_string());
        let id = "0123456789abcdef0123456789abcdef";
        let directory = root.join("if-jobs").join(id);
        fs::create_dir_all(&directory).unwrap();
        fs::write(directory.join("request.json"), json!({"owner":{"token":"secret","pid":123},"operation":"volume"}).to_string()).unwrap();
        fs::write(directory.join("status.json"), json!({"status":"completed","volume":{"bytes":6}}).to_string()).unwrap();
        fs::write(directory.join("volume.raw"), [1,2,3,4,5,6]).unwrap();
        assert_eq!(read_chunk(&root, "secret", 123, id, 2, 3).unwrap(), [3,4,5]);
        assert!(read_chunk(&root, "other", 123, id, 0, 1).is_err());
        assert!(read_chunk(&root, "secret", 123, id, u64::MAX, 1).is_err());
        assert!(read_chunk(&root, "secret", 123, "../bad", 0, 1).is_err());
        fs::write(directory.join(".cancel"), []).unwrap();
        assert!(read_chunk(&root, "secret", 123, id, 0, 1).is_err());
        fs::remove_dir_all(root).unwrap();
    }
}
