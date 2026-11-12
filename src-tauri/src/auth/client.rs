use super::{
    callback,
    config::Config,
    oauth::Network,
    storage::{CredentialStore, DisabledStore, OsStore},
    types::*,
};
use std::{
    path::PathBuf,
    sync::{Arc, Mutex},
    time::Duration,
};
use tokio::sync::{watch, Mutex as AsyncMutex};

struct Inner {
    generation: u64,
    snapshot: Snapshot,
    credentials: Option<Credentials>,
    pending: Option<watch::Sender<bool>>,
    initialized: bool,
}
#[derive(Clone)]
pub struct Auth {
    inner: Arc<Mutex<Inner>>,
    store: Arc<dyn CredentialStore>,
    storage_gate: Arc<AsyncMutex<()>>,
    refresh_gate: Arc<AsyncMutex<()>>,
    network: Option<Network>,
    accounts_disabled: bool,
}
impl Auth {
    pub fn new(root: PathBuf, application: &str) -> Result<Self, &'static str> {
        Self::from_config(root, application, Config::environment())
    }
    fn from_config(
        root: PathBuf,
        application: &str,
        config: Result<Option<Config>, &'static str>,
    ) -> Result<Self, &'static str> {
        Ok(match config {
            Ok(Some(config)) => {
                let store = match OsStore::new(root, application, &config.issuer_string()) {
                    Ok(store) => Arc::new(store),
                    Err("account_owner_busy") => return Err("account_owner_busy"),
                    Err(_) => {
                        return Ok(Self::disabled(
                            "unavailable",
                            Some("account_owner_unavailable"),
                        ))
                    }
                };
                match Network::new(config) {
                    Ok(network) => Self::create(store, Some(network), "guest"),
                    Err(_) => Self::create(store, None, "unavailable"),
                }
            }
            Ok(None) => Self::disabled("unconfigured", None),
            Err(_) => Self::disabled("unavailable", Some("invalid_configuration")),
        })
    }
    fn disabled(status: &'static str, code: Option<&'static str>) -> Self {
        let mut auth = Self::create(Arc::new(DisabledStore), None, status);
        auth.accounts_disabled = true;
        if let Some(code) = code {
            auth.inner.lock().unwrap().snapshot = Snapshot::new(status).error(code);
        }
        auth
    }
    fn create(
        store: Arc<dyn CredentialStore>,
        network: Option<Network>,
        status: &'static str,
    ) -> Self {
        Self {
            inner: Arc::new(Mutex::new(Inner {
                generation: 0,
                snapshot: Snapshot::new(status),
                credentials: None,
                pending: None,
                initialized: false,
            })),
            store,
            network,
            accounts_disabled: false,
            storage_gate: Arc::new(AsyncMutex::new(())),
            refresh_gate: Arc::new(AsyncMutex::new(())),
        }
    }
    #[cfg(test)]
    fn with_store(store: Arc<dyn CredentialStore>) -> Self {
        Self::create(store, None, "guest")
    }
    pub fn snapshot(&self) -> Snapshot {
        self.inner.lock().unwrap().snapshot.clone()
    }
    fn start(&self) -> (u64, watch::Receiver<bool>) {
        let mut inner = self.inner.lock().unwrap();
        if let Some(sender) = inner.pending.take() {
            let _ = sender.send(true);
        }
        inner.generation += 1;
        inner.initialized = true;
        inner.credentials = None;
        inner.snapshot = Snapshot::new("logging_in");
        let (tx, rx) = watch::channel(false);
        inner.pending = Some(tx);
        if self.store.block().is_err() {
            inner.snapshot = Snapshot::new("unavailable").error("credential_invalidation_failed");
        }
        (inner.generation, rx)
    }
    #[cfg(test)]
    fn begin(&self) -> u64 {
        self.start().0
    }
    pub fn cancel(&self) -> Snapshot {
        let mut inner = self.inner.lock().unwrap();
        if inner.pending.is_none() {
            return inner.snapshot.clone();
        }
        if let Some(sender) = inner.pending.take() {
            let _ = sender.send(true);
        }
        inner.generation += 1;
        inner.credentials = None;
        inner.initialized = true;
        inner.snapshot = Snapshot::new("guest").error("login_cancelled");
        if self.store.block().is_err() {
            inner.snapshot = inner
                .snapshot
                .clone()
                .error("credential_invalidation_failed");
        }
        inner.snapshot.clone()
    }
    async fn storage<T: Send + 'static>(
        &self,
        task: impl FnOnce(Arc<dyn CredentialStore>) -> Result<T, &'static str> + Send + 'static,
    ) -> Result<T, &'static str> {
        let _gate = self.storage_gate.lock().await;
        let store = self.store.clone();
        tokio::task::spawn_blocking(move || task(store))
            .await
            .map_err(|_| "credential_storage_failed")?
    }
    fn fail(&self, generation: u64, code: &'static str, status: &'static str) -> Snapshot {
        let mut inner = self.inner.lock().unwrap();
        if inner.generation != generation {
            return inner.snapshot.clone();
        }
        if status == "offline" || status == "authenticated" {
            inner.snapshot.status = status;
            inner.snapshot = inner.snapshot.clone().error(code);
        } else {
            inner.generation += 1;
            inner.credentials = None;
            inner.pending = None;
            inner.snapshot = Snapshot::new(status).error(code);
            let _ = self.store.block();
            let auth = self.clone();
            let cleanup_generation = inner.generation;
            if let Ok(runtime) = tokio::runtime::Handle::try_current() {
                runtime.spawn(async move {
                    let _ = auth.delete_generation(cleanup_generation).await;
                });
            }
        }
        inner.snapshot.clone()
    }
    async fn commit(
        &self,
        generation: u64,
        credentials: Credentials,
        profile: Profile,
        persistent: bool,
    ) -> Snapshot {
        if credentials.family_expires <= now()
            || credentials.access_expires <= now()
            || !profile.matches_credentials(&credentials)
        {
            return self.fail(generation, "unauthorized", "reauth_required");
        }
        let _gate = self.storage_gate.lock().await;
        if self.inner.lock().unwrap().generation != generation {
            return self.snapshot();
        }
        if persistent {
            let stored = StoredCredentials {
                refresh: credentials.refresh.to_string(),
                family_expires: credentials.family_expires,
                subject: credentials.subject.clone(),
                nonce: credentials.nonce.clone(),
                session_id: credentials.session_id.clone(),
            };
            let store = self.store.clone();
            let saved = tokio::task::spawn_blocking(move || store.write(&stored))
                .await
                .unwrap_or(Err("credential_storage_failed"));
            if saved.is_err() {
                let _ = self.store.block();
                let store = self.store.clone();
                let _ = tokio::task::spawn_blocking(move || store.delete()).await;
                return self.fail(generation, "credential_storage_failed", "unavailable");
            }
        }
        // No credential-manager call is made under the state lock. Only the nonsecret marker
        // and final snapshot commit share the fence with cancel/logout/switch.
        let outcome = {
            let mut inner = self.inner.lock().unwrap();
            if inner.generation != generation {
                Err("stale_generation")
            } else if persistent && self.store.activate().is_err() {
                Err("credential_storage_failed")
            } else {
                inner.credentials = Some(credentials);
                inner.pending = None;
                inner.initialized = true;
                inner.snapshot = Snapshot {
                    status: "authenticated",
                    profile: Some(profile),
                    message: None,
                    persistent,
                    error_code: None,
                };
                Ok(inner.snapshot.clone())
            }
        };
        match outcome {
            Ok(snapshot) => snapshot,
            Err(code) => {
                let store = self.store.clone();
                let _ = tokio::task::spawn_blocking(move || store.delete()).await;
                if code == "stale_generation" {
                    self.snapshot()
                } else {
                    self.fail(generation, code, "unavailable")
                }
            }
        }
    }
    async fn delete_generation(&self, generation: u64) -> Result<(), &'static str> {
        let _gate = self.storage_gate.lock().await;
        if self.inner.lock().unwrap().generation != generation {
            return Ok(());
        }
        let store = self.store.clone();
        tokio::task::spawn_blocking(move || store.delete())
            .await
            .map_err(|_| "credential_cleanup_failed")?
    }
    pub async fn logout(&self) -> Snapshot {
        self.logout_generation(None).await
    }
    async fn logout_generation(&self, expected: Option<u64>) -> Snapshot {
        if self.accounts_disabled || self.snapshot().status == "unconfigured" {
            return self.snapshot();
        }
        let (generation, credentials, blocked) = {
            let mut inner = self.inner.lock().unwrap();
            if expected.is_some_and(|generation| generation != inner.generation) {
                return inner.snapshot.clone();
            }
            if let Some(sender) = inner.pending.take() {
                let _ = sender.send(true);
            }
            inner.generation += 1;
            inner.initialized = true;
            let credentials = inner.credentials.take();
            inner.snapshot = Snapshot::new(
                if self.network.is_none() && inner.snapshot.status == "unconfigured" {
                    "unconfigured"
                } else {
                    "guest"
                },
            );
            (inner.generation, credentials, self.store.block().is_ok())
        };
        let deleted = self.delete_generation(generation).await.is_ok();
        if let (Some(network), Some(credentials)) = (self.network.clone(), credentials) {
            tokio::spawn(async move {
                network.revoke(&credentials).await;
            });
        }
        let mut inner = self.inner.lock().unwrap();
        if generation == inner.generation && (!blocked || !deleted) {
            // Either durable removal is sufficient to prevent restart restore.
            // When both fail, preserve the local guest state without claiming that guarantee.
            let invalidated = blocked || deleted;
            inner.snapshot = inner.snapshot.clone().error(if invalidated {
                "credential_cleanup_failed"
            } else {
                "credential_invalidation_failed"
            });
        }
        inner.snapshot.clone()
    }
    pub async fn login(&self, memory_only: bool, switch_account: bool) -> Snapshot {
        self.login_with_opener(memory_only, switch_account, |url| {
            open::that_detached(url.as_str()).map_err(|_| "browser_unavailable")
        })
        .await
    }
    async fn login_with_opener(
        &self,
        memory_only: bool,
        switch_account: bool,
        opener: impl FnOnce(&url::Url) -> Result<(), &'static str> + Send + 'static,
    ) -> Snapshot {
        let Some(network) = self.network.clone() else {
            return self.snapshot();
        };
        let (generation, mut cancel) = self.start();
        if self.snapshot().status != "logging_in" {
            return self.snapshot();
        }
        let listener_cancel = cancel.clone();
        let attempt = async {
            // Bind before opening a browser: no race with the first callback.
            let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
                .await
                .map_err(|_| "callback_unavailable")?;
            let login = network
                .prepare(
                    listener
                        .local_addr()
                        .map_err(|_| "callback_unavailable")?
                        .port(),
                    switch_account,
                )
                .await?;
            let url = login.url.clone();
            tokio::task::spawn_blocking(move || opener(&url))
                .await
                .map_err(|_| "browser_unavailable")??;
            let code = callback::receive(
                listener,
                login.state.secret(),
                &network.config.issuer_string(),
                listener_cancel,
                Duration::from_secs(180),
            )
            .await?;
            let credentials = network.exchange(login, code).await?;
            let profile = network.profile(&credentials).await?;
            Ok::<_, &'static str>((credentials, profile))
        };
        let result = tokio::select! {biased;_=cancel.changed()=>Err("login_cancelled"),result=tokio::time::timeout(Duration::from_secs(210),attempt)=>result.unwrap_or(Err("login_timeout"))};
        match result {
            Ok((credentials, profile)) => {
                self.commit(generation, credentials, profile, !memory_only)
                    .await
            }
            Err(code) => self.fail(generation, code, "guest"),
        }
    }
    async fn access(&self) -> Result<(u64, Credentials), &'static str> {
        let _gate = self.refresh_gate.lock().await;
        let Some(network) = self.network.clone() else {
            return Err("unconfigured");
        };
        let (generation, load) = {
            let mut inner = self.inner.lock().unwrap();
            if inner.pending.is_some() {
                return Err("login_in_progress");
            }
            let load = !inner.initialized;
            inner.initialized = true;
            (inner.generation, load)
        };
        if load {
            let restored = self.storage(|store| store.load()).await;
            let mut inner = self.inner.lock().unwrap();
            if inner.generation != generation {
                return Err("stale_generation");
            }
            match restored {
                Ok(Some(stored))
                    if stored.family_expires > now()
                        && !stored.refresh.is_empty()
                        && !stored.subject.is_empty()
                        && !stored.session_id.is_empty() =>
                {
                    inner.credentials = Some(Credentials {
                        access: zeroize::Zeroizing::new(String::new()),
                        refresh: zeroize::Zeroizing::new(stored.refresh.clone()),
                        access_expires: 0,
                        family_expires: stored.family_expires,
                        subject: stored.subject.clone(),
                        nonce: stored.nonce.clone(),
                        session_id: stored.session_id.clone(),
                    });
                    inner.snapshot.persistent = true;
                }
                Ok(Some(_)) => {
                    inner.snapshot = Snapshot::new("reauth_required").error("unauthorized");
                    let _ = self.store.block();
                    return Err("unauthorized");
                }
                Ok(None) => return Err("guest"),
                Err(code) => {
                    inner.snapshot = Snapshot::new("unavailable").error(code);
                    return Err(code);
                }
            }
        }
        let (previous, persistent) = {
            let inner = self.inner.lock().unwrap();
            if inner.generation != generation {
                return Err("stale_generation");
            }
            (
                inner.credentials.clone().ok_or("guest")?,
                inner.snapshot.persistent,
            )
        };
        if previous.family_expires <= now() {
            self.fail(generation, "unauthorized", "reauth_required");
            return Err("unauthorized");
        }
        if previous.access_expires > now() + 30 {
            return Ok((generation, previous));
        }
        // Discovery can fail without consuming a rotating refresh credential. Once a
        // POST can be sent, restore is disabled until the replacement is committed.
        let metadata = match network.discover().await {
            Ok(metadata) => metadata,
            Err(code) => {
                self.fail(generation, code, "offline");
                return Err(code);
            }
        };
        {
            let inner = self.inner.lock().unwrap();
            if inner.generation != generation {
                return Err("stale_generation");
            }
            if self.store.block().is_err() {
                drop(inner);
                self.fail(generation, "credential_storage_failed", "unavailable");
                return Err("credential_storage_failed");
            }
        }
        let credentials = match network.refresh(&previous, metadata).await {
            Ok(credentials) => credentials,
            Err(code) => {
                self.fail(generation, code, "reauth_required");
                return Err(code);
            }
        };
        let profile = match network.profile(&credentials).await {
            Ok(profile) => profile,
            Err(code) => {
                self.fail(
                    generation,
                    if code == "network_unavailable" {
                        "refresh_ambiguous"
                    } else {
                        code
                    },
                    "reauth_required",
                );
                return Err(code);
            }
        };
        let result = credentials.clone();
        let snapshot = self
            .commit(generation, credentials, profile, persistent)
            .await;
        if snapshot.status == "authenticated" && self.inner.lock().unwrap().generation == generation
        {
            Ok((generation, result))
        } else {
            Err(snapshot.error_code.unwrap_or("stale_generation"))
        }
    }
    pub async fn status(&self) -> Snapshot {
        let Ok((generation, credentials)) = self.access().await else {
            return self.snapshot();
        };
        let network = self.network.as_ref().unwrap();
        match network.profile(&credentials).await {
            Ok(profile) => {
                let mut inner = self.inner.lock().unwrap();
                if inner.generation == generation {
                    inner.snapshot.status = "authenticated";
                    inner.snapshot.profile = Some(profile);
                    inner.snapshot.message = None;
                    inner.snapshot.error_code = None;
                }
                inner.snapshot.clone()
            }
            Err(code) => {
                let terminal = matches!(
                    code,
                    "unauthorized" | "invalid_id_token" | "invalid_response"
                );
                let result = self.fail(
                    generation,
                    code,
                    if terminal {
                        "reauth_required"
                    } else {
                        "offline"
                    },
                );
                result
            }
        }
    }
    async fn api(
        &self,
        method: reqwest::Method,
        path: &str,
        body: Option<serde_json::Value>,
    ) -> Result<(u64, serde_json::Value), &'static str> {
        let (generation, credentials) = self.access().await?;
        let result = self
            .network
            .as_ref()
            .unwrap()
            .api(method, path, &credentials.access, body)
            .await;
        if self.inner.lock().unwrap().generation != generation {
            return Err("stale_generation");
        }
        match result {
            Ok(value) => {
                let mut inner = self.inner.lock().unwrap();
                if inner.generation != generation {
                    return Err("stale_generation");
                }
                inner.snapshot.status = "authenticated";
                inner.snapshot.error_code = None;
                inner.snapshot.message = None;
                Ok((generation, value))
            }
            Err(code) => {
                self.fail(
                    generation,
                    code,
                    if code == "unauthorized" {
                        "reauth_required"
                    } else if code == "network_unavailable" {
                        "offline"
                    } else {
                        "authenticated"
                    },
                );
                Err(code)
            }
        }
    }
    pub async fn update_profile(&self, name: String) -> Snapshot {
        if self.accounts_disabled {
            return self.snapshot();
        }
        let name = name.trim();
        if name.is_empty() || name.chars().count() > 60 || name.chars().any(char::is_control) {
            let mut snapshot = self.snapshot();
            snapshot = snapshot.error("invalid_profile");
            return snapshot;
        }
        let Ok((generation, value)) = self
            .api(
                reqwest::Method::PATCH,
                "/api/v1/me",
                Some(serde_json::json!({"name":name})),
            )
            .await
        else {
            return self.snapshot();
        };
        let Ok(profile) = serde_json::from_value::<Profile>(value) else {
            return self.fail(generation, "invalid_response", "unavailable");
        };
        let mut inner = self.inner.lock().unwrap();
        if inner.generation == generation {
            if !inner
                .credentials
                .as_ref()
                .is_some_and(|credentials| profile.matches_credentials(credentials))
            {
                drop(inner);
                return self.fail(generation, "invalid_id_token", "reauth_required");
            }
            inner.snapshot.profile = Some(profile);
            inner.snapshot.status = "authenticated";
            inner.snapshot.message = None;
            inner.snapshot.error_code = None;
        }
        inner.snapshot.clone()
    }
    pub async fn sessions(&self) -> Result<Vec<DeviceSession>, String> {
        let (generation, value) = self
            .api(reqwest::Method::GET, "/api/v1/sessions", None)
            .await
            .map_err(str::to_owned)?;
        #[derive(serde::Deserialize)]
        struct List {
            sessions: Vec<DeviceSession>,
        }
        let sessions = serde_json::from_value::<List>(value)
            .map(|v| v.sessions)
            .map_err(|_| "invalid_response".to_string())?;
        if self.inner.lock().unwrap().generation != generation {
            return Err("stale_generation".into());
        }
        Ok(sessions)
    }
    pub async fn revoke_session(&self, id: String) -> Snapshot {
        let Ok(id) = uuid::Uuid::parse_str(&id) else {
            return self.snapshot().error("invalid_request");
        };
        let path = format!("/api/v1/sessions/{id}");
        let Ok((generation, _)) = self.api(reqwest::Method::DELETE, &path, None).await else {
            return self.snapshot();
        };
        let current = {
            let inner = self.inner.lock().unwrap();
            inner.generation == generation
                && inner
                    .credentials
                    .as_ref()
                    .is_some_and(|credentials| credentials.session_id == id.to_string())
        };
        if current {
            self.logout_generation(Some(generation)).await
        } else {
            self.snapshot()
        }
    }
    pub async fn revoke_all(&self) -> Snapshot {
        if let Ok((generation, _)) = self
            .api(reqwest::Method::POST, "/api/v1/sessions/revoke-all", None)
            .await
        {
            self.logout_generation(Some(generation)).await
        } else {
            self.snapshot()
        }
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicBool, Ordering};
    #[derive(Default)]
    pub(super) struct Store {
        active: AtomicBool,
        saved: Mutex<Option<String>>,
        fail_write: AtomicBool,
        fail_delete: AtomicBool,
        fail_block: AtomicBool,
    }
    impl CredentialStore for Store {
        fn load(&self) -> Result<Option<StoredCredentials>, &'static str> {
            if !self.active.load(Ordering::SeqCst) {
                return Ok(None);
            }
            Ok(self
                .saved
                .lock()
                .unwrap()
                .as_ref()
                .map(|raw| serde_json::from_str(raw).unwrap()))
        }
        fn write(&self, c: &StoredCredentials) -> Result<(), &'static str> {
            if self.fail_write.load(Ordering::SeqCst) {
                return Err("credential_storage_failed");
            }
            *self.saved.lock().unwrap() = Some(serde_json::to_string(c).unwrap());
            Ok(())
        }
        fn activate(&self) -> Result<(), &'static str> {
            self.active.store(true, Ordering::SeqCst);
            Ok(())
        }
        fn block(&self) -> Result<(), &'static str> {
            if self.fail_block.load(Ordering::SeqCst) {
                return Err("credential_cleanup_failed");
            }
            self.active.store(false, Ordering::SeqCst);
            Ok(())
        }
        fn delete(&self) -> Result<(), &'static str> {
            if self.fail_delete.load(Ordering::SeqCst) {
                return Err("credential_cleanup_failed");
            }
            *self.saved.lock().unwrap() = None;
            Ok(())
        }
    }
    pub(super) fn credentials() -> Credentials {
        Credentials {
            access: zeroize::Zeroizing::new("secret-access".into()),
            refresh: zeroize::Zeroizing::new("secret-refresh".into()),
            access_expires: now() + 600,
            family_expires: now() + 1000,
            subject: "u1".into(),
            nonce: "nonce".into(),
            session_id: "s1".into(),
        }
    }
    pub(super) fn profile() -> Profile {
        Profile {
            id: "u1".into(),
            name: "Alice".into(),
            email: "a@example.org".into(),
            created_at: "2026-11-12T00:00:00Z".into(),
            email_verified: true,
            administrator_approved: false,
            session_id: "s1".into(),
        }
    }
    #[tokio::test]
    async fn managed_profile_commit_preserves_eligibility_and_identity_guards() {
        for (verified, approved, subject, session, accepted) in [
            (false, false, "u1", "s1", false),
            (false, true, "u1", "s1", true),
            (true, false, "u1", "s1", true),
            (false, true, "other", "s1", false),
            (false, true, "u1", "other", false),
        ] {
            let store = Arc::new(Store::default());
            let auth = Auth::with_store(store.clone());
            let generation = auth.begin();
            let mut value = serde_json::to_value(profile()).unwrap();
            value["emailVerified"] = serde_json::json!(verified);
            value["administratorApproved"] = serde_json::json!(approved);
            value["id"] = serde_json::json!(subject);
            value["sessionId"] = serde_json::json!(session);
            let snapshot = auth
                .commit(
                    generation,
                    credentials(),
                    serde_json::from_value(value).unwrap(),
                    true,
                )
                .await;
            assert_eq!(
                snapshot.status == "authenticated",
                accepted,
                "verified={verified}, approved={approved}, subject={subject}, session={session}"
            );
            assert_eq!(store.load().unwrap().is_some(), accepted);
            if accepted {
                assert_eq!(snapshot.profile.unwrap().email_verified, verified);
            }
        }
    }
    #[tokio::test]
    async fn cancellation_fences_late_credential_commit() {
        let store = Arc::new(Store::default());
        let auth = Auth::with_store(store.clone());
        let generation = auth.begin();
        auth.cancel();
        let snapshot = auth
            .commit(generation, credentials(), profile(), true)
            .await;
        assert_eq!(snapshot.status, "guest");
        assert!(store.load().unwrap().is_none());
        assert!(auth.inner.lock().unwrap().credentials.is_none());
    }
    #[tokio::test]
    async fn switch_fences_old_login_and_snapshot_never_contains_tokens() {
        let store = Arc::new(Store::default());
        let auth = Auth::with_store(store.clone());
        let old = auth.begin();
        let current = auth.begin();
        auth.commit(old, credentials(), profile(), true).await;
        assert!(store.load().unwrap().is_none());
        let snapshot = auth.commit(current, credentials(), profile(), true).await;
        assert_eq!(snapshot.status, "authenticated");
        assert!(snapshot.persistent);
        let json = serde_json::to_string(&snapshot).unwrap();
        assert!(!json.contains("secret-"));
        assert!(!json.contains("refresh"));
    }
    #[tokio::test]
    async fn keychain_refusal_requires_explicit_memory_only_choice() {
        let store = Arc::new(Store::default());
        store.fail_write.store(true, Ordering::SeqCst);
        let auth = Auth::with_store(store);
        let generation = auth.begin();
        let snapshot = auth
            .commit(generation, credentials(), profile(), true)
            .await;
        assert_eq!(snapshot.error_code, Some("credential_storage_failed"));
        assert_ne!(snapshot.status, "authenticated");
        let generation = auth.begin();
        let snapshot = auth
            .commit(generation, credentials(), profile(), false)
            .await;
        assert_eq!(snapshot.status, "authenticated");
        assert!(!snapshot.persistent);
    }
    #[tokio::test]
    async fn deletion_failure_denies_restart_restore_and_reports_cleanup() {
        let store = Arc::new(Store::default());
        let auth = Auth::with_store(store.clone());
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        store.fail_delete.store(true, Ordering::SeqCst);
        let snapshot = auth.logout().await;
        assert_eq!(snapshot.status, "guest");
        assert_eq!(snapshot.error_code, Some("credential_cleanup_failed"));
        assert!(store.load().unwrap().is_none());
    }
    #[tokio::test]
    async fn dual_cleanup_failure_reports_possible_restart_restore() {
        let store = Arc::new(Store::default());
        let auth = Auth::with_store(store.clone());
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        store.fail_block.store(true, Ordering::SeqCst);
        store.fail_delete.store(true, Ordering::SeqCst);
        let snapshot = auth.logout().await;
        assert_eq!(snapshot.status, "guest");
        assert_eq!(snapshot.error_code, Some("credential_invalidation_failed"));
        assert!(snapshot.message.unwrap().contains("可能"));
        assert!(!snapshot.message.unwrap().contains("自动恢复已禁用"));
        assert!(store.load().unwrap().is_some());
        assert!(auth.inner.lock().unwrap().credentials.is_none());
        // A retry that removes the OS credential also makes restore impossible,
        // even when the marker filesystem remains unavailable.
        store.fail_delete.store(false, Ordering::SeqCst);
        let retry = auth.logout().await;
        assert_eq!(retry.error_code, Some("credential_cleanup_failed"));
        assert!(!retry.message.unwrap().contains("可能"));
        assert!(store.load().unwrap().is_none());
    }
    #[tokio::test]
    async fn recoverable_api_error_keeps_current_credentials() {
        let auth = Auth::with_store(Arc::new(Store::default()));
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), false)
            .await;
        let snapshot = auth.fail(generation, "recent_auth_required", "authenticated");
        assert_eq!(snapshot.profile, Some(profile()));
        assert!(auth.inner.lock().unwrap().credentials.is_some());
    }
    #[tokio::test]
    async fn stale_cleanup_cannot_delete_replacement_credentials() {
        let store = Arc::new(Store::default());
        let auth = Auth::with_store(store.clone());
        let old = auth.begin();
        let current = auth.begin();
        auth.commit(current, credentials(), profile(), true).await;
        auth.delete_generation(old).await.unwrap();
        assert!(store.load().unwrap().is_some());
    }
    #[tokio::test]
    async fn expired_family_never_becomes_authenticated() {
        let auth = Auth::with_store(Arc::new(Store::default()));
        let generation = auth.begin();
        let mut expired = credentials();
        expired.family_expires = now() - 1;
        let snapshot = auth.commit(generation, expired, profile(), false).await;
        assert_eq!(snapshot.status, "reauth_required");
        assert!(auth.inner.lock().unwrap().credentials.is_none());
    }

    #[tokio::test]
    async fn cancel_during_os_write_cannot_activate_or_retain_late_credentials() {
        struct BlockingStore {
            base: Store,
            started: std::sync::mpsc::Sender<()>,
            release: Arc<(Mutex<bool>, std::sync::Condvar)>,
        }
        impl CredentialStore for BlockingStore {
            fn load(&self) -> Result<Option<StoredCredentials>, &'static str> {
                self.base.load()
            }
            fn write(&self, c: &StoredCredentials) -> Result<(), &'static str> {
                let _ = self.started.send(());
                let (lock, cv) = &*self.release;
                let mut ready = lock.lock().unwrap();
                while !*ready {
                    ready = cv.wait(ready).unwrap();
                }
                self.base.write(c)
            }
            fn activate(&self) -> Result<(), &'static str> {
                self.base.activate()
            }
            fn block(&self) -> Result<(), &'static str> {
                self.base.block()
            }
            fn delete(&self) -> Result<(), &'static str> {
                self.base.delete()
            }
        }
        let (tx, rx) = std::sync::mpsc::channel();
        let release = Arc::new((Mutex::new(false), std::sync::Condvar::new()));
        let store = Arc::new(BlockingStore {
            base: Store::default(),
            started: tx,
            release: release.clone(),
        });
        let auth = Auth::with_store(store.clone());
        let generation = auth.begin();
        let task_auth = auth.clone();
        let pending = tokio::spawn(async move {
            task_auth
                .commit(generation, credentials(), profile(), true)
                .await
        });
        tokio::task::spawn_blocking(move || rx.recv().unwrap())
            .await
            .unwrap();
        let before = std::time::Instant::now();
        assert_eq!(auth.cancel().status, "guest");
        assert!(before.elapsed() < Duration::from_millis(100));
        let (lock, cv) = &*release;
        *lock.lock().unwrap() = true;
        cv.notify_all();
        assert_eq!(pending.await.unwrap().status, "guest");
        assert!(store.load().unwrap().is_none());
        assert!(store.base.saved.lock().unwrap().is_none());
    }
}

