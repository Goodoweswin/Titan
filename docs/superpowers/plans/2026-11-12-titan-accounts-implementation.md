# Titan Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Implement the approved Titan account lifecycle, desktop browser login, and isolated ECS deployment preparation.
**Architecture:** Django + DRF + OAuth Toolkit provide the independent identity service. Tauri Rust owns OAuth and credentials; React sees only sanitized state. PostgreSQL is isolated from the existing product.
**Tech Stack:** Existing React 19/Tauri 2, Python Django/DRF/DOT, PostgreSQL, Docker Compose.
**Spec:** `docs/superpowers/specs/2026-11-12-titan-accounts-ecs-design.md` (approved by user: 执行).

## Global Constraints

- Preserve the installed 0.4.1 product baseline from `release/account-update-0.4.1`, based on `2309e8b`.
- Browser authorization code + PKCE S256, RS256 ID tokens, public native client, exact loopback host/path with variable port.
- Access lifetime 600 seconds; refresh family absolute lifetime 30 days. Reuse revokes the family, including access tokens.
- No tokens in React, localStorage, project files or logs. No science data uploaded.
- Local guest functionality remains available during every account failure.
- Independent account/database/network names. Existing ECS service must remain untouched. No deployment without concrete authorization.
- Combined new-service experimental memory budget 384 MiB; measure before claiming viability.
- Preserve source working tree edits; no server credentials in git.

## Review Focus

- Delayed responses after account switch/logout must not revive a session (Task 3/4).
- Concurrent refresh/recovery consumption must not mint two live descendants (Task 2 PostgreSQL tests).
- Malformed callback/query/redirect data must not consume a legitimate login (Task 3).
- Server restart and database restore must have explicit session invalidation rules (Task 2/5).
- Guest project drafts and shortcuts must survive opening/closing account UI (Task 4).

## Shared Contracts

The API uses `Authorization: Bearer <opaque access token>` for desktop requests. Browser mutations use Django CSRF and secure host-only sessions.
`GET /api/v1/me` returns `{id,name,email,createdAt,emailVerified,sessionId}`.
`PATCH /api/v1/me` accepts `{name}` only, returns the same profile.
`GET /api/v1/sessions` returns `{sessions:[{id,label,platform,createdAt,lastSeenAt,expiresAt,current}]}`.
`DELETE /api/v1/sessions/{id}` returns 204, inaccessible IDs do not expose another user's data.
`POST /api/v1/sessions/revoke-all` requires recent authentication <= 5 minutes and returns 204. `DELETE` current is logout.
Errors: `{code,message,request_id}`. Standard OAuth endpoints retain protocol errors.
OIDC public client id `titan-desktop`, scopes `openid profile email`, callback `http://127.0.0.1:<port>/oauth/callback`. Issuer configured, no hardcoded production domain. Discovery is authoritative.
Rust sanitized snapshot: `{status: 'unconfigured'|'guest'|'logging_in'|'authenticated'|'offline'|'reauth_required'|'unavailable', profile: Profile|null, message: string|null, persistent: boolean}`.
Tauri commands: `auth_status()`, `auth_login(memoryOnly:boolean,switchAccount:boolean)`, `auth_cancel()`, `auth_logout()`, `auth_update_profile(name:string)` return snapshot; `auth_sessions()` returns session array; `auth_revoke_session(id:string)` and `auth_revoke_all()` return snapshot. No command accepts issuer/URL/token from JS.

### Task 1: Reproduce installed baseline

Files: existing `src/`, `tests/`, package lock and Tauri source/config; design and this plan.
Produces: committed 0.4.1 account/settings baseline without build caches.
- [ ] Compare source snapshot to `2309e8b`, import only reviewed differences; save approved spec and plan.
- [ ] Run `npm test` and `npm run build`; record exact results; commit baseline.

### Task 2: Independent identity service and lifecycle

Files: create `services/accounts/pyproject.toml`, lock file, `manage.py`, `config/{settings,urls,wsgi}.py`, `accounts/{models,forms,views,api,oauth,security,mail,admin,urls}.py`, migrations, templates, tests and README. Split cohesive modules further only when needed.
Consumes: Shared Contracts and approved spec. Produces: runnable OIDC issuer and profile/session API, migration/setup commands and account test fixtures.
- [ ] Pin supported dependencies after reading official docs/installed source; write failing real endpoint tests for discovery, code/PKCE, verified-only authorization and identity data.
- [ ] Implement User, DeviceSession, one-time verification/recovery and durable rate limits/outbox; use framework hashing and OAuth implementation, not hand-rolled cryptography.
- [ ] Test email normalization/duplicate registration, password errors, verification/recovery replay/expiry, precise Origin/CSRF, disabled users and nickname validation; implement until passing.
- [ ] Test refresh rotation/replay, absolute expiry, account/session ownership, password reset invalidation, recent-auth enforcement and restore epoch with actual PostgreSQL transactions. Fail closed on uncertain state.
- [ ] Provide local-only bootstrap/dev mail retrieval (no public debug mailbox), bounded mail dispatcher, admin disabling and deterministic setup. Do not print credentials/tokens in logs.
- [ ] Run entire account suite, Django deployment checks with production-like configuration, dependency checks; document component token storage and P0 results; commit.

