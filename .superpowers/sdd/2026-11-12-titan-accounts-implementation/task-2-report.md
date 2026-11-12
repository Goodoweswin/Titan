# Task 2 — Titan identity service implementation report

Date: 2026-11-12. Status: implemented and verified locally; no ECS deployment, no actual email sent. Worktree: `/Users/janus/.codex/worktrees/titan-account-login/Titan`, based on `7c94478`. Changed only `services/accounts/` and this report. The parent thread's in-progress plan edits were left untouched.

## Delivered

- Independent pinned Django 5.2.19 / Django OAuth Toolkit 3.4.1 / DRF 3.18.3 / psycopg 3.2.13 / Gunicorn 27.0.0 service and `uv.lock`, separate PostgreSQL database and Python environment.
- UUID identity, normalized case-insensitive unique email, framework PBKDF2 passwords, validated nickname; browser registration/login, confirmation/resend/recovery/reset, safe authorization continuation, prompt=login/max_age=0 reauthentication.
- OIDC code + PKCE S256 + RS256, public client `titan-desktop`, exact numeric IPv4 loopback host/path and variable port, identical redemption redirect URI. Scopes limited to openid/profile/email, discovery/JWKS/userinfo/revocation.
- Shared `/api/v1/me`, profile PATCH, session list, own-session DELETE, recent-auth revoke-all contracts. Profile JSON exactly uses id/name/email/createdAt/emailVerified/sessionId. Session JSON exactly uses id/label/platform/createdAt/lastSeenAt/expiresAt/current.
- PostgreSQL-serialized refresh families with 600-second access lifetime and original 30-day absolute deadline. Refresh responses add `session_id` and `refresh_expires_in`, computed from the original family deadline. Replay commits permanent family revocation, including access credentials, before returning invalid_grant.
- User-first transactional lock order across issuance/rotation/recovery; credential fingerprint and externally stored epoch checked for browser/code/link/access/refresh. Admin disabling rotates a framework session-HMAC version so re-enabling cannot revive any old credentials.
- Durable database rate limits by source and account identifier, transactional outbox, bounded retry dispatcher, local-only private-file mailbox retrieval, cleanup preserving replay tombstones, guarded admin route, deterministic bootstrap and setup instructions.

## P0 outcomes and component source findings

| Requirement | Evidence / result |
| --- | --- |
| PKCE S256, public OIDC code flow, RS256 | Real endpoint chain mints tokens; wrong verifier rejected; plain rejected; JWKS validates ID token issuer/audience/nonce/sub/email. |
| Dynamic loopback ports without open redirect | Standard callback works; localhost, suffix domains, wrong path, userinfo, query additions fail; changed port on redemption rejected. |
| Code replay and concurrent exchange | Repeat code rejected; separate PostgreSQL connections yield exactly [200, 400]. |
| Refresh rotation and replay | First rotation changes refresh value; replay invalidates original family and descendant access/refresh. Two concurrent refreshes yield [200, 400], then the one descendant is unusable. |
| Absolute family expiry | Deadline never moves on refresh; expired family cannot refresh even with otherwise live component rows; remaining seconds extension tracks original deadline. |
| Password reset / disable | Reset invalidates existing access, refresh, browser password session and other reset links. Disabled user rejected immediately. Disable→re-enable cannot revive browser, unredeemed code or desktop session. |
| Restore vs restart | New independent SESSION_EPOCH rejects browser, unredeemed code, access and refresh; ordinary client/worker reconstruction with same epoch retains sessions. Actual backup restoration is a later deployment drill. |
| Recovery races | Two separate PostgreSQL consumers of one reset link produce exactly [200, 400]. |
| Fail closed | Database uncertainty produces structured 503 and no usable credentials. |
| Token storage | DOT 3.4.1 defaults to recoverable token columns. Enabled `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE=True`, asserted both access/refresh raw columns are empty and protocol still works. Titan TokenBinding stores SHA-256 digests only. |
| Cleanup replay semantics | DOT can delete revoked refresh rows. Titan preserves independent refresh checksum tombstones until family absolute expiry; replay still revokes descendant after component revoked rows are removed. |
| Local mailbox and mail bounds | Local export requires DEBUG and disabled delivery, writes exclusive 0600 file and no body to stdout; batch cap 50, five attempts, backoff, expired/sent body erasure tested. |