#[cfg(test)]
mod live_tests {
    use super::*;
    use std::collections::HashMap;
    fn merge_cookies(response: &reqwest::Response, cookies: &mut HashMap<String, String>) {
        for header in response.headers().get_all(reqwest::header::SET_COOKIE) {
            if let Ok(value) = header.to_str() {
                if let Some((name, value)) = value
                    .split(';')
                    .next()
                    .and_then(|part| part.split_once('='))
                {
                    cookies.insert(name.into(), value.into());
                }
            }
        }
    }
    async fn browser(mut url: url::Url, fixture: serde_json::Value) -> Result<(), &'static str> {
        let http = reqwest::Client::builder()
            .no_proxy()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|_| "browser client")?;
        let issuer = url.origin().ascii_serialization();
        let mut cookies = HashMap::new();
        for _ in 0..12 {
            let cookie = cookies
                .iter()
                .map(|(k, v)| format!("{k}={v}"))
                .collect::<Vec<_>>()
                .join("; ");
            let mut response = http
                .get(url.clone())
                .header(reqwest::header::COOKIE, cookie)
                .send()
                .await
                .map_err(|_| "browser get")?;
            merge_cookies(&response, &mut cookies);
            if url.host_str() == Some("127.0.0.1") && url.path() == "/oauth/callback" {
                return if response.status() == 200 {
                    Ok(())
                } else {
                    Err("callback rejected")
                };
            }
            if response.status() == 200 && url.path() == "/login" {
                let html = response.text().await.map_err(|_| "login page")?;
                let csrf = html
                    .split("name=\"csrfmiddlewaretoken\" value=\"")
                    .nth(1)
                    .and_then(|s| s.split('"').next())
                    .ok_or("missing csrf")?;
                let next = url
                    .query_pairs()
                    .find(|(key, _)| key == "next")
                    .map(|(_, v)| v.into_owned())
                    .unwrap_or_else(|| "/".into());
                let cookie = cookies
                    .iter()
                    .map(|(k, v)| format!("{k}={v}"))
                    .collect::<Vec<_>>()
                    .join("; ");
                response = http
                    .post(url.clone())
                    .header(reqwest::header::COOKIE, cookie)
                    .header(reqwest::header::REFERER, format!("{issuer}/login"))
                    .form(&[
                        ("email", fixture["email"].as_str().ok_or("fixture email")?),
                        (
                            "password",
                            fixture["password"].as_str().ok_or("fixture password")?,
                        ),
                        ("csrfmiddlewaretoken", csrf),
                        ("next", &next),
                    ])
                    .send()
                    .await
                    .map_err(|_| "browser login")?;
                merge_cookies(&response, &mut cookies);
            }
            if !response.status().is_redirection() {
                return Err("unexpected browser response");
            }
            let location = response
                .headers()
                .get(reqwest::header::LOCATION)
                .and_then(|s| s.to_str().ok())
                .ok_or("redirect missing")?;
            let target = url.join(location).map_err(|_| "bad redirect")?;
            if target.origin() != url::Url::parse(&issuer).map_err(|_| "issuer")?.origin()
                && !(target.host_str() == Some("127.0.0.1") && target.path() == "/oauth/callback")
            {
                return Err("browser escaped issuer");
            }
            url = target;
        }
        Err("too many redirects")
    }
    async fn login(
        auth: &Auth,
        fixture: &serde_json::Value,
        persistent: bool,
        switch: bool,
    ) -> Snapshot {
        let (tx, rx) = tokio::sync::oneshot::channel();
        let (snapshot, browser_result) = tokio::join!(
            auth.login_with_opener(!persistent, switch, move |url| tx
                .send(url.clone())
                .map_err(|_| "browser_unavailable")),
            async {
                let url = rx.await.map_err(|_| "missing authorization url")?;
                browser(url, fixture.clone()).await
            }
        );
        assert_eq!(browser_result, Ok(()));
        assert_eq!(
            snapshot.status, "authenticated",
            "snapshot code: {:?}",
            snapshot.error_code
        );
        snapshot
    }
    // Real service, passwords, PKCE, signatures, callback and rotating sessions;
    // injected HTTP browser and in-memory credential store deliberately exclude OS/UI proof.
    #[tokio::test]
    #[ignore = "requires isolated managed service and private TITAN_MANAGED_NATIVE_FIXTURE; memory store only"]
    async fn local_managed_service_memory_store_roundtrip() {
        let fixture: serde_json::Value = serde_json::from_slice(
            &std::fs::read(
                std::env::var("TITAN_MANAGED_NATIVE_FIXTURE").expect("managed fixture path"),
            )
            .expect("managed fixture read"),
        )
        .expect("managed fixture JSON");
        let network = Network::new(
            Config::parse(
                fixture["issuer"].as_str().expect("managed fixture issuer"),
                true,
            )
            .expect("managed issuer policy"),
        )
        .expect("managed network");
        let store = Arc::new(super::tests::Store::default());
        let auth = Auth::create(store.clone(), Some(network.clone()), "guest");
        let snapshot = login(&auth, &fixture, true, false).await;
        let profile = snapshot.profile.as_ref().expect("authenticated profile");
        assert!(profile.id == fixture["id"].as_str().expect("managed fixture subject"));
        assert!(!profile.email_verified);
        assert!(profile.administrator_approved);
        assert!(snapshot.persistent);
        assert!(store.load().unwrap().is_some());
        let updated = auth
            .update_profile("Managed Native Protocol Test".into())
            .await;
        assert_eq!(updated.status, "authenticated");
        let profile = updated.profile.as_ref().unwrap();
        assert_eq!(profile.name, "Managed Native Protocol Test");
        assert!(!profile.email_verified);
        assert!(profile.administrator_approved);
        assert!(auth
            .sessions()
            .await
            .unwrap()
            .iter()
            .any(|s| s.current && s.id == profile.session_id));
        let previous = auth.inner.lock().unwrap().credentials.clone().unwrap();
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access_expires = 0;
        let (first, second) = tokio::join!(auth.status(), auth.status());
        for snapshot in [first, second] {
            assert_eq!(
                snapshot.status, "authenticated",
                "refresh code {:?}",
                snapshot.error_code
            );
            assert!(!snapshot.profile.as_ref().unwrap().email_verified);
            assert!(snapshot.profile.as_ref().unwrap().administrator_approved);
        }
        let refreshed = auth.inner.lock().unwrap().credentials.clone().unwrap();
        assert!(refreshed.refresh != previous.refresh);
        assert_eq!(refreshed.family_expires, previous.family_expires);
        drop(auth);
        let restored = Auth::create(store.clone(), Some(network.clone()), "guest");
        let snapshot = restored.status().await;
        assert_eq!(
            snapshot.status, "authenticated",
            "restore code {:?}",
            snapshot.error_code
        );
        assert!(snapshot.persistent);
        assert!(!snapshot.profile.as_ref().unwrap().email_verified);
        assert!(snapshot.profile.as_ref().unwrap().administrator_approved);
        let other = Auth::create(
            Arc::new(super::tests::Store::default()),
            Some(network.clone()),
            "guest",
        );
        let other_snapshot = login(&other, &fixture, false, false).await;
        let other_id = other_snapshot.profile.unwrap().session_id;
        assert!(restored
            .sessions()
            .await
            .unwrap()
            .iter()
            .any(|s| !s.current && s.id == other_id));
        assert_eq!(
            restored.revoke_session(other_id).await.status,
            "authenticated"
        );
        assert_eq!(other.status().await.status, "reauth_required");
        let before_logout = restored.inner.lock().unwrap().credentials.clone().unwrap();
        assert_eq!(restored.logout().await.status, "guest");
        assert!(store.load().unwrap().is_none());
        assert!(restored.inner.lock().unwrap().credentials.is_none());
        // Local fencing returns immediately; server revocation is deliberately asynchronous.
        tokio::time::timeout(Duration::from_secs(5), async {
            loop {
                match network.profile(&before_logout).await {
                    Err("unauthorized") => break,
                    Ok(_) => tokio::time::sleep(Duration::from_millis(250)).await,
                    Err(code) => panic!("unexpected logout revocation response: {code}"),
                }
            }
        })
        .await
        .expect("server confirmed asynchronous logout revocation");
        let snapshot = login(&restored, &fixture, true, false).await;
        assert!(!snapshot.profile.as_ref().unwrap().email_verified);
        login(&other, &fixture, false, false).await;
        assert_eq!(restored.revoke_all().await.status, "guest");
        assert!(store.load().unwrap().is_none());
        assert_eq!(other.status().await.status, "reauth_required");
    }
    #[tokio::test]
    #[ignore = "requires isolated local service, private TITAN_NATIVE_FIXTURE and macOS/Windows credential store"]
    async fn local_service_full_roundtrip() {
        let fixture: serde_json::Value = serde_json::from_slice(
            &std::fs::read(std::env::var("TITAN_NATIVE_FIXTURE").expect("fixture path"))
                .expect("fixture read"),
        )
        .expect("fixture JSON");
        let network = Network::new(Config::parse("http://127.0.0.1:8000", true).unwrap()).unwrap();
        let auth = Auth::create(
            Arc::new(super::tests::Store::default()),
            Some(network.clone()),
            "guest",
        );
        let snapshot = login(&auth, &fixture, false, false).await;
        assert!(!snapshot.persistent);
        assert_eq!(
            snapshot.profile.as_ref().unwrap().id,
            fixture["id"].as_str().unwrap()
        );
        let updated = auth
            .update_profile("Native Integration Verified".into())
            .await;
        assert_eq!(updated.profile.unwrap().name, "Native Integration Verified");
        let sessions = auth.sessions().await.unwrap();
        assert!(sessions
            .iter()
            .any(|s| s.current && s.id == snapshot.profile.as_ref().unwrap().session_id));
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access_expires = 0;
        let (first, second) = tokio::join!(auth.status(), auth.status());
        assert_eq!(
            first.status, "authenticated",
            "refresh: {:?}",
            first.error_code
        );
        assert_eq!(
            second.status, "authenticated",
            "concurrent refresh: {:?}",
            second.error_code
        );
        let valid = auth.inner.lock().unwrap().credentials.clone().unwrap();
        let unavailable = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = unavailable.local_addr().unwrap().port();
        drop(unavailable);
        let offline = Auth::create(
            Arc::new(super::tests::Store::default()),
            Some(
                Network::new(Config::parse(&format!("http://127.0.0.1:{port}"), true).unwrap())
                    .unwrap(),
            ),
            "guest",
        );
        let generation = offline.begin();
        offline
            .commit(generation, valid.clone(), first.profile.unwrap(), false)
            .await;
        let snapshot = offline.status().await;
        assert_eq!(snapshot.status, "offline");
        assert!(snapshot.profile.is_some());
        assert!(offline.inner.lock().unwrap().credentials.is_some());
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access = zeroize::Zeroizing::new("invalid-access-token".into());
        let snapshot = auth.status().await;
        assert_eq!(snapshot.status, "reauth_required");
        assert_eq!(snapshot.error_code, Some("unauthorized"));
        assert!(snapshot.profile.is_none());
        network.revoke(&valid).await;
        let root =
            std::env::temp_dir().join(format!("titan-native-keychain-{}", uuid::Uuid::new_v4()));
        let isolated_issuer = format!("isolated-native-test:{}", uuid::Uuid::new_v4());
        let store = Arc::new(
            OsStore::new(root.clone(), "com.titan.native-test", &isolated_issuer).unwrap(),
        );
        let persistent = Auth::create(store.clone(), Some(network.clone()), "guest");
        let snapshot = login(&persistent, &fixture, true, true).await;
        assert!(snapshot.persistent);
        assert!(store.load().unwrap().is_some());
        drop(persistent);
        drop(store);
        let store = Arc::new(
            OsStore::new(root.clone(), "com.titan.native-test", &isolated_issuer).unwrap(),
        );
        let restored = Auth::create(store.clone(), Some(network), "guest");
        let snapshot = restored.status().await;
        assert_eq!(
            snapshot.status, "authenticated",
            "restore: {:?}",
            snapshot.error_code
        );
        assert!(snapshot.persistent);
        let snapshot = restored.revoke_all().await;
        assert_eq!(
            snapshot.status, "guest",
            "revoke all: {:?}",
            snapshot.error_code
        );
        assert!(store.load().unwrap().is_none());
        let _ = store.delete();
        drop(restored);
        drop(store);
        std::fs::remove_dir_all(root).unwrap();
    }
}

