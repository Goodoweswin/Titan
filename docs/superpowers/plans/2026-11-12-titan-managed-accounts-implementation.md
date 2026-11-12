# Titan Managed Accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Develop administrator-provisioned password login, sessions and logout without requiring mail, and prepare accurate ECS deployment instructions.

**Architecture:** Extend the existing independent Django/PostgreSQL account service with an explicit managed policy; keep self-service as the default. The native client accepts an issuer-authenticated administrator approval separately from email verification, retaining all existing token/storage/guest safeguards. Domain and server access remain external deployment prerequisites.

**Tech Stack:** Existing Python3.12+/Django/PostgreSQL17, OAuth2/OIDC/RS256, Rust/Tauri2, React/TypeScript; no new identity library.

**Spec:** `docs/superpowers/specs/2026-11-12-titan-managed-accounts-design.md`

## Global Constraints

- `ACCOUNTS_ACCOUNT_MODE=self_service|managed`，默认 `self_service`；未知值拒绝启动。
- self_service：维持现有邮箱注册、验证、邮件找回。生产仍必须 SMTP 且邮箱验证后才能取得桌面授权。
- managed：仅管理员开通的有效账号可取得授权和使用会话；允许明确的 `ACCOUNTS_MAIL_DELIVERY=disabled`。
- User 增加布尔 `admin_provisioned`，默认 false，迁移不自动批准既有用户；`verified_at` 仅代表真实邮件验证，管理员创建不设置它。
- 两种模式生产环境都继续要求 HTTPS issuer、强密钥、独立数据库角色、精确可信网关与安全 Cookie/CSRF。
- 会话600秒access、30天固定refresh家族、PKCE S256、RS256、撤销/重放/epoch/密码/停用失效规则保持。
- 账户仍在中栏；WB/IF/统计游客、草稿、正方形活动视图与现有OS凭据保护不变。
- 不修改现有Caddy、旧产品库、authorized_keys、安全组或公网路由；不将未确定域名或旧域名编入客户端。

## Review Focus

1. Mode changes and admin-approval revoke/reapprove must not accidentally revive old credentials; approval mutation rotates auth_version, policy-mode transitions explicitly require a new external epoch.
2. Stale admin saves must not overwrite admin provisioning/auth_version/password; all sensitive commands use user-first row locks.
3. Direct GET/POST to disabled registration/recovery/verify/reset routes must have no account/mail/token/password side effect.
4. An unverified profile must require explicit authenticated administrator approval and exact subject/session binding on every native profile path.
5. Managed deployment must not silently start mail dispatch or break self_service's default mail-worker behavior; no local proof is called ECS/public/Keychain acceptance.

---

### Task 1: Managed service policy and administrator lifecycle

**Files:**
- Create: `services/accounts/accounts/policy.py`, migration `0005_user_admin_provisioned.py`, management commands `provision_account.py` and `set_account_password.py` plus a focused shared helper if needed.
- Modify: `models.py`, `oauth.py`, `security.py`, `views.py`, `api.py`, `admin.py`, `config/settings.py` and existing browser page template.
- Test: new `accounts/tests/test_managed_accounts.py`, existing deployment/admin-concurrency/browser/endpoints/lifecycle suites as appropriate.

**Interfaces:**
- Consumes: existing user/session/epoch credential policy, transaction lock ordering, forms/password validators, mode/mail env config.
- Produces: `account_eligible(user)->bool` in policy.py; `User.admin_provisioned`; `/api/v1/me.administratorApproved: bool`; commands and configuration named above. Function returns true only active+managed-provisioned or active+self_service-email-verified. Existing public API remains additive and no client field grants approval.

- [x] Write real PostgreSQL failing cases proving managed unverified provisioned user can authorize/mint/list/rotate/logout; unmanaged (even email verified) is refused in managed, unverified provisioned refused in self_service; default behavior stays email-verified. Prove mode transitions with a new configured session epoch reject old browser/code/access/refresh credentials. Test direct disabled routes and absent links/outbox side effects.
- [x] Write command cases: hidden prompt/confirmation or explicit `--password-stdin` only (no argv password); weak/similar/mismatched passwords and duplicate normalized email rejected; existing user never overwritten; ordinary user roles, verified_at staysnull; reset preserves approval and invalidates browser/code/access/refresh. No secret echoed. Add stale admin save/approval revoke+reapprove cases.
- [x] Write production settings matrix: unknown mode fails; managed+disabled starts without any SMTP values but retains all other production requirements; self_service+disabled fails, existing SMTP checks remain.
- [x] Run focused new tests; Expected: behavioral failures on existing code, not unrelated missing infrastructure. Then implement minimal policy, guards, additive migration, safe commands and authenticated profile field. Keep self_service behavior and safe CSRF/referrer handling.
- [x] Run full account suite on disposable pytest PG DB and `makemigrations --check --dry-run --settings=config.test_settings`; Expected: all pass, no missing migration. Commit ownedfiles and report exact RED/GREEN/logs/remaining concerns.

