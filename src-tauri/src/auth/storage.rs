use super::types::StoredCredentials;
use sha2::{Digest, Sha256};
use std::{io::Write, path::PathBuf};

pub trait CredentialStore: Send + Sync {
    fn load(&self) -> Result<Option<StoredCredentials>, &'static str>;
    fn write(&self, credentials: &StoredCredentials) -> Result<(), &'static str>;
    fn activate(&self) -> Result<(), &'static str>;
    fn block(&self) -> Result<(), &'static str>;
    fn delete(&self) -> Result<(), &'static str>;
}
// The marker contains no identity or secret. Missing, damaged, or inaccessible markers
// deny restore. It is removed BEFORE token consumption/logout, and activated only
// after the OS write and the final generation fence both succeed.
pub struct OsStore {
    pub service: String,
    pub marker: PathBuf,
}
impl OsStore {
    pub fn new(root: PathBuf, issuer: &str) -> Self {
        let scope = format!(
            "{:x}",
            Sha256::digest(format!("titan.accounts.v1\0{issuer}\0titan-desktop").as_bytes())
        );
        Self {
            service: format!("org.titan.accounts.{scope}"),
            marker: root.join(format!("{scope}.restore")),
        }
    }
    fn entry(&self) -> Result<keyring::Entry, &'static str> {
        if !cfg!(any(
            target_os = "macos",
            target_os = "windows",
            target_os = "linux",
            target_os = "ios"
        )) {
            return Err("credential_storage_failed");
        }
        keyring::Entry::new(&self.service, "titan-desktop").map_err(|_| "credential_storage_failed")
    }
}
impl CredentialStore for OsStore {
    fn load(&self) -> Result<Option<StoredCredentials>, &'static str> {
        if std::fs::read(&self.marker).ok().as_deref() != Some(b"restore-v1".as_slice()) {
            return Ok(None);
        }
        let raw = match self.entry()?.get_password() {
            Ok(value) => zeroize::Zeroizing::new(value),
            Err(keyring::Error::NoEntry) => return Ok(None),
            Err(_) => return Err("credential_storage_failed"),
        };
        if raw.len() > 16384 {
            return Err("credential_storage_failed");
        }
        serde_json::from_str(&raw)
            .map(Some)
            .map_err(|_| "credential_storage_failed")
    }
    fn write(&self, credentials: &StoredCredentials) -> Result<(), &'static str> {
        let raw = zeroize::Zeroizing::new(
            serde_json::to_string(credentials).map_err(|_| "credential_storage_failed")?,
        );
        self.entry()?
            .set_password(&raw)
            .map_err(|_| "credential_storage_failed")
    }
    fn activate(&self) -> Result<(), &'static str> {
        let root = self.marker.parent().ok_or("credential_storage_failed")?;
        std::fs::create_dir_all(root).map_err(|_| "credential_storage_failed")?;
        let temp = root.join(format!(".restore-{}", uuid::Uuid::new_v4()));
        let result = (|| {
            let mut options = std::fs::OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            let mut file = options.open(&temp)?;
            file.write_all(b"restore-v1")?;
            file.sync_all()?;
            #[cfg(windows)]
            {
                let _ = std::fs::remove_file(&self.marker);
            }
            std::fs::rename(&temp, &self.marker)
        })();
        let _ = std::fs::remove_file(temp);
        result.map_err(|_| "credential_storage_failed")
    }
    fn block(&self) -> Result<(), &'static str> {
        match std::fs::remove_file(&self.marker) {
            Ok(()) => Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(_) => Err("credential_cleanup_failed"),
        }
    }
    fn delete(&self) -> Result<(), &'static str> {
        match self.entry()?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(_) => Err("credential_cleanup_failed"),
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn issuer_scopes_do_not_collide_and_restore_defaults_to_denied() {
        let root = std::env::temp_dir().join(format!("titan-store-{}", uuid::Uuid::new_v4()));
        let a = OsStore::new(root.clone(), "http://127.0.0.1:8000");
        let b = OsStore::new(root.clone(), "https://accounts.example.org");
        assert_ne!(a.service, b.service);
        assert_ne!(a.marker, b.marker);
        assert!(a.load().unwrap().is_none());
        a.activate().unwrap();
        assert!(a.marker.is_file());
        a.block().unwrap();
        assert!(a.load().unwrap().is_none());
        std::fs::remove_dir_all(root).unwrap();
    }
}
