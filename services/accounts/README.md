# Titan accounts (independent service)

Django 5.2 LTS, Django OAuth Toolkit 3.4.1 and PostgreSQL. This service accepts only identity information, never experiment/project data. Its dependencies and database are independent of Titan's science engine and of any other ECS application. Nothing in this directory deploys a public service.

## Account mode and administrator lifecycle

`ACCOUNTS_ACCOUNT_MODE=self_service|managed` defaults to self-service and rejects unknown values. Self-service requires genuine email verification and production SMTP. Managed permits only active accounts with administrator approval, with `ACCOUNTS_MAIL_DELIVERY=disabled` and no sender/SMTP variables. It disables registration/resend/recovery and all verification/reset link consumption, for GET and POST. Browser copy points users to their administrator. Ordinary profile editing and client input cannot grant approval.

Run `manage.py provision_account --email user@example.org --name Researcher` under managed configuration to create an ordinary approved account. Run `manage.py set_account_password --email user@example.org` to reset an existing account and invalidate all browser/code/desktop credentials. Both prompt with hidden confirmation; explicit `--password-stdin` supports a controlled private input stream. There is no password argv option or default password; weak/similar passwords and duplicate emails are rejected. Administrator opening never sets `verified_at`: authenticated `/api/v1/me` adds boolean `administratorApproved`, while `emailVerified` stays truthful. Web admin approval display is read-only; normal model approval transitions rotate credential versions permanently.

Use the [local launcher and managed Compose guide](../../deploy/accounts/README.md) for separate private directories, explicit `init --account-mode managed`, API/DB-only production selection and private command invocation. Mode is fixed deployment policy: switching it requires a new external `ACCOUNTS_SESSION_EPOCH`, cold restart and reauthentication. Existing users remain unapproved after the additive migration. This extension has not deployed to ECS or updated the installed application; the earlier installed update has a separate record.

## Protocol contract

Configure `ACCOUNTS_ISSUER` as the exact externally visible origin without a trailing slash. Production requires HTTPS. Discovery: `/.well-known/openid-configuration`; authorization: `/o/authorize/`; token: `/o/token/`; JWKS: `/o/.well-known/jwks.json`; userinfo: `/o/userinfo/`; revocation: `/o/revoke_token/`. Only the public client `titan-desktop`, code flow, PKCE S256, RS256, and scopes `openid profile email` are supported. Redirect URI must be `http://127.0.0.1:<port>/oauth/callback`, no credentials/query/fragment. Code redemption must use the identical complete redirect URI.

Native authorization requests may include `device_platform` (`macos`, `windows`, `linux` or `desktop`) and `device_label` (1–80 Unicode characters, nonblank, no Unicode control/format/surrogate/private/unassigned characters; surrounding spaces normalized). Rust supplies the compile-target platform and a fixed descriptive label such as `Titan on macOS`. No hostname, OS username, serial/hardware ID, OS version or project/science data is collected. These fields describe the session and are never authorization evidence. They are validated before code issuance and saved in `GrantContext` by migration `0004_grant_device_metadata`; redemption copies that code-bound metadata into the device session. Token/refresh parameters cannot replace it; refresh preserves it. Omitted fields retain `desktop` / `Titan Desktop` compatibility for older clients. Apply the additive migration and cold-start the service before accepting new native sessions; this repair did not migrate or restart the controller's live localhost service.