### Task 2: Native and frontend managed-account contract

**Files:**
- Modify: `src-tauri/src/auth/types.rs`, `client.rs`, `oauth.rs`; shared Profile eligibility helper where fitting.
- Modify: `src/account-bridge.ts`, `AccountPage.tsx`, `AccountSessionPanel.tsx` and affected unit/browser fixtures/labels.
- Test: signed/native binding and client-state regressions; dedicated opt-in real managed-service memory-store roundtrip; front panel/page/account browser tests.

**Interfaces:**
- Consumes: Task1 real `/api/v1/me.administratorApproved` and admin-provisioned unverified user.
- Produces: Rust Profile `administrator_approved: bool` serde camelCase/defaultfalse; TypeScript optional boolean for older fixtures; neutral “登录账户” entry. Existing8Tauri commands and sanitized snapshots unchanged apart from additive profile flag.

- [x] Write failures for unverified/unapproved refusal, unverified/admin-approved acceptance, wrong-type flag rejection and subject/session mismatch. Check login commit, refresh/restore/status/profile-update paths; preserve all generation/process-owner/credential guards.
- [x] Implement eligibility from authenticated issuer-bound profile only; no JS supplied profile. Keep all ID signature/nonce/issuer/aud/azp/time validation and HTTPS policy. Do not fabricate emailVerified or grant from compile-time client setting.
- [x] Update neutral login entry/copy and tests without moving account pane or disturbing activity/guest drafts. Email-verification badge depends only on actual emailVerified.
- [x] Run full regular Rust tests, full frontend tests/build, affected account browser tests; Expected all pass with existing opt-in real OS test still honestly unaccepted.
- [x] Run a new explicit real local managed-service OAuth/password/session/refresh/logout loop using synthetic account and in-memory test store. Fixture/private service config never printed. It must prove authenticated profile has emailVerified=false and administratorApproved=true; do not replace or relabel existing failed OS Keychain integration. Commit/report exact proof.

### Task 3: Managed ECS configuration, launcher and handoff

**Files:**
- Create: `deploy/accounts/env.managed.example`, `compose.managed.yaml`.
- Modify: local launcher `scripts/local.py`, deploy structure checker/README and service README.
- Test: deployment material/local launcher validation and real isolated managed startup/provision/login/invalidations/stop evidence; docs checkpoint under `docs/checkpoint-reports/accounts/`.

**Interfaces:**
- Consumes: Task1 `ACCOUNTS_ACCOUNT_MODE=managed`, managed-only disabled mail and commands; Task2 accepted unverified approved profile.
- Produces: `local.py init --account-mode managed` (defaultself_service) and explicit managed Compose override, default api+db only. Self_service base still starts original worker. New env example contains no fake issuer/SMTP secrets. Document mode changes require epoch rotation.

- [x] Test launcher invalid mode fails before files/processes; managed init explicitly writes mode+disabled mail without SMTP values, default remains self_service. Managed compose override suppresses worker without mutating base service defaults; production config still validates issuer/roles/gateway.
- [x] Run focused failures then implement config/templates/docs and launcher option. Use existing explicit platform/path/PID ownership conventions; no cloud or OS changes.
- [x] Exercise actual independent local PG/service environment withmanaged settings, safe provision/reset commands and real browser endpoints; confirm no outbox and unavailable mail routes, sessions and invalidation, then stop only ownedprocesses. Do not use scientific .venv or installedapp data. Config/private fixtures remain0600 and excluded fromGit.
- [x] Verify structure/YAML/shell syntax and affected service suite; retain Task2 native evidence rather than repeat it. Write durable handoff: exact commits/tests, public old-site200/SSHkeydenied management absent, newdomain/authorizedWorkbench required; no deployment/current Keychain claim. Preserve previous evidence/history.
- [x] Commit and request whole-feature independent review. User already chose implementation scope; do not ask routine method approval. Address actionable findings and retain honest external gates. InstalledApp update is a separate explicit user request.

## Final local acceptance

Whole-feature review `ea735dc..2b8533c` found two operator-input P2 defects. Repair `18d5dd0` passed focused72/full191 service tests and the original reviewer accepted both fixes with no new Critical/Important issue. All three task reviews and the final scoped review are approved. Controller-owned test services and browser preview were confirmed closed. [Durable managed checkpoint](../../checkpoint-reports/accounts/managed-2026-11-12.md) preserves exact evidence, both rulings and all nine accepted deferred/excluded boundaries. No public ECS deployment or installed-app update is claimed.
