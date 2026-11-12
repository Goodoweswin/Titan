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
// Account-disabled startup has no OS store, marker path, or network capability.
// This is deliberately not a memory-only credential store.
pub struct DisabledStore;
impl CredentialStore for DisabledStore {
    fn load(&self) -> Result<Option<StoredCredentials>, &'static str> {
        Err("account_owner_unavailable")
    }
    fn write(&self, _: &StoredCredentials) -> Result<(), &'static str> {
        Err("account_owner_unavailable")
    }
    fn activate(&self) -> Result<(), &'static str> {
        Err("account_owner_unavailable")
    }
    fn block(&self) -> Result<(), &'static str> {
        Err("account_owner_unavailable")
    }
    fn delete(&self) -> Result<(), &'static str> {
        Err("account_owner_unavailable")
    }
}
// The marker contains no identity or secret. Missing, damaged, or inaccessible markers
// deny restore. It is removed BEFORE token consumption/logout, and activated only
// after the OS write and the final generation fence both succeed.
pub struct OsStore {
    pub service: String,
    pub marker: PathBuf,
    // Never unlink the lock file: all contenders must lock the same inode.
    _owner: std::fs::File,
}
impl OsStore {
    pub fn new(root: PathBuf, application: &str, issuer: &str) -> Result<Self, &'static str> {
        std::fs::create_dir_all(&root).map_err(|_| "account_owner_unavailable")?;
        let root = std::fs::canonicalize(root).map_err(|_| "account_owner_unavailable")?;
        let mut hash = Sha256::new();
        hash.update(
            format!("titan.accounts.v2\0{application}\0{issuer}\0titan-desktop\0").as_bytes(),
        );
        hash.update(root.as_os_str().as_encoded_bytes());
        let scope = format!("{:x}", hash.finalize());
        let mut options = std::fs::OpenOptions::new();
        options.read(true).write(true).create(true).truncate(false);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let owner = options
            .open(root.join(format!("{scope}.owner")))
            .map_err(|_| "account_owner_unavailable")?;
        owner.try_lock().map_err(|error| match error {
            std::fs::TryLockError::WouldBlock => "account_owner_busy",
            std::fs::TryLockError::Error(_) => "account_owner_unavailable",
        })?;
        Ok(Self {
            service: format!("org.titan.accounts.{scope}"),
            marker: root.join(format!("{scope}.restore")),
            _owner: owner,
        })
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
    fn distinct_application_roots_do_not_share_credentials() {
        let root = std::env::temp_dir().join(format!("titan-namespace-{}", uuid::Uuid::new_v4()));
        let release = OsStore::new(
            root.join("release"),
            "com.titan.release",
            "https://accounts.example.org",
        )
        .unwrap();
        let qa = OsStore::new(
            root.join("qa"),
            "com.titan.release",
            "https://accounts.example.org",
        )
        .unwrap();
        assert_ne!(
            release.service, qa.service,
            "application roots share an OS credential"
        );
        let alternate = OsStore::new(
            root.join("release"),
            "com.titan.qa",
            "https://accounts.example.org",
        )
        .unwrap();
        assert_ne!(
            release.service, alternate.service,
            "application IDs share an OS credential"
        );
        assert_ne!(release.marker, alternate.marker);
        drop((release, qa, alternate));
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn process_owner_probe() {
        let Ok(root) = std::env::var("TITAN_OWNER_PROBE_ROOT") else {
            return;
        };
        let owner = OsStore::new(
            PathBuf::from(&root),
            "com.titan.test",
            "https://accounts.example.org",
        );
        match owner {
            Err("account_owner_busy") => std::process::exit(73),
            Err(code) => panic!("unexpected lock failure: {code}"),
            Ok(_owner) => {
                if std::env::var_os("TITAN_OWNER_PROBE_HOLD").is_some() {
                    std::fs::write(PathBuf::from(root).join("ready"), b"ready").unwrap();
                    loop {
                        std::thread::sleep(std::time::Duration::from_millis(50));
                    }
                }
            }
        }
    }
    #[test]
    fn second_process_cannot_own_live_credentials() {
        let root = std::env::temp_dir().join(format!("titan-owner-{}", uuid::Uuid::new_v4()));
        let owner = OsStore::new(
            root.clone(),
            "com.titan.test",
            "https://accounts.example.org",
        )
        .unwrap();
        owner.activate().unwrap();
        let before = std::fs::read(&owner.marker).unwrap();
        let result = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "auth::storage::tests::process_owner_probe"])
            .env("TITAN_OWNER_PROBE_ROOT", &root)
            .output()
            .unwrap();
        assert_eq!(
            result.status.code(),
            Some(73),
            "second independent process acquired live credentials"
        );
        assert_eq!(
            std::fs::read(&owner.marker).unwrap(),
            before,
            "refused owner changed restoration state"
        );
        // Independent construction inside one process is also refused. No stale
        // logout, refresh or write can start while another owner remains alive.
        assert!(matches!(
            OsStore::new(
                root.clone(),
                "com.titan.test",
                "https://accounts.example.org"
            ),
            Err("account_owner_busy")
        ));
        // A pending storage closure owns an Arc to the store even after Auth is
        // dropped. It must finish before a new process may own the namespace.
        let pending_storage = std::sync::Arc::new(owner);
        let retained = pending_storage.clone();
        drop(pending_storage);
        let while_pending = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "auth::storage::tests::process_owner_probe"])
            .env("TITAN_OWNER_PROBE_ROOT", &root)
            .output()
            .unwrap();
        assert_eq!(while_pending.status.code(), Some(73));
        drop(retained);
        let successor = OsStore::new(
            root.clone(),
            "com.titan.test",
            "https://accounts.example.org",
        )
        .unwrap();
        successor.activate().unwrap();
        assert!(successor.marker.is_file());
        drop(successor);
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn crashed_process_releases_owner_without_deleting_lock_file() {
        let root = std::env::temp_dir().join(format!("titan-owner-crash-{}", uuid::Uuid::new_v4()));
        let mut child = std::process::Command::new(std::env::current_exe().unwrap())
            .args(["--exact", "auth::storage::tests::process_owner_probe"])
            .env("TITAN_OWNER_PROBE_ROOT", &root)
            .env("TITAN_OWNER_PROBE_HOLD", "1")
            .stdout(std::process::Stdio::null())
            .spawn()
            .unwrap();
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(10);
        while !root.join("ready").is_file() && std::time::Instant::now() < deadline {
            std::thread::sleep(std::time::Duration::from_millis(10));
        }
        let ready = root.join("ready").is_file();
        let refused = if ready {
            matches!(
                OsStore::new(
                    root.clone(),
                    "com.titan.test",
                    "https://accounts.example.org"
                ),
                Err("account_owner_busy")
            )
        } else {
            false
        };
        child.kill().unwrap();
        child.wait().unwrap();
        assert!(ready, "child did not acquire owner");
        assert!(refused, "parent entered while child was alive");
        let successor = OsStore::new(
            root.clone(),
            "com.titan.test",
            "https://accounts.example.org",
        )
        .unwrap();
        successor.activate().unwrap();
        assert!(successor.marker.is_file());
        drop(successor);
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn inaccessible_owner_root_fails_without_fallback() {
        let root =
            std::env::temp_dir().join(format!("titan-owner-invalid-{}", uuid::Uuid::new_v4()));
        std::fs::write(&root, b"not a directory").unwrap();
        assert!(matches!(
            OsStore::new(
                root.clone(),
                "com.titan.test",
                "https://accounts.example.org"
            ),
            Err("account_owner_unavailable")
        ));
        std::fs::remove_file(root).unwrap();
    }
    #[test]
    fn issuer_scopes_do_not_collide_and_restore_defaults_to_denied() {
        let root = std::env::temp_dir().join(format!("titan-store-{}", uuid::Uuid::new_v4()));
        let a = OsStore::new(root.clone(), "com.titan.test", "http://127.0.0.1:8000").unwrap();
        let b = OsStore::new(
            root.clone(),
            "com.titan.test",
            "https://accounts.example.org",
        )
        .unwrap();
        assert_ne!(a.service, b.service);
        assert_ne!(a.marker, b.marker);
        assert!(a.load().unwrap().is_none());
        a.activate().unwrap();
        assert!(a.marker.is_file());
        a.block().unwrap();
        assert!(a.load().unwrap().is_none());
        drop(a);
        drop(b);
        std::fs::remove_dir_all(root).unwrap();
    }
}