### Task 3: Native authentication bridge

Files: create `src-tauri/src/auth/{mod,config,types,oauth,callback,storage,client}.rs`, modify `Cargo.toml`, `Cargo.lock`, `lib.rs`; tests alongside auth modules.
Consumes: exact API above and Task 2 discovery behavior. Produces: the Tauri command contract above.
- [ ] Write failing tests for strict issuer/URL policy and callback state/path/method/query/size/timeout; verify failures.
- [ ] Implement mature OIDC/PKCE client, constrained browser opener, temporary loopback listener and cancellation. Validate signature/issuer/audience/nonce/time; reject unexpected redirect/token endpoint origins.
- [ ] Write failing tests for one refresh in flight, refresh ambiguity, logout/switch generation fences, expired credentials, server 401 vs connectivity failure and Keychain refusal.
- [ ] Implement OS credential storage, session snapshot, refresh and profile/session commands; persistent refresh credentials include family absolute expiry, memory-only opt-in. Never serialize raw tokens to JS.
- [ ] Run `cargo test --manifest-path src-tauri/Cargo.toml` and compile checks; integration-test against local service where possible; commit.

### Task 4: Account UI integration

Files: create `src/account-bridge.ts`, `src/useAccount.ts`, `src/AccountSessionPanel.tsx`, their tests; modify `src/AccountPage.tsx`, `src/App.tsx`, `src/account.css`, relevant browser tests.
Consumes: Tauri command/snapshot and API contracts. Produces: complete login/cancel/logout/profile/session UI with no raw secrets.
- [ ] Write failing tests for configured/unconfigured states, login cancellation, explicit memory-only choice after storage failure, offline logout notice, switch account and stale response rejection.
- [ ] Connect existing account page and sidebar to hook; show editable nickname and devices only from confirmed service data. Keep guest page and research statistics intact.
- [ ] Add confirmation for destructive account-wide logout within product; require browser reauthentication if server asks. Handle 429 and retryable service failures without blocking local tools.
- [ ] Verify account navigation preserves workbench drafts and keyboard isolation. Run `npm test`, `npm run build`, relevant Playwright tests; commit.

### Task 5: Deployment, CI and end-to-end evidence

Files: create `deploy/accounts/{compose.yaml,Caddyfile.fragment,env.example,README.md}`, scripts for checks/backup/restore and local test launch; `.github/workflows/accounts.yml`; `docs/checkpoint-reports/accounts/`.
Consumes: runnable service and desktop implementation. Produces: reviewable artifacts, local E2E evidence and honest remaining deployment/platform checklist.
- [ ] Test production settings fail closed without explicit issuer/secret/DB/SMTP/trusted proxy config; validate Compose/network exposure/resources and rollback script scope.
- [ ] Add pinned image build, dedicated app/database networks and volumes, loopback-only optional preview, bounded outbox worker, health/log controls and no second public 80/443 binding.
- [ ] Document gateway config validation and reversible swap with existing admin-off Caddy; no arbitrary execution against ECS. Include old-product read-only health checks and per-release manifest.
- [ ] Test encrypted backup and restore to a separate local database with forced new session epoch. Never restore over live data by default.
- [ ] Run full local PostgreSQL account flow + real system-browser/macOS callback/keychain when available; ensure guest WB flow and save/reopen/export still pass. Capture limitations without treating mocks as platform evidence.
- [ ] Add Windows/Linux CI tests and build jobs; native Windows acceptance remains explicitly pending without actual evidence.
- [ ] Review full branch against spec and resolve findings; record exact results, commits, startup instructions, unconfigured-production behavior and inputs needed for deployment.

## Execution decisions

User approved implementation. Use the subagent-driven workflow for the service, native bridge, UI and deployment units, with sequential implementers and independent reviews; baseline preparation is controller setup. Do not ask the user to choose routine implementation methods again. No cloud changes or externally delivered email are authorized by local implementation alone.
