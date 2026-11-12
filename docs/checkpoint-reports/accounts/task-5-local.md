# Account deployment/local evidence — 2026-11-12

Status: local implementation and deployment materials complete for review; **not production deployed**, **current macOS persistent login acceptance NOT PASSED**. No domain/mail/ECS action, real email, registry push or installed-app/user-project change was performed. Controller owns independent whole-branch review. Build instructions and exact operational safeguards are in [deploy/accounts/README.md](../../../deploy/accounts/README.md).

## Delivered

Pinned official Python/PostgreSQL images; hash-locked Python production dependencies; allowlisted Docker build context; separate owner/migrator/runtime roles; startup privilege/config checks; dedicated gateway/database/mail networks and DB volume; optional loopback-only preview; bounded outbox worker and rotating logs; explicit experimental total 384 MiB limits; exact-peer trusted source-address handling; admin-off existing gateway validation/swap/rollback procedure; streaming age encrypted backup/new-DB restore/new epoch; conservative image-only rollback preparation; per-release manifest; independent local launcher; Linux/Windows CI definitions.

The account image's actual registry digest must be supplied after a future build/publish. No arbitrary server commands or default public listener are included. Restore never selects live data; rollback generation never invokes Docker or changes the gateway/DB/epoch. The production app cannot silently use local PG defaults, missing SMTP, wildcard hosts or arbitrary forwarded addresses.

## Measured local verification

Commands used repository `/Users/janus/.codex/worktrees/titan-account-login/Titan`; account-only interpreter `/tmp/titan-accounts-venv/bin/python`, PostgreSQL 17.9. Routine shell cwd mistakes were corrected before the successful commands below; they did not mutate service state. Docker and Podman were unavailable.

| Check | Actual result |
| --- | --- |
| New production/gateway tests before implementation | 24 failed / 7 passed; missing explicit DB/mail/host settings were accepted, unsafe issuer/hosts accepted, middleware absent. |
| New production/gateway tests after implementation | 31 passed in 0.86s. Later empty comma-only trusted peer regression added; focused final **32 passed in 1.03s**. |
| Account suite including new tests | `/tmp/titan-accounts-venv/bin/pytest -q` from `services/accounts`: **94 passed in 11.79s** before the final extra peer-list case. The final extra case was covered by the focused 32-case run, not mislabeled a new full-suite run. |
| Actual runtime role preflight | Production `check --deploy --fail-level WARNING`: no issues (one intentional DOT loopback W008 silence). Cluster administrator rejected. Temporary non-admin role passed, then removed. |
| Separate owner/migrator/runtime SQL bootstrap | Executed exact `init-db.sh` on a disposable 55433 cluster: migrator migrations passed; runtime bootstrap/write and pg_dump passed; runtime CREATE TABLE refused; migrator rejected as runtime. `check --deploy` and runtime preflight passed. This cluster was stopped afterward. |
| Encrypted restore drill | `PATH=/tmp/age:/opt/homebrew/opt/postgresql@17/bin:$PATH PGHOST=127.0.0.1 PGPORT=55432 /tmp/titan-accounts-venv/bin/python deploy/accounts/scripts/rehearse_restore.py --directory /tmp/titan-accounts-restore-drill-2`: passed. age v1.3.2, source and target were both disposable new DBs. User preserved; old access/refresh/code/browser/reset credentials rejected with new epoch; duplicate target refused; source unchanged. Both DBs removed after verification. |
| Restore harness correction | First drill expected reset-link GET to fail; this endpoint deliberately displays a form and validates/consumes on POST. Changed the probe to password POST, cleaned only that first drill's own DBs, reran successfully. No authentication behavior change. |
| Independent local launcher | `python3 deploy/accounts/scripts/local.py init/start/status/stop --directory /tmp/titan-accounts-repro-check` with ports 18081/55433: all passed; actual `/health/ready` HTTP 200. Init used a separate locked venv/private key/epoch/PG cluster; SMTP disabled. Processes stopped. |
| Offline deployment structure | `uv run --no-project --with PyYAML==6.0.3 python deploy/accounts/scripts/check.py`: passed; also parsed both Compose files and CI YAML. This is not `docker compose config` or runtime acceptance. |
| Dependency export consistency | `uv export --project services/accounts --frozen --no-dev --no-emit-project --format requirements-txt --no-header --output-file /tmp/accounts-requirements.txt` then `diff deploy/accounts/requirements.txt /tmp/accounts-requirements.txt`: identical. |
| Rollback scope | Generated release manifest and image override; JSON contained only api/worker image keys. Mismatched migration/dependency-lock digest rejected without output. No Docker/gateway/database action. |
| Source hygiene | Scoped Ruff correctness/import checks and formatter; Python compileall for scripts; sh syntax checks for entrypoint/init-db; `git diff --check`: passed. |

The age executable was fetched from the official FiloSottile/age v1.3.2 release into `/tmp/age`, not installed into shared application environments. Its identity, encrypted fixture and restore epoch remain only in private `/tmp/titan-accounts-restore-drill-2`; temporary old-credential JSON was deleted on success. No secret values or dump contents are included in this report.

Port 8000/PG55432 running service and controller's GUI were not restarted by Task5. The 55432 cluster was used only for the separate uniquely named drill DBs and an explicitly removed non-admin preflight role. The reproducibility cluster on 55433 was independent and is stopped. No dependency was installed into the original Desktop scientific environment.

## Actual native and guest result

See [controller native macOS report](native-macos-2026-11-12.md) for detailed GUI evidence and commands. The isolated ad-hoc DEBUG app used `com.titan.accounts.localcheck`, a private test library and local issuer. Actual Chrome launch, browser CSRF, real loopback callback, explicit memory-only login, profile update and device list worked. Synthetic guest WB quantification, save, export, restart and reopen passed. The controller's integrated science run passed **346 tests + 5 subtests in 29.03s**. Those are engineering checks, not real experimental scientific validation or a notarized release.

Persistent login **did not pass current acceptance**. Actual app Keychain write and a fresh-UUID independent native test both returned `platform_failure`, OSStatus `-25293`; read-only keychain settings inspection also returned an authentication error. A previous Task3 Keychain success is historical only. The underlying system cause is unproven; no Keychain settings/passwords/security controls were changed. Temporary diagnostics and the added direct dependency were removed, restoring reviewed native code exactly. Do not claim production signing/ACL or Windows/native persistence acceptance.

## Gates remaining

- **Production inputs:** approved issuer/domain and DNS, SMTP sender/provider/credentials and real verification/recovery delivery, server/gateway inventory and deployment authorization.
- **Container/server:** actual pinned Docker build, Compose runtime validation, installed Caddy version validation, dedicated peer network and firewall inspection, measured combined cgroup memory/peak/OOM under 384 MiB, host/gateway headroom, load/failure/restore timing.
- **Platform:** current usable macOS Keychain persistent login/restart; production-signed macOS ACL; actual Windows default browser/loopback/Credential Manager/offline/logout/restart. Linux compile jobs are not Linux packaging support.
- **CI:** workflow added, no GitHub run triggered or claimed. Installer build success will still require native user-session acceptance.
- **Review:** independent Task5 and final whole-branch reviews owned by controller; schema compatibility and account image digest must be recorded before a later rollout.
- **Local cleanup:** controller reported the Mac locked; isolated GUI/test-tab cleanup awaits user unlock. Existing installed Titan remains untouched.