DOT's own refresh lifetime is relative to the paired access expiry; it is not Titan's absolute family deadline. That additional deadline is mandatory in DeviceSession. Authorization codes remain recoverable in the component grant table for 60 seconds. Pending outbox bodies necessarily contain recoverable email links until successful delivery/expiry erasure; only OneTimeToken rows are hashed. Protect DB access and encrypted backups. Never claim all database secrets are hashed.

The HMAC extension uses Django's `salted_hmac` session-auth hook with password hash plus per-user UUID auth_version; cryptography/signing/PKCE/password hashing remain in framework/component code. Disablement uses supported model save/admin paths. Bulk direct database updates bypass model lifecycle hooks and are not a supported disable workflow.

## RED → GREEN evidence

1. Minimal service routes: discovery and anonymous profile each failed 404 versus expected 200/401; after route/protocol implementation, 2/2 passed.
2. First PostgreSQL endpoint run: 4 failed / 9 passed. Expected failures: profile returned 401, unverified authorization incorrectly returned 302, disabled refresh incorrectly returned 200, PATCH lacked name. After session/validator/API implementation, all 13 passed.
3. Lifecycle/concurrency run: 6 failed / 4 passed, missing registration/login/verification/recovery endpoints and outbox effects. Implemented browser flows; complete 23-test suite passed.
4. Continuation/re-auth expansion: 2 failed / 31 passed. max_age=0 incorrectly returned a callback; recovery lost its authorization continuation. Fixed both; 33 passed.
5. Operational expansion: 4 failed / 2 passed: bootstrap/admin/dev-mail missing and database failure escaped as exception. Implemented commands/admin/503 handling. One later test-fixture failure was pytest's default DEBUG=False; made the local-mail test explicitly set DEBUG=True, keeping the production guard intact.
6. Cleanup regression first failed because the command was absent; implemented cleanup with active-family tombstones retained.
7. Final self-review found disable→re-enable could revive an unredeemed code/browser session. A new endpoint regression first failed (200 versus expected 400); added per-user auth_version to Django session HMAC. Final 44-test suite passed.
8. Formatter/import cleanup temporarily removed a side-effect-only test environment import; restored it as an explicit re-export before final rerun. No unresolved failures remain.

Tests were added in behavior batches before their implementations. Initial framework/config/schema scaffolding was needed to run endpoint tests. Some characterization tests already passed on DOT or existing implementation; these are reported as characterization, not fabricated RED cycles.

## Commands and final results

Working directory for commands below: `services/accounts`; environment `/tmp/titan-accounts-venv`, never the repository science `.venv`.

