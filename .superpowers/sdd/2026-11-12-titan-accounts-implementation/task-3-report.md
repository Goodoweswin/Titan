# Task 3 native authentication bridge — 2026-11-12

Implementation is local, on the managed detached checkout, and consumes the reviewed account service. No deployment, app replacement, science environment changes, project access, branch creation or push was performed. The controller's plan edits are left uncommitted.

## Delivered behavior

- Eight Tauri account commands are registered alongside the existing engine commands. Issuer comes from compile-time `TITAN_ACCOUNTS_ISSUER`; debug builds additionally accept this environment variable at runtime. Missing configuration produces `unconfigured` rather than an invented endpoint. Release builds cannot accept runtime issuer overrides.
- Browser authorization code flow uses the mature `openidconnect`/`oauth2` client, random state and nonce, PKCE S256, the public `titan-desktop` client and `openid profile email`. Account switching requests `prompt=login` and `max_age=0`. The native opener receives only the generated, validated authorization URL.
- Discovery issuer must exactly match the configured issuer. Authorization, token, JWKS, userinfo and optional revocation endpoints must share its origin and contain no credentials, query or fragment. Discovery is validated before JWKS is fetched. HTTP redirects are disabled, with 5-second connection/15-second request timeouts and bounded response bodies.
- A listener binds `127.0.0.1` on an ephemeral port before browser launch. It accepts only GET, exact `/oauth/callback`, exact Host, bounded headers/query, one matching state, a code or error, and an optional exact RFC 9207 issuer. Duplicate, malformed percent/UTF-8, extra, wrong-state and wrong-issuer query data do not consume the login. Overall callback wait is 180 seconds (210 seconds for the complete attempt), individual socket reads are bounded. Cancellation closes the listener and does not wait for browser/network operations.
- ID tokens are validated for RS256 signature, issuer, audience/authorized party, nonce, expiry, issue time and optional `at_hash`. Profile subject/session/verified-email must agree with the authenticated credentials. Initial ID tokens require the nonce. Refresh ID tokens may omit it; if present it must match the original nonce, following OIDC Core 12.2. Refresh ID tokens themselves are optional under that section.
- Only sanitized snapshots/profiles/session rows cross Tauri IPC. No command accepts issuer, URL or token from JS. Access/refresh credentials have no Serialize/Debug implementation, remain native, and use zeroizing secret strings. OS storage contains the rotating refresh credential, original nonce, subject/session binding and absolute family deadline, never an access token. It is scoped by Titan application namespace + issuer + client.
- Refresh uses one in-flight lock and a second check after acquiring it. Native response fields, rotating refresh presence, access lifetime, bounded family lifetime, unchanged session and nonextended original family deadline are checked. A dropped/ambiguous refresh response is never automatically retried; the old credential cannot be restored after restart. API 401 clears authentication; connectivity failure preserves cached profile/credentials with `offline` status. Local guest science behavior does not depend on account availability.
- A nonsecret, issuer-scoped restore-permission marker is removed before logout, switching, login replacement or refresh consumption. It is activated only after OS write success and a final generation fence. Missing/damaged/inaccessible markers deny restore. Keychain refusal never silently falls back to persistence or memory-only mode. Logout reports `credential_cleanup_failed` if removal fails; a successful marker removal prevents restart restoration even when OS deletion is refused.
- Generation checks protect delayed profile/API results, final credential writes and queued credential cleanup; stale cleanup cannot delete the replacement account's credentials. Credential-manager calls run outside the state lock. Logout performs local fencing/cleanup first; server revocation is best-effort in a background task.

## Tauri consumer contract

- `auth_status()`, `auth_login({memoryOnly,switchAccount})`, `auth_cancel()`, `auth_logout()`, `auth_update_profile({name})`, `auth_revoke_session({id})`, `auth_revoke_all()` resolve the shared snapshot `{status,profile,message,persistent,errorCode}`. Async command wrappers use `Result<Snapshot, ()>` for Tauri's lifetime requirement and always resolve their snapshot.
- `auth_login` remains pending for browser callback/exchange/storage; the UI must set its progress state before awaiting it and keep Cancel enabled. `auth_cancel` is independent and synchronous. `auth_status` reports `logging_in` during the attempt; status/API work can queue behind an already-running refresh, so cancellation must call its dedicated command directly.
- `auth_sessions()` resolves the session array, or rejects with a stable code string; it never returns upstream bodies/errors. Representative codes are `unconfigured`, `guest`, `login_in_progress`, `stale_generation`, `network_unavailable`, `unauthorized`, `refresh_ambiguous`, `invalid_response`, `service_unavailable`, `credential_storage_failed`.
- Snapshot action codes additionally include `credential_cleanup_failed`, `recent_auth_required`, `invalid_profile`, `invalid_request`, `invalid_discovery`, `invalid_id_token`, `invalid_token_response`, `browser_unavailable`, `callback_unavailable`, `login_failed`, `login_denied`, `login_cancelled`, `login_timeout`. Branch on `errorCode`; localized Chinese `message` is display-only.
- No new UI or backend files were edited. No global browser login/logout is requested by local logout. Current-session revocation and successful revoke-all clear the local session. Noncurrent session IDs are UUID-validated before constructing the fixed API path.

