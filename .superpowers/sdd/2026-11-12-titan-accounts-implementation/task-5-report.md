# Task 5 implementer report — 2026-11-12

Base `40ab099`. Scope: local deployment/CI/backup/startup/evidence artifacts, production config/trusted-gateway handling and tests. No remote server/DNS/email/registry push/production deployment/installed Titan or user project change. Controller owns task review, final branch review and native GUI work.

## Implemented

- `deploy/accounts/`: official digest-pinned Python/PostgreSQL build, hash-exported locked requirements and Docker context allowlist; dedicated accounts DB volume/networks; optional loopback preview; API144 + DB160 + worker80 MiB limits; bounded mail worker/heartbeat/log rotation; nonroot readonly app/worker.
- Initial SQL bootstrap separates bootstrap admin, NOLOGIN owner, migrator and runtime. Default grants permit runtime DML/sequences/dump but no schema CREATE. API/worker entrypoints require Django production checks and actual runtime privilege preflight before serving/dispatching.
- Production settings fail closed for missing issuer/secret/key/epoch/allowed host/PG/SMTP/trusted gateway settings. Local DEBUG no-send preserved. Exact-peer middleware accepts only one gateway-replaced client IP and HTTPS, strips arbitrary forwarded headers; Gunicorn blanket proxy trust disabled. Auth lifetimes/protocol/Chinese text unchanged.
- Streamed `pg_dump`→age encrypted backup; checksum manifest; fresh-name-only transactional restore/new random epoch; no implicit service start/promotion/overwrite. Script rejects source/existing DB and existing epoch file. Full local disposable restore drill validates old credentials invalidation.
- Reproducible disposable local launcher, private keys/config/venv/PG ports; explicit stop ownership check; no science environment mutation.
- Existing admin-off Caddy full-config validation/reversible cold-swap procedure and read-only old-product health gates, per-release manifests, conservative image-only rollback override generation (migration + dependency-lock digest must match).
- Linux service/Docker build/audit CI, Windows/Linux native tests/compile, Windows installer build using existing packaging/notices. No CI run triggered.
- Durable reports: `docs/checkpoint-reports/accounts/task-5-local.md` and `native-macos-2026-11-12.md`; full commands/constraints in deployment README.

## Verification

- Deployment tests RED: 24 failed / 7 passed, missing config accepted and middleware absent. GREEN31 passed/0.86s. Whole account suite94 passed/11.79s. Added comma-only empty gateway regression; final focused32 passed/1.03s. Full suite was not rerun solely for the extra single configuration case; report preserves exact scope.
- Actual production checks: Django no warnings (one intentionally silenced DOT W008); cluster admin rejected; temporary non-admin accepted and removed.
- Exact `init-db.sh` on independent55433 cluster: migrator migrations succeeded; runtime bootstrap/DML and pg_dump succeeded; runtime DDL refused; migrator runtime preflight refused. Cluster stopped.
- Actual age1.3.2+PG17.9 restore drill passed. New DB+new epoch preserves synthetic user and rejects old access, refresh, authorization code, browser session and reset POST. Duplicate destination rejected. Source unchanged; own source/target DBs removed after success.
- First drill harness incorrectly expected reset GET to reject; endpoint displays form and validates on POST. Corrected probe, cleaned its own DBs, reran. No product auth fix or silent weakened assertion.
- Independent launcher init/start/health HTTP200/status/stop passed at18081/55433; SMTP disabled; temp cluster stopped. Port8000/55432 controller service not restarted.
- Offline Compose/preview/CI YAML and structural checks passed; lock export identical; rollback output only api/worker image overrides and rejects schema mismatch; scoped Ruff, compileall, shell syntax and git diff check passed.
- Docker/Podman absent: actual image build, compose config, Caddy validate and 384MiB hard-limit viability NOT measured. Production SMTP/server/DNS absent as explicitly deferred inputs.

## Controller native support and evidence

At controller request, added temporary DEBUG-only stage/category/OSStatus diagnostic code with compile-time local logfile and exclusive0600 create (no symlink following, no error object/credential logging), temporarily referencing already locked security-framework3.7.0 on macOS only. Controller built once and observed actual write -25293; freshUUID native integration also failed same OS boundary; read-only keychain info reports authentication failure. Per controller request all diagnostics/file switch/direct dependency and native source changes were restored exactly to reviewed HEAD; no native diff remains.

Controller's actual GUI passed default Chrome launch, CSRF fixed previously in cfbdebf, real loopback callback, explicit memory-only login, profile/device UI, local logout, synthetic WB quantification/save/export/restart/reopen. Integrated scientific tests346 +5subtests/29.03s. Persistent Keychain login/restart current acceptance **NOT PASSED**; historical Task3 success is not current evidence. Cause beyond OS authentication/authorization failure remains unproven; no system security changes attempted. Production signed/notarized macOS and Windows native acceptance pending. Mac later locked; test-window cleanup awaits user unlock.

## Remaining review/release gates

Independent Task5/final branch review; selected domain/SMTP/approved server inventory; actual container/Caddy validation and memory/load/failure evidence; production image digest and operator manifest; actual mail delivery; current macOS persistence and Windows native checks. These are explicit external/platform gates, not reasons to fabricate acceptance or deploy without authorization.

Runtime launcher/restore private evidence lives under `/tmp/titan-accounts-repro-check`, `/tmp/titan-accounts-restore-drill-2` and `/tmp/age`; no secret contents in git. Account venv `/tmp/titan-accounts-venv`; controller moved the isolated science clone into ignored worktree `.venv`, original Desktop environment unchanged. No broad frontend/native suites were repeated by this task.

## Commit

Implementation commit is recorded in the implementer's final handoff and in git history; this report is included in the same scoped commit.