- `UV_PROJECT_ENVIRONMENT=/tmp/titan-accounts-venv uv sync --frozen`: success, locked environment checked.
- `/tmp/titan-accounts-venv/bin/pytest -q`: **44 passed in 8.57s**, actual PostgreSQL 17.9; includes three independent-connection race tests. This is the entire independent account project's bare pytest suite.
- `DJANGO_SETTINGS_MODULE=config.test_settings .../python manage.py makemigrations --check --dry-run`: no changes detected.
- `.../python manage.py migrate --noinput` and `bootstrap_accounts`: applied all framework/component and 3 account migrations to isolated local DB; desktop client created.
- Production-like `ACCOUNTS_DEBUG=0 ACCOUNTS_ISSUER=https://accounts.example.invalid .../python manage.py check --deploy --fail-level WARNING`: no issues, **one intentionally silenced DOT W008**. W008 broadly warns about HTTP redirect URIs; RFC 8252 needs HTTP loopback, and exact host/path/port tests establish the bounded exception. Other initial warnings (implicit/password grants and missing clickjacking middleware) were fixed.
- `uv pip check --python /tmp/titan-accounts-venv/bin/python`: all 46 installed packages compatible.
- `.../pip-audit --progress-spinner off`: no known vulnerabilities. Initial DRF 3.16.1 audit reported five advisories (PYSEC-2026-3827/3828 and CVE-2026-114138/114136/114137); official release notes were checked, dependency upgraded/locked to 3.18.3, audit rerun clean. An initial audit invocation incorrectly supplied --disable-pip without -r; corrected command above succeeded.
- `uvx ruff check . --select E4,E7,E9,F,I --ignore F403`: all checks passed. Formatter applied to account files only. Broad inherited root lint initially reported framework/migration-class and imported-fixture style findings; focused correctness/import check was then used and cleaned.
- `git diff --check`: clean before staging; final staged diff also checked.
- Actual Gunicorn HTTP smoke: `/health/live`, `/health/ready`, `/.well-known/openid-configuration`, `/login`, `/o/.well-known/jwks.json` each 200; discovery issuer exactly `http://127.0.0.1:8000`.
- Actual local PBKDF2-SHA256 benchmark: 1,000,000 iterations, median **67.59 ms** over five hashes on this Mac. No work-factor weakening in tests. This is not an ECS CPU/capacity benchmark.

The parent already verified the preserved product baseline (98 frontend, 346 Python plus 5 subtests, 8 Rust, 6 browser tests). This task did not edit that product code and does not represent those earlier runs as post-integration acceptance.

## Local handoff, no credentials

- Running PostgreSQL: `/tmp/titan-accounts-pg`, bound only to `127.0.0.1:55432`, database `titan_accounts`, current local OS role; local development trust auth only. Homebrew PostgreSQL 17 installed; **no brew services/autostart started**. Homebrew also installed dependencies and ran its ordinary cache cleanup; no existing database was started or altered.
- Stop DB when integration ends: `/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /tmp/titan-accounts-pg stop -m fast`.
- Restart DB: `/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /tmp/titan-accounts-pg -l /tmp/titan-accounts-pg.log -o '-p 55432 -h 127.0.0.1 -c unix_socket_directories=/tmp -c shared_buffers=32MB -c max_connections=20' start`.
- Private dev config: `/tmp/titan-accounts-local/service.env` (0600); signing key is sibling `signing.pem` (0600), directory 0700. Source this file without printing it. No secrets checked in.
- Running Gunicorn: `http://127.0.0.1:8000`, 1 worker / 2 threads. PID file `/tmp/titan-accounts-local/gunicorn.pid`; access log disabled, error log `/tmp/titan-accounts-local/gunicorn-error.log`.
- Stop app: `kill -TERM "$(cat /tmp/titan-accounts-local/gunicorn.pid)"`. Parent will stop both temporary processes after later integration work.
- Test signing key `/tmp/titan-accounts-test-key.pem` is test-only and separate from the running local service.

## Remaining boundaries

No actual browser GUI or native desktop login/credential-store acceptance occurred in Task 2. Windows, Keychain, frontend delayed-response isolation and science regression after integration belong to their respective tasks. No remote server, DNS, mail provider or ECS config was touched. SMTP transport exists but only local backend/failure paths were exercised; no messages sent. Outbox delivery is at-least-once after process crash, while link redemption is single-use.

No container hard-limit measurement, backup/restore drill or combined 384 MiB viability claim is made. Session labels currently use the honest generic `Titan Desktop` / `desktop` because no device metadata protocol was agreed. Behind a proxy source limits conservatively use its REMOTE_ADDR until a trusted source-address mechanism is configured; do not trust arbitrary forwarded-for headers. Admin is off by default and must be restricted to a private management gateway when enabled. Production signing-key rotation with overlapping JWKS keys is not implemented in this first issuer; changing keys requires coordinating a session epoch/key rollover and reauthentication.

Sources inspected: official DOT stable settings/OIDC/changelog, installed DOT 3.4.1 validator/model/view source, official Django password management, official DRF release notes. URLs are recorded in the service README.
