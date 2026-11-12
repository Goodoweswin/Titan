# Titan accounts implementation verification — 2026-11-12

Local implementation is complete through the independently reviewed Task 5 commit `e983c2f`. **Current macOS persistent login acceptance has not passed.** The actual memory-only account flow and isolated guest WB save/export/reopen passed. This document records existing evidence; its documentation-only handoff does not rerun code suites or claim a single final all-tests-pass run. Controller whole-branch review remains pending.

No ECS, DNS, production email, registry publication, GitHub push, installed-app replacement or user project change was performed. User explicitly deferred production domain/mail/server work. See the [approved plan](../../superpowers/plans/2026-11-12-titan-accounts-implementation.md), [deployment guide](../../../deploy/accounts/README.md), [Task 5 local evidence](task-5-local.md) and [actual macOS GUI report](native-macos-2026-11-12.md).

## Commit and review history

| Task | Commits | Delivered/reviewed result |
| --- | --- | --- |
| Baseline | `2309e8b` → `7c94478` | Preserved installed 0.4.1 source baseline; imported reviewed account/appearance changes; no scientific engine replacement. |
| Task 2 service | `af2fc14`, `0f80a0b`, `af64fd4` | Independent OIDC/lifecycle service; stale admin credential/state writes repaired; scoped review approved. Reload failure and successful cold restart documented. |
| Task 3 native bridge | `6633678`, `bde1e85` | Native OAuth/OS storage/callback bridge; discovery-refresh classification, signed authorized-party validation and honest dual cleanup failure repaired; scoped review approved. |
| Task 4 UI | `1c6ccd6`, `cfbdebf` | Confirmed profile/device UI and guest-preserving account flows; actual browser CSRF/referrer failure repaired; scoped review approved. |
| Shared handoff | `40ab099` | Reviewed contracts and user-confirmed local-only scope recorded. |
| Task 5 delivery | `e983c2f` | Deployment/configuration/CI/backup/local-launch/evidence materials; scoped review approved. Reviewer requested only more precise documentation of an existing Cargo warning, addressed here without source cleanup. |

The eight public Tauri account commands return sanitized account state; no raw tokens or endpoint input enter React. Access lifetime stays 600 seconds and rotating refresh families retain their original 30-day absolute deadline. No deployment work changed those reviewed contracts.

## Latest recorded evidence by scope

These rows describe different executions and must not be summed into a fictitious unified test result. Task 5 changed service/deployment configuration; unchanged frontend/native suites were not rerun merely to restate success.

| Scope | Command/evidence | Exact recorded result and limit |
| --- | --- | --- |
| Scientific engine after integration | `.venv/bin/python -m pytest -q` | **346 passed + 5 subtests, 29.03s**, controller run after isolating the worktree environment. Synthetic engineering evidence; not real experimental scientific validation. |
| Frontend | `npm test` | **116 passed, 20 files**, Task 4. Includes real local-engine statistics fixtures and new account hook/panel tests. |
| Frontend production build | `npm run build` | Passed at Task 4. Existing font fallback/chunk-size warnings were not treated as failures. |
| Browser regressions | `npm run test:e2e -- tests/browser/account.spec.ts tests/browser/workspace-navigation.spec.ts tests/browser/workspace-chrome.spec.ts tests/browser/appearance.spec.ts` | **28 passed, 57.8s**, Task 4. Account native IPC is mocked in browser tests; actual OS/browser evidence is separate. |
| Regular Rust | `cargo test --manifest-path src-tauri/Cargo.toml --offline` | **33 passed, 1 opt-in test ignored**, Task 4; main/doc targets passed. This does not claim Keychain success. |
| Account service, full suite | `/tmp/titan-accounts-venv/bin/pytest -q` from `services/accounts` | **94 passed, 11.79s**, Task 5 before one final empty trusted-peer-list regression was added. |
| Final production/gateway focused suite | `/tmp/titan-accounts-venv/bin/pytest accounts/tests/test_deployment.py -q` | **32 passed, 1.03s**, includes that final extra case. No subsequent full-suite total is claimed. |
| Production configuration/roles | `check --deploy --fail-level WARNING`, `check_accounts_deployment`, actual SQL bootstrap/migration/permissions exercise | No deployment warnings except the intentionally silenced DOT W008 loopback warning. Runtime DML/bootstrap/dump passed; runtime DDL and administrator/migrator runtime credentials refused. Independent 55433 cluster stopped. |
| Encrypted recovery | `rehearse_restore.py` with PostgreSQL 17.9 and age 1.3.2 | New source/target DBs only; restored user preserved, old access/refresh/code/browser/reset credentials rejected with new epoch, duplicate target refused. Both disposable DBs removed afterward. |
| Local launch | `local.py init/start/status/stop` | Independent 18081/55433 environment and actual readiness HTTP 200; mail disabled; processes stopped. |
| Deployment materials | Offline structure/YAML checks, lock-export diff, image-only rollback scope check, scoped Ruff/compileall/shell syntax/diff checks | Passed. Docker/Podman absent: actual Docker build/Compose/Caddy/cgroup runtime acceptance not performed. CI workflow authored but not run remotely. |
| Actual macOS memory-only/guest | Controller CUA, isolated ad-hoc DEBUG app | Chrome launch, strict-CSRF form, real ephemeral callback, explicit memory-only login, profile update/device list, logout and guest WB quantification/save/export/restart/reopen passed. |
| Current real Keychain persistence | Actual GUI plus fresh-UUID `local_service_full_roundtrip -- --include-ignored` | **NOT PASSED**: write returned OSStatus `-25293`; independent test **1 failed, 33 filtered**. An earlier filter matched zero tests and is not success evidence. |