#[cfg(test)]
mod transport_tests {
    use super::tests::{credentials, profile, Store};
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    async fn issuer(
        drop_refresh: bool,
        fail_second_discovery: bool,
    ) -> (
        Network,
        Arc<AtomicUsize>,
        Arc<AtomicUsize>,
        tokio::task::JoinHandle<()>,
    ) {
        issuer_with_profile(
            drop_refresh,
            fail_second_discovery,
            serde_json::to_value(profile()).unwrap(),
        )
        .await
    }
    async fn issuer_with_profile(
        drop_refresh: bool,
        fail_second_discovery: bool,
        response_profile: serde_json::Value,
    ) -> (
        Network,
        Arc<AtomicUsize>,
        Arc<AtomicUsize>,
        tokio::task::JoinHandle<()>,
    ) {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let config = Config::parse(&base, true).unwrap();
        let count = Arc::new(AtomicUsize::new(0));
        let calls = count.clone();
        let discovery_count = Arc::new(AtomicUsize::new(0));
        let discovery_calls = discovery_count.clone();
        let task = tokio::spawn(async move {
            loop {
                let Ok((mut socket, _)) = listener.accept().await else {
                    return;
                };
                let base = base.clone();
                let calls = calls.clone();
                let discovery_calls = discovery_calls.clone();
                let response_profile = response_profile.clone();
                tokio::spawn(async move {
                    let mut raw = Vec::new();
                    loop {
                        let mut buf = [0u8; 1024];
                        let n = socket.read(&mut buf).await.unwrap_or(0);
                        if n == 0 {
                            return;
                        }
                        raw.extend_from_slice(&buf[..n]);
                        if raw.len() > 16384 {
                            return;
                        }
                        if let Some(pos) = raw.windows(4).position(|w| w == b"\r\n\r\n") {
                            let head = String::from_utf8_lossy(&raw[..pos]);
                            let length = head
                                .lines()
                                .find_map(|line| {
                                    line.to_ascii_lowercase()
                                        .strip_prefix("content-length:")
                                        .and_then(|s| s.trim().parse::<usize>().ok())
                                })
                                .unwrap_or(0);
                            if raw.len() >= pos + 4 + length {
                                break;
                            }
                        }
                    }
                    let raw = String::from_utf8(raw).unwrap();
                    let path = raw.split(' ').nth(1).unwrap_or("");
                    if path == "/.well-known/openid-configuration"
                        && discovery_calls.fetch_add(1, Ordering::SeqCst) > 0
                        && fail_second_discovery
                    {
                        return;
                    }
                    let body=match path {
    "/.well-known/openid-configuration"=>serde_json::json!({"issuer":base,"authorization_endpoint":format!("{base}/o/authorize/"),"token_endpoint":format!("{base}/o/token/"),"jwks_uri":format!("{base}/jwks"),"response_types_supported":["code"],"subject_types_supported":["public"],"id_token_signing_alg_values_supported":["RS256"],"code_challenge_methods_supported":["S256"]}).to_string(),
    "/jwks"=>"{\"keys\":[]}".into(),
    "/o/token/"=>{calls.fetch_add(1,Ordering::SeqCst);if drop_refresh{return;}tokio::time::sleep(Duration::from_millis(30)).await;serde_json::json!({"access_token":"new-access","refresh_token":"new-refresh","expires_in":600,"token_type":"Bearer","refresh_expires_in":900,"session_id":"s1"}).to_string()},
    "/api/v1/me"=>response_profile.to_string(),_=>"null".into(),
   };
                    let response=format!("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",body.len());
                    let _ = socket.write_all(response.as_bytes()).await;
                });
            }
        });
        (Network::new(config).unwrap(), count, discovery_count, task)
    }
    #[tokio::test]
    async fn profile_update_rejects_unapproved_unverified_response() {
        let mut value = serde_json::to_value(profile()).unwrap();
        value["emailVerified"] = serde_json::json!(false);
        value["administratorApproved"] = serde_json::json!(false);
        let (network, _, _, server) = issuer_with_profile(false, false, value).await;
        let auth = Auth::create(Arc::new(Store::default()), Some(network), "guest");
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), false)
            .await;
        let result = auth.update_profile("New Name".into()).await;
        assert_eq!(result.status, "reauth_required");
        assert!(result.profile.is_none());
        server.abort();
    }
    #[tokio::test]
    async fn older_profile_without_approval_defaults_to_email_verification() {
        for (verified, accepted) in [(false, false), (true, true)] {
            let mut value = serde_json::to_value(profile()).unwrap();
            value
                .as_object_mut()
                .unwrap()
                .remove("administratorApproved");
            value["emailVerified"] = serde_json::json!(verified);
            let (network, _, _, server) = issuer_with_profile(false, false, value).await;
            let result = network.profile(&credentials()).await;
            assert_eq!(result.is_ok(), accepted);
            if let Ok(profile) = result {
                assert!(!profile.administrator_approved);
            }
            server.abort();
        }
    }
    // A trusted API profile still must match this token's subject/session and eligibility.
    #[tokio::test]
    async fn managed_profiles_guard_network_status_and_updates() {
        for (flag, verified, subject, session, expected) in [
            (serde_json::json!(true), false, "u1", "s1", Ok(())),
            (
                serde_json::json!(false),
                false,
                "u1",
                "s1",
                Err("invalid_id_token"),
            ),
            (
                serde_json::json!(true),
                false,
                "other",
                "s1",
                Err("invalid_id_token"),
            ),
            (
                serde_json::json!(true),
                false,
                "u1",
                "other",
                Err("invalid_id_token"),
            ),
            (
                serde_json::json!("true"),
                false,
                "u1",
                "s1",
                Err("invalid_response"),
            ),
            (
                serde_json::Value::Null,
                false,
                "u1",
                "s1",
                Err("invalid_response"),
            ),
        ] {
            let mut value = serde_json::to_value(profile()).unwrap();
            value["emailVerified"] = serde_json::json!(verified);
            value["administratorApproved"] = flag;
            value["id"] = serde_json::json!(subject);
            value["sessionId"] = serde_json::json!(session);
            let (network, _, _, server) = issuer_with_profile(false, false, value).await;
            assert_eq!(network.profile(&credentials()).await.map(|_| ()), expected);
            for update in [false, true] {
                let auth = Auth::create(Arc::new(Store::default()), Some(network.clone()), "guest");
                let generation = auth.begin();
                auth.commit(generation, credentials(), profile(), false)
                    .await;
                let result = if update {
                    auth.update_profile("New Name".into()).await
                } else {
                    auth.status().await
                };
                if expected.is_ok() {
                    assert_eq!(result.status, "authenticated");
                    assert!(!result.profile.unwrap().email_verified);
                } else {
                    assert_ne!(
                        result.status, "authenticated",
                        "update={update}, expected={expected:?}"
                    );
                    assert!(result.profile.is_none());
                }
            }
            server.abort();
        }
    }
    #[tokio::test]
    async fn managed_profile_refresh_and_restore_keep_real_verification_state() {
        let mut value = serde_json::to_value(profile()).unwrap();
        value["emailVerified"] = serde_json::json!(false);
        value["administratorApproved"] = serde_json::json!(true);
        let (network, posts, _, server) = issuer_with_profile(false, false, value).await;
        let store = Arc::new(Store::default());
        let auth = Auth::create(store.clone(), Some(network.clone()), "guest");
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        drop(auth);
        let restored = Auth::create(store.clone(), Some(network), "guest");
        let result = restored.status().await;
        assert_eq!(result.status, "authenticated", "{:?}", result.error_code);
        assert!(!result.profile.unwrap().email_verified);
        assert_eq!(posts.load(Ordering::SeqCst), 1);
        assert_eq!(store.load().unwrap().unwrap().refresh, "new-refresh");
        server.abort();
    }
    #[tokio::test]
    async fn authorization_request_carries_native_device_metadata() {
        let (network, _, _, server) = issuer(false, false).await;
        let login = network.prepare(47991, false).await.unwrap();
        let query: std::collections::HashMap<_, _> = login.url.query_pairs().into_owned().collect();
        let (platform, label) = if cfg!(target_os = "macos") {
            ("macos", "Titan on macOS")
        } else if cfg!(target_os = "windows") {
            ("windows", "Titan on Windows")
        } else if cfg!(target_os = "linux") {
            ("linux", "Titan on Linux")
        } else {
            ("desktop", "Titan Desktop")
        };
        assert_eq!(
            query.get("device_platform").map(String::as_str),
            Some(platform)
        );
        assert_eq!(query.get("device_label").map(String::as_str), Some(label));
        server.abort();
    }
    #[tokio::test]
    async fn concurrent_refresh_posts_once_and_keeps_rotated_descendant() {
        let (network, count, _, server) = issuer(false, false).await;
        let store = Arc::new(Store::default());
        let auth = Auth::create(store.clone(), Some(network), "guest");
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access_expires = 0;
        let (a, b, c) = tokio::join!(auth.status(), auth.status(), auth.status());
        for result in [a, b, c] {
            assert_eq!(
                result.status, "authenticated",
                "code {:?}",
                result.error_code
            );
        }
        assert_eq!(count.load(Ordering::SeqCst), 1);
        assert_eq!(store.load().unwrap().unwrap().refresh, "new-refresh");
        server.abort();
    }
    #[tokio::test]
    async fn lost_refresh_response_is_never_retried_or_restored() {
        let (network, count, _, server) = issuer(true, false).await;
        let store = Arc::new(Store::default());
        let auth = Auth::create(store.clone(), Some(network), "guest");
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access_expires = 0;
        let result = auth.status().await;
        assert_eq!(result.status, "reauth_required");
        assert_eq!(result.error_code, Some("refresh_ambiguous"));
        assert!(store.load().unwrap().is_none());
        assert_eq!(auth.status().await.status, "reauth_required");
        assert_eq!(count.load(Ordering::SeqCst), 1);
        server.abort();
    }
    #[tokio::test]
    async fn refresh_uses_successful_discovery_once_without_second_preflight() {
        let (network, posts, discoveries, server) = issuer(false, true).await;
        let store = Arc::new(Store::default());
        let auth = Auth::create(store.clone(), Some(network), "guest");
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access_expires = 0;
        let snapshot = auth.status().await;
        assert_eq!(snapshot.status, "authenticated");
        assert_eq!(discoveries.load(Ordering::SeqCst), 1);
        assert_eq!(posts.load(Ordering::SeqCst), 1);
        assert_eq!(store.load().unwrap().unwrap().refresh, "new-refresh");
        server.abort();
    }
    #[tokio::test]
    async fn pre_consumption_discovery_failure_preserves_offline_refresh_credentials() {
        let (network, posts, discoveries, server) = issuer(false, true).await;
        network.discover().await.unwrap();
        let store = Arc::new(Store::default());
        let auth = Auth::create(store.clone(), Some(network), "guest");
        let generation = auth.begin();
        auth.commit(generation, credentials(), profile(), true)
            .await;
        auth.inner
            .lock()
            .unwrap()
            .credentials
            .as_mut()
            .unwrap()
            .access_expires = 0;
        let snapshot = auth.status().await;
        assert_eq!(snapshot.status, "offline");
        assert_eq!(snapshot.error_code, Some("network_unavailable"));
        assert!(snapshot.profile.is_some());
        assert!(snapshot.persistent);
        assert_eq!(
            auth.inner
                .lock()
                .unwrap()
                .credentials
                .as_ref()
                .unwrap()
                .refresh
                .as_str(),
            "secret-refresh"
        );
        assert_eq!(store.load().unwrap().unwrap().refresh, "secret-refresh");
        assert_eq!(discoveries.load(Ordering::SeqCst), 2);
        assert_eq!(posts.load(Ordering::SeqCst), 0);
        server.abort();
    }
}