Token responses additionally contain `session_id` and `refresh_expires_in` (remaining whole seconds to the original session's absolute deadline). Refresh does not reset that deadline. Access tokens expire in 600 seconds. Restore from backup **requires a new externally stored `ACCOUNTS_SESSION_EPOCH`** before allowing traffic. A normal process restart retains the epoch and existing sessions. Epoch is not restored from the database.

Desktop profile and session APIs use bearer tokens, never browser cookies. Browser forms use host-only session cookies and Django CSRF validation. Do not enable wildcard CORS. `prompt=login` forces the browser password form, including when switching accounts. Verification links require POST confirmation so mail scanners cannot consume them.

## Storage and trust boundaries

DOT is configured with `COMPLIANT_BCP_RFC9700_TOKEN_STORAGE=True`: access/refresh raw token columns are blank and SHA-256 checksums are used for lookup. Titan keeps refresh checksum tombstones independently, so DOT token cleanup cannot erase replay detection during an active family. Authorization codes remain transient recoverable values in DOT's grant table (60-second validity). Email link tokens are hashed in the token table; pending outbox bodies necessarily contain recoverable links until successful delivery/expiry cleanup. Restrict database and backup access, encrypt backups, and do not log bodies, headers, query strings, or complete callback URLs.

All token issuance and refresh lock the user row, then the device-session row, inside an outer PostgreSQL transaction. Recovery uses the same user-first order. A replay commits family revocation and returns `invalid_grant`; it cannot roll back the revocation by raising an exception. API and userinfo authorization re-check user activity, mode-specific eligibility (email verification or administrator provisioning), password fingerprint, epoch, session expiry and revocation. Password change invalidation is derived from Django's password hash; no out-of-band setter may bypass it. Account disablement remains effective if later re-enabled by the supported admin action, which permanently revokes existing sessions.

## Upstream references inspected

- [DOT OIDC](https://django-oauth-toolkit.readthedocs.io/en/stable/oidc.html)
- [DOT settings](https://django-oauth-toolkit.readthedocs.io/en/stable/settings.html)
- [DOT changelog](https://django-oauth-toolkit.readthedocs.io/en/stable/changelog.html)

Locked source, endpoint tests and PostgreSQL race tests are authoritative for Titan's behavior; framework defaults alone are insufficient.

## Local setup

Run from `services/accounts` using Python 3.12+ and PostgreSQL 17. `uv sync --frozen` creates **this service's** `.venv`; never install into the repository root science `.venv`. To use another location, set `UV_PROJECT_ENVIRONMENT` to an absolute path before syncing. Tests require a disposable PostgreSQL database and a role allowed to create its test database; never point tests at production. No SQLite fallback exists.

```sh
uv sync --frozen
# Use an existing isolated local PostgreSQL instance, or create one (macOS Homebrew example):
/opt/homebrew/opt/postgresql@17/bin/initdb -D /tmp/titan-accounts-pg -A trust --no-locale
/opt/homebrew/opt/postgresql@17/bin/pg_ctl -D /tmp/titan-accounts-pg -l /tmp/titan-accounts-pg.log -o '-p 55432 -h 127.0.0.1 -c unix_socket_directories=/tmp -c shared_buffers=32MB -c max_connections=20' start
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 55432 titan_accounts
```

The trust-auth instance above is exclusively a local development convenience. Production uses a private network, SCRAM credentials, distinct owner/migrator/runtime roles and encrypted backups. No Homebrew service or autostart is required.

Generate local secrets once into a directory outside the repository (do not overwrite existing configuration):

```sh
mkdir -m 700 -p "$HOME/.config/titan-accounts-local"
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets, getpass, shlex, os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
root=Path.home()/'.config/titan-accounts-local'
key=root/'signing.pem'
env=root/'service.env'
if key.exists() or env.exists():
    raise SystemExit('Configuration already exists; reuse it, do not regenerate on restart.')
private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
with os.fdopen(os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
    f.write(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
values={'ACCOUNTS_DEBUG':'1','ACCOUNTS_SECRET_KEY':secrets.token_urlsafe(64),
        'ACCOUNTS_SESSION_EPOCH':secrets.token_urlsafe(32),'ACCOUNTS_ISSUER':'http://127.0.0.1:8000',
        'ACCOUNTS_RSA_KEY_FILE':str(key),'ACCOUNTS_ALLOWED_HOSTS':'127.0.0.1,localhost',
        'PGHOST':'127.0.0.1','PGPORT':'55432','PGUSER':getpass.getuser(),'PGDATABASE':'titan_accounts'}
with os.fdopen(os.open(env,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
    f.writelines(f'export {k}={shlex.quote(v)}\n' for k,v in values.items())
PY
. "$HOME/.config/titan-accounts-local/service.env"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py bootstrap_accounts
.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
```

In default self-service mode, register in the browser. The local outbox never sends mail. Managed mode instead uses the administrator commands above and creates no mail outbox. In a second shell loading the same environment, run `manage.py dev_mail` to list IDs, then `manage.py dev_mail <id> --output /tmp/titan-private-message.eml`. The file is created exclusively with mode 0600; open it locally and follow the confirmation link. Delete local exported messages when finished. There is **no HTTP debug mailbox**.

Self-service production startup requires SMTP configuration (local DEBUG no-send remains supported). Managed production supports explicit disabled delivery without SMTP or a mail worker. Once a provider is approved, set `ACCOUNTS_MAIL_DELIVERY=smtp`, `ACCOUNTS_SMTP_HOST`, `ACCOUNTS_SMTP_USER`, `ACCOUNTS_SMTP_PASSWORD`, explicit `ACCOUNTS_SMTP_PORT` (normally 587), and `ACCOUNTS_FROM_EMAIL`. STARTTLS is required. Run `manage.py dispatch_mail --limit 10` periodically: at most 50 per invocation, a 10-second network timeout, five attempts, exponential backoff, and `skip_locked` per-message locking. Delivery is at-least-once across process crashes; link consumption is exactly once. Successful/expired bodies are erased. Run `manage.py cleanup_accounts` daily. SMTP interoperability and actual delivery have not been tested or authorized.

Admin URLs are absent by default. Set `ACCOUNTS_ADMIN_ENABLED=1` only behind a private management gateway, then use `manage.py createsuperuser`. Admin disabling irrevocably revokes all current desktop sessions; disabling also rotates the framework session-HMAC version. A later re-enable cannot revive old browser sessions, authorization codes, email links or desktop sessions. Never publish the admin through a wildcard gateway route.

## Configuration and verification

Local required settings: `ACCOUNTS_SECRET_KEY`, `ACCOUNTS_RSA_KEY_FILE`, `ACCOUNTS_ISSUER`, `ACCOUNTS_SESSION_EPOCH`. Production additionally requires all explicit DB/host/gateway settings and mode-appropriate mail settings described in [the deployment guide](../../deploy/accounts/README.md). `ACCOUNTS_TRUST_PROXY` is obsolete and ignored. `ACCOUNTS_TRUSTED_PROXY_IPS` accepts exact IPs only; middleware discards all arbitrary forwarding headers and accepts one gateway-replaced `X-Titan-Client-IP` only from an exact configured peer. Gunicorn's independent forwarded-header trust is disabled.

```sh
.venv/bin/pytest
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py check --deploy --fail-level WARNING
uv pip check --python .venv/bin/python
.venv/bin/pip-audit --progress-spinner off
```

Run deployment checks with production-like settings. The sole intentionally silenced check is DOT `W008`, which flags allowing HTTP redirects: RFC 8252 loopback requires HTTP, and Titan's validator restricts host/path/port and tests malicious alternatives. Implicit/password grants and PKCE plain are disabled. CSRF origins are the exact configured issuer, with secure host-only cookies and no CORS credentials.

Gunicorn example: `gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 1 --threads 2 --timeout 30 --forwarded-allow-ips "" --access-logfile /dev/null`. Do not enable access/query/body logging in any gateway. Django request/server/OAuth logs are suppressed because URLs can carry one-time credentials. Errors expose only stable codes, messages and request IDs. Service readiness is `/health/ready`; liveness is `/health/live`.

Resource budgets are **not certified** by unit/integration tests. The managed 304 MiB API+PostgreSQL limit and self-service 384 MiB API+PostgreSQL+worker limit require actual container measurements under the selected mode’s workload/restart/failure conditions before ECS deployment. Native credential stores, actual browser UI and Windows acceptance are separate desktop tasks.

Additional dependency sources: [DRF security release notes](https://www.django-rest-framework.org/community/release-notes/), [Django password management](https://docs.djangoproject.com/en/5.2/topics/auth/passwords/). Passwords use Django's default PBKDF2-SHA256 work factor without weakening for tests; benchmark on the target deployment before capacity claims.

Managed extension evidence, exact Task 1/2/3 validation and current external/platform gates are recorded in [managed handoff](../../docs/checkpoint-reports/accounts/managed-2026-11-12.md). The [prior implementation history](../../docs/checkpoint-reports/accounts/implementation-verification.md) and its seven execution rulings remain preserved.