The exact pre-existing Cargo diagnostic is **`function decode_response is never used`**, at **`src-tauri/src/lib.rs:11:4`** ([source](../../../src-tauri/src/lib.rs)). It predates account changes and was left untouched. Debug package builds also lacked production notarization credentials; these QA bundles are not release artifacts.

## Preserved Task 2 evidence and source map

Task 2's original full account run was **44 passed in 8.57s** on PostgreSQL 17.9. The stale-admin repair added five focused regressions (**5 passed in 1.88s**) and reran the affected lifecycle/operations/concurrency/admin scope (**31 passed in 6.81s**). Later Task 4 and Task 5 results above supersede that earlier whole-suite count; they do not erase its review history.

[OAuth validator](../../../services/accounts/accounts/oauth.py), [models](../../../services/accounts/accounts/models.py), [API](../../../services/accounts/accounts/api.py) and [security](../../../services/accounts/accounts/security.py) implement exact loopback redirects, PKCE S256, RS256, verified users, single-use codes, atomic refresh rotation/replay revocation, fixed absolute family expiry, owner-only session access, password/disable invalidation and restore epoch. [Endpoint tests](../../../services/accounts/accounts/tests/test_endpoints.py), [lifecycle tests](../../../services/accounts/accounts/tests/test_lifecycle.py) and [separate-connection concurrency tests](../../../services/accounts/accounts/tests/test_concurrency.py) preserve those checks.

[Admin repair](../../../services/accounts/accounts/admin.py) writes only explicitly changed fields against locked current state; unchanged stale forms cannot resurrect account activity, credentials or group state. The dedicated password form uses the same current-state rule. [Admin regression tests](../../../services/accounts/accounts/tests/test_admin_concurrency.py) cover those deterministic interleavings; they are distinct from the simultaneous refresh/code/recovery tests.

[Mail/outbox](../../../services/accounts/accounts/mail.py) and [operations tests](../../../services/accounts/accounts/tests/test_operations.py) cover bounded retries, private local mailbox export, replay tombstone retention and service failure behavior. Component token hashing was explicitly enabled: raw access/refresh component columns are empty, while short-lived authorization codes and pending mail links remain recoverable and require protected DB/backups. No assertion that every database secret is hashed is made.

The historical locked-environment/dependency audit reported all 46 packages compatible and no known vulnerabilities after DRF was upgraded to 3.18.3. That is the recorded Task 2 audit, not a fresh security scan today. Local PBKDF2-SHA256 used 1,000,000 iterations, median 67.59ms over five hashes; no work-factor weakening and no target-server capacity conclusion. Gunicorn HUP failed with worker SIGKILL/restarts and readiness timeout; cause was not established. TERM plus cold start restored readiness/discovery HTTP 200. HUP reload is not accepted.

## Preserved Task 3 evidence and source map

[Configuration](../../../src-tauri/src/auth/config.rs), [callback](../../../src-tauri/src/auth/callback.rs), [OIDC/HTTP validation](../../../src-tauri/src/auth/oauth.rs), [client state machine](../../../src-tauri/src/auth/client.rs) and [OS storage](../../../src-tauri/src/auth/storage.rs) contain the corresponding unit/integration tests. The bridge validates exact issuer/origin/endpoints, bounded callback syntax/state/host/path, RS256 signature/audience/authorized party/nonce/time, token response bindings and original family deadline. One refresh lock and generation fences prevent duplicate refresh or delayed login/cleanup from restoring the wrong account. Fault injection removing the refresh lock or final credential-write fence made their tests fail as expected.

Task 3 originally ran **29 passed including real service/macOS Keychain**; after scoped review fixes, the affected native auth run was **25 passed including the real integration, 8 unrelated tests filtered**. These are **historical** results. The integration used real service, PostgreSQL, loopback exchange, signed tokens and OS credential writes; its injected opener automated HTTP browser interaction and was not actual default-browser GUI evidence.

The review repaired discovery-failure classification before refresh consumption, explicit signed `azp` checking and cleanup guarantees. `credential_cleanup_failed` means at least one durable invalidation route succeeded; `credential_invalidation_failed` explicitly warns restart restoration can remain possible if both marker removal and OS deletion fail. No automatic memory-only fallback was added. The callback content-length complaint did not reproduce (34-byte body); deriving length was retained without misreporting it as a reproduced defect.