#[cfg(test)]
mod startup_tests {
    use super::*;
    fn config() -> Result<Option<Config>, &'static str> {
        Ok(Some(Config::parse("http://127.0.0.1:9", true).unwrap()))
    }
    #[tokio::test]
    async fn owner_io_failure_allows_guest_science_and_disables_all_account_access() {
        for lock_failure in [false, true] {
            let root =
                std::env::temp_dir().join(format!("titan-guest-start-{}", uuid::Uuid::new_v4()));
            let accounts = root.join("accounts");
            std::fs::create_dir_all(&root).unwrap();
            if lock_failure {
                let owner = OsStore::new(
                    accounts.clone(),
                    "com.titan.startup-test",
                    "http://127.0.0.1:9",
                )
                .unwrap();
                let lock = owner.marker.with_extension("owner");
                drop(owner);
                std::fs::remove_file(&lock).unwrap();
                std::fs::create_dir(lock).unwrap();
            } else {
                std::fs::write(&accounts, b"account-path-is-not-a-directory").unwrap();
            }
            let project = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap();
            // This is the same bundle-construction path consumed by run().setup:
            // Ok contains all three states, which setup immediately manages.
            let result = crate::prepare_startup(
                Auth::from_config(accounts.clone(), "com.titan.startup-test", config()),
                root.join("library"),
                project.join(if cfg!(windows) {
                    ".venv/Scripts/python.exe"
                } else {
                    ".venv/bin/python"
                }),
                vec![project.join("backend/entry.py").into_os_string()],
            );
            assert!(
                result.is_ok(),
                "account-only I/O failure blocked scientific startup"
            );
            let startup = result.unwrap();
            assert_eq!(startup.session.library_root, root.join("library"));
            assert!(!startup.session.token.is_empty());
            let health = startup
                .worker
                .request(serde_json::json!({"command":"health"}))
                .await;
            startup.worker.shutdown().await;
            assert!(
                health.is_ok(),
                "guest scientific engine did not start: {health:?}"
            );
            let auth = startup.auth;
            assert!(auth.network.is_none());
            for snapshot in [
                auth.status().await,
                auth.login(false, false).await,
                auth.login(true, false).await,
                auth.logout().await,
                auth.cancel(),
                auth.update_profile("Ignored".into()).await,
                auth.revoke_all().await,
                auth.revoke_session("00000000-0000-0000-0000-000000000000".into())
                    .await,
            ] {
                assert_eq!(snapshot.status, "unavailable");
                assert_eq!(snapshot.error_code, Some("account_owner_unavailable"));
                assert!(!snapshot.persistent);
                assert!(snapshot.profile.is_none());
            }
            assert!(auth.inner.lock().unwrap().credentials.is_none());
            assert!(auth.sessions().await.is_err());
            assert!(auth.store.load().is_err());
            assert!(auth.store.activate().is_err());
            assert!(auth
                .store
                .write(&StoredCredentials {
                    refresh: "synthetic-not-stored".into(),
                    family_expires: now() + 1000,
                    subject: "synthetic".into(),
                    nonce: "synthetic".into(),
                    session_id: "synthetic".into(),
                })
                .is_err());
            assert!(auth.store.block().is_err());
            assert!(auth.store.delete().is_err());
            if !lock_failure {
                assert_eq!(
                    std::fs::read(&accounts).unwrap(),
                    b"account-path-is-not-a-directory"
                );
            }
            std::fs::remove_dir_all(root).unwrap();
        }
    }
    #[test]
    fn unconfigured_or_invalid_accounts_never_require_a_storage_owner() {
        let root =
            std::env::temp_dir().join(format!("titan-unconfigured-start-{}", uuid::Uuid::new_v4()));
        for (configuration, expected) in [
            (Ok(None), "unconfigured"),
            (Err("invalid_configuration"), "unavailable"),
        ] {
            let auth =
                Auth::from_config(root.clone(), "com.titan.startup-test", configuration).unwrap();
            assert_eq!(auth.snapshot().status, expected);
            assert!(
                !root.exists(),
                "inactive accounts touched their storage directory"
            );
            assert!(auth.network.is_none());
        }
    }
    #[test]
    fn busy_account_owner_still_refuses_duplicate_startup() {
        let root = std::env::temp_dir().join(format!("titan-busy-start-{}", uuid::Uuid::new_v4()));
        let first = Auth::from_config(root.clone(), "com.titan.startup-test", config()).unwrap();
        assert!(matches!(
            Auth::from_config(root.clone(), "com.titan.startup-test", config()),
            Err("account_owner_busy")
        ));
        drop(first);
        std::fs::remove_dir_all(root).unwrap();
    }
}
