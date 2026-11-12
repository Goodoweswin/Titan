# Controller native macOS acceptance — 2026-11-12

## Isolated test build
Built an ad-hoc signed DEBUG app from reviewed UI/native code (1c6ccd6), with productName Titan Accounts Test, identifier com.titan.accounts.localcheck, compile-time local issuer http://127.0.0.1:8000 and temporary Tauri override /tmp/titan-accounts-native-check/tauri.check.json. Installed /Applications/Titan.app remained separately running and untouched. Test app used its own Application Support library. This is not a notarized production release. Resources were read from installed engine/notices without modifying them.

The DEBUG engine initially hung when worktree .venv pointed at the Desktop science environment. A byte clone outside Desktop restored access; after restart the app showed 本地引擎就绪. The clone now occupies the ignored worktree .venv directory (~351MiB); original Desktop environment unchanged. No permission/security setting was changed. Cause was not independently proven beyond this environment isolation result.

## Actual GUI evidence (CUA)
- Clicked desktop 登录 / 注册: actual default Chrome launched the local login page, native UI showed waiting/cancel.
- Initial actual browser form submission returned403 Origin:null. Root cause response no-referrer policy; fix cfbdebf changed to same-origin. After cold restart, actual Chrome form login passed CSRF and reached real ephemeral loopback callback. Backend63 tests + scoped review cover fix and continued null/foreign rejection.
- Native persistent login returned credential_storage_failed. Explicit 仅本次登录 then succeeded through actual browser/callback; desktop showed verified synthetic user, memory-only status and real device sessions. Synthetic account only, no real mail/user data.
- Edited nickname and observed confirmed native profile update. Opened all-device logout confirmation, observed cancel initial focus, cancelled successfully. Exited this device; desktop returned guest and accurately said server revocation unconfirmed.
- After local logout, opened synthetic WB demo, completed quantification (24 measurements,11/12 valid target ratios,6 biological units,1 blocked saturated lane), saved /tmp/titan-accounts-native-check/guest-wb.titanwb and exported /tmp/titan-accounts-native-check/guest-results. UI confirmed save/export. Export directory contains results.xlsx, plot.png/plot.svg, CSVs, originals, overlays and audit JSON. This is engineering validation, not real experimental accuracy.
- Quit/restarted isolated app; engine ready, saved analysis and export appeared in independent sidebar; opened saved experiment and observed saved state with24 regions.

## Persistent credential acceptance: NOT PASSED
Temporary DEBUG-only, compile-time-gated diagnostics in a second ad-hoc package reported only `stage=write category=platform_failure os_code=Some(-25293)`. No credentials or full error objects were logged.
A fresh UUID namespace in the independent existing integration test also now fails at OS write with the same -25293:
`TITAN_NATIVE_FIXTURE=/tmp/titan-native-fixture.json cargo test --manifest-path src-tauri/Cargo.toml --offline local_service_full_roundtrip -- --include-ignored` ->1 failed,33 filtered; failure credential_storage_failed/unavailable instead of authenticated. An earlier over-specific test filter matched0 tests and is NOT evidence of success.
Read-only system control `security show-keychain-info /Users/janus/Library/Keychains/login.keychain-db` returns exit51 with SecKeychainCopySettings authentication error. The ordinary local issuer namespace metadata query returned NoEntry, so the observed fresh-write failure is not established as stale-item collision.
Apple defines errSecAuthFailed as authorization/authentication failure: https://developer.apple.com/documentation/security/errsecauthfailed . Current exact OS cause is unproven. No OS/Keychain password or real user password was requested or entered. The actual browser acceptance used a newly seeded synthetic localhost account password. No keychain reset/unlock/settings change, permission weakening or fallback persistence was attempted. Previous Task3 real Keychain success is historical evidence, not final current acceptance.
Temporary diagnostics, file switch and direct dependency were removed by the Task5 implementer; the native files are restored exactly to their reviewed HEAD versions. This report preserves the diagnostic evidence. Current explicit memory-only and guest paths pass. Real persistent-login/restart acceptance must be rerun after the machine's keychain is usable. Windows/Linux native and production-signed macOS ACL acceptance remain pending.

## Other verification
`.venv/bin/python -m pytest -q` after integration and environment isolation:346 passed +5 subtests,29.03s.
Native debug builds succeed; pre-existing Cargo warning `function decode_response is never used` at `src-tauri/src/lib.rs:11:4` and lack of notarization credentials reported.

## Cleanup state
CUA later reported Mac locked and automatic unlock failed, so test app/window cleanup awaits user handoff. Async unlock request sent. No further UI action while locked. Local Chrome test tab IDs:1251376197,1251376200,1251376203,1251376206.

## Final repair wave boundary
The subsequent code repair adds a lifetime process owner for an application/issuer/client/data-root credential namespace and descriptive native platform labels. Its regular Rust/process-boundary, service and frontend tests do not access the OS credential manager. The actual Keychain failure above is unchanged and remains NOT PASSED. No native GUI/desktop interaction, OS/security changes or live-service restart/migration were performed in this repair wave. The new duplicate-startup dialog is compiled but has no new GUI acceptance evidence. The existing unused `decode_response` warning now appears at `src-tauri/src/lib.rs:12:4` after adding a dialog import; the helper itself is unchanged.

## Scoped startup correction
The subsequent scoped review confirmed the original four repairs and identified that account-owner I/O failures incorrectly blocked guest startup. The correction uses an inert unavailable account while continuing the shared scientific startup bundle; only proven duplicate-owner conflicts retain startup refusal. A new non-GUI regression exercises invalid account/lock paths through the same factory as setup and starts its real EngineWorker successfully. Unconfigured accounts no longer touch account storage. This neither changes nor passes the failed Keychain gate above.

The controller has now verified and stopped its local Gunicorn/PostgreSQL test processes, preserving data and private configuration. Future live acceptance requires starting PostgreSQL, applying migration0004 and cold-starting updated service code. Locked-Mac test windows/browser tabs still await user handoff; no native GUI cleanup was performed in this correction.