Current GUI and fresh-namespace OS writes both fail with `-25293`. Read-only Keychain settings inspection returned exit51/authentication error; metadata lookup found no existing issuer item. Exact OS cause is unproven. No password was entered, no keychain reset/unlock/settings adjustment or security weakening was attempted. Temporary strictly redacted debug instrumentation/direct dependency were removed, restoring reviewed native sources. See the [current native report](native-macos-2026-11-12.md); historical Task 3 success cannot satisfy current persistence acceptance.

## Preserved Task 4 evidence and source map

[Typed bridge](../../../src/account-bridge.ts), [hook](../../../src/useAccount.ts), [panel](../../../src/AccountSessionPanel.tsx), [hook tests](../../../src/useAccount.test.ts), [panel tests](../../../src/account-session-panel.test.ts) and [browser tests](../../../tests/browser/account.spec.ts) retain explicit memory-only choice, immediate login/cancel, stale response fencing, confirmed profile/device data, uncertain remote logout notice, all-device confirmation/reauthentication, guest drafts and keyboard isolation. Hook ownership survives dialog close/reopen. Chinese service forms were localized without weakening CSRF/continuation behavior.

Task 4's initial service run was **55 passed**. Actual native Chrome form submission then failed with HTTP403/Origin:null despite simulated suites. Commit `cfbdebf` changed response referrer policy from no-referrer to same-origin. [Strict browser CSRF tests](../../../services/accounts/accounts/tests/test_browser_csrf.py) and [form controls](../../../services/accounts/accounts/tests/test_browser_forms.py) verify same-origin HTTP/HTTPS success, continued null/foreign Origin rejection, and HTTPS Referer checks. The affected run passed **26**, then the full service run passed **63 in 12.25s**. Actual Chrome POST/callback subsequently passed. Frontend/native suites were not repeated for that header-only fix. HTTP403/429 mapping was a narrow approved integration change, not a token/session redesign.

## Decisions preserved from the execution ledger

The following `Ruling:` lines are copied verbatim, in original order, from the execution ledger. Their rationale and cost remain attached. The earlier read-only scientific symlink decision was later superseded by the final clone ruling; the isolated clone now occupies the ignored worktree `.venv`, while the original Desktop environment is unchanged.

Ruling: User's 执行 already authorizes implementation; use sequential subagent implementation without another method approval — routine execution choice — cost if wrong: change workflow on request.

Ruling: Use existing scientific .venv as read-only symlink for baseline tests, independent account environment — missing interpreter caused two initial test failures — cost if wrong: recreate scientific environment if dependency mismatch appears.

Ruling: Task4 may fix the narrow native HTTP API error mapping (429 rate_limited; otherwise-forbidden403) with focused tests — integration revealed the reviewed bridge collapsed them into service_unavailable, conflicting with design §6 — cost if wrong: revert this mapping without changing token/session flows.

Ruling: Extend Task4 narrowly to response Referrer-Policy and CSRF regressions — actual native/browser login fails despite simulated suites; preserve same-origin form provenance while suppressing cross-origin sensitive URLs — cost if wrong: adjust header policy and rerun browser acceptance, without changing CSRF trust rules.

Ruling: Clone the scientific environment for isolated native validation rather than change installed-app Desktop permissions — debug engine hung with the read-only Desktop .venv link; clone outside Desktop made test library/demo work — cost if wrong: ~351MiB temporary workspace disk use, original environment unchanged.

## Pending acceptance and handoff

- **Independent review:** Task 5 scoped review approved; controller's final whole-branch/spec review is still pending at this handoff. No open scoped important finding is being hidden by the documentation commit.
- **macOS persistence:** rerun actual persistent login/rotation/restart once the machine's credential store is usable; current result is failed, not merely untested. Production-signed/notarized Keychain ACL acceptance remains unperformed.
- **Windows/Linux:** actual Windows browser/callback/firewall/Credential Manager/offline/logout/restart acceptance unperformed. Windows/Linux CI tests/build jobs authored but not executed remotely. Linux native platform acceptance and Linux packaging remain unclaimed.
- **Deployment inputs/actions:** approved issuer/domain/DNS, SMTP provider/sender/credentials, real verification/recovery delivery, authorized ECS/gateway inventory and deployment are deferred. Unconfigured desktop builds remain guest-capable; production service configuration fails closed rather than inventing endpoints or silently disabling mail.
- **Runtime capacity and gateway:** actual pinned image build, Compose validation/runtime, installed Caddy version/full-config validation, dedicated peer-network/firewall checks, old-product health checks before/after a future swap, 384MiB combined cgroup peak/OOM/load/failure testing and host/gateway headroom are unperformed. Configured limits are not measurements.
- **Promotion/recovery:** future production image digest, complete operator release manifest, reviewed schema compatibility and restored-role grants, backup key custody/retention/restore duration and new epoch are required before promotion. Local encrypted recovery proof does not certify production operations.
- **Local cleanup:** the controller reported a locked Mac and requested user unlock; isolated test-window/browser-tab cleanup was pending at handoff. No action on installed Titan or its project library was authorized by that cleanup.

Private fixture/config/key paths are intentionally not expanded into values here. Detailed startup commands and evidence boundaries remain in the linked deployment/local/native reports. This handoff changes documentation only; no code suite was rerun for it.
