use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct Profile {
    pub id: String,
    pub name: String,
    pub email: String,
    pub created_at: String,
    pub email_verified: bool,
    pub session_id: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeviceSession {
    pub id: String,
    pub label: String,
    pub platform: String,
    pub created_at: String,
    pub last_seen_at: String,
    pub expires_at: String,
    pub current: bool,
}
#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Snapshot {
    pub status: &'static str,
    pub profile: Option<Profile>,
    pub message: Option<&'static str>,
    pub persistent: bool,
    pub error_code: Option<&'static str>,
}
impl Snapshot {
    pub fn new(status: &'static str) -> Self {
        Self {
            status,
            profile: None,
            message: None,
            persistent: false,
            error_code: None,
        }
    }
    pub fn error(mut self, code: &'static str) -> Self {
        self.error_code = Some(code);
        self.message = Some(match code {
            "credential_storage_failed" => "系统凭据存储不可用，请重试或选择仅本次登录。",
            "credential_cleanup_failed" => "已退出本机账户，凭据清理未全部完成；已阻止自动恢复。",
            "credential_invalidation_failed" => "已退出当前运行的账户，但无法清除登录凭据或禁用自动恢复；重启后可能再次登录，请重试退出。",
            "recent_auth_required" => "请重新登录后再退出所有设备。",
            "refresh_ambiguous" => "登录凭据更新结果不确定，请重新登录。",
            "login_cancelled" => "已取消登录。",
            "login_timeout" => "登录等待超时，请重试。",
            "unauthorized" => "登录已失效，请重新登录。",
            "network_unavailable" => "账户服务暂时无法连接，本地功能仍可使用。",
            "invalid_profile" => "请输入1至60个字符的昵称。",
            _ => "账户操作未完成，请稍后重试。",
        });
        self
    }
}
// Intentionally neither Serialize nor Debug: commands can only return sanitized snapshots.
#[derive(Clone)]
pub struct Credentials {
    pub access: zeroize::Zeroizing<String>,
    pub refresh: zeroize::Zeroizing<String>,
    pub access_expires: u64,
    pub family_expires: u64,
    pub subject: String,
    pub nonce: String,
    pub session_id: String,
}
#[derive(Deserialize, Serialize)]
pub struct StoredCredentials {
    pub refresh: String,
    pub family_expires: u64,
    pub subject: String,
    pub nonce: String,
    pub session_id: String,
}
impl Drop for StoredCredentials {
    fn drop(&mut self) {
        use zeroize::Zeroize;
        self.refresh.zeroize();
    }
}
pub fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}