## RED / GREEN evidence

Normal development REDs (assertion failures, not just compile errors):

1. Standalone callback test against the initial stub: valid code callback returned None; 1 failed/1 passed. Config policy stub: both issuer/endpoint tests failed. Storage scope stub: test failed because distinct issuer namespaces were identical.
2. First Cargo auth run: 9 passed/4 failed, covering valid native-token response, authenticated persistence, explicit Keychain refusal and cleanup-failure reporting. Implementations then passed 13/13.
3. Regression tests for recoverable API errors and stale cleanup failed against their initial implementations, then passed. RFC 9207 callback test first failed, then passed after exact issuer support.
4. Real service integration initially failed with `invalid_id_token` during refresh. Inspection of the actual OAuth library and OIDC Core 12.2 identified the legitimate missing-refresh-nonce case; validation was corrected without accepting mismatched present nonces. Real integration then passed.
5. Added malformed UTF-8 callback input produced `Some(Denied)` instead of rejecting; explicit decoded UTF-8/control validation fixed it. The final full suite below passed.

Separate fault-injection verification (mutations restored immediately; these are not final failures):

- Removing the refresh lock made the HTTP concurrency test fail with 3 refresh POSTs instead of 1.
- Removing the final Keychain generation fence made the cancellation-during-blocked-OS-write test fail by returning `authenticated` instead of `guest`.

Final commands/results:

- `TITAN_NATIVE_FIXTURE=/tmp/titan-native-fixture.json cargo test --manifest-path src-tauri/Cargo.toml --offline -- --include-ignored`: **29 passed, 0 failed, 0 ignored**; main/doc targets also passed. This includes the eight existing Rust tests, 20 isolated auth tests and one real service/OS integration test.
- `cargo check --manifest-path src-tauri/Cargo.toml --offline`: passed. Existing `decode_response` dead-code warning remains outside this task.
- `rustfmt --edition 2021 --check src-tauri/src/auth/*.rs`: passed.
- `git diff --check`: passed.

The real integration test performs CSRF-protected browser-form login against the running Django service/PostgreSQL, actual ephemeral loopback callback, PKCE code exchange, signed OIDC validation, profile edit, session listing, concurrent access refresh, explicit HTTP 401 versus disconnected service handling, switching/forced password form, **real macOS Keychain write/load/delete**, new-client restore/rotation and revoke-all. The opener is injected only to automate the browser HTTP interaction; it does not substitute token responses or cryptographic validation. The test uses an isolated synthetic user and unique test Keychain namespace; it never touches installed Titan or a user's project library. The private fixture file remains mode 0600 outside git for controller review/replay. Its contents, service environment and signing key were never printed or committed.

## Dependencies and boundaries

Locked versions: `openidconnect 4.1.0`, `oauth2 5.0.0`, `keyring 3.6.3`, `reqwest 0.12.28` (rustls, no redirects), `open 5.4.5`, `sha2 0.10.9`, `subtle 2.6.1`, `zeroize 1.9.1`, `url 2.5.8`. `keyring` 3.6.3 was selected deliberately because its documented built-in stores support explicit macOS Keychain, Windows Credential Manager and persistent Linux Secret Service; no unspecified platform may silently use its mock fallback. Cargo uses official registry checksums. An initial direct TLS error was resolved with a per-command local proxy, without disabling TLS verification or editing global Cargo configuration.

Primary sources inspected: [openidconnect 4.1](https://docs.rs/openidconnect/4.1.0/openidconnect/), [keyring 3.6.3 features](https://docs.rs/crate/keyring/3.6.3/features), [keyring platform documentation](https://docs.rs/crate/keyring/3.6.3/source/README.md), [OIDC Core refresh response](https://openid.net/specs/openid-connect-core-1_0.html#RefreshTokenResponse). Downloaded crate source and the live service contract were also inspected.

Not claimed: packaged/signed-app Keychain ACL behavior, actual default-browser GUI launch, user-denied Keychain UI interaction (refusal is injected at the credential-store boundary), Windows/Linux native acceptance, release packaging/notices, public domain/mail/ECS deployment, real email delivery or combined service memory certification. Full product UI/native validation and deployment materials remain controller follow-on tasks. Server revocation on local logout can be unconfirmed while offline; local restore remains blocked. Simultaneous failure of both the local restore-marker filesystem operation and OS deletion is surfaced as cleanup failure; there is no claim of durability through arbitrary filesystem failure or power loss.
