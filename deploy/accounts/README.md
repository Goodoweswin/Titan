# Titan accounts deployment materials

**Local implementation only. No ECS, DNS, real email, registry push or production deployment has been performed or authorized.** Production requires a selected domain, SMTP provider/credentials, gateway inventory and a measured capacity decision. Blank example values deliberately cannot start production.

## Reproduce locally

Prerequisites: Python 3.12+, uv, OpenSSL and PostgreSQL 17 tools. Run from repository root. The launcher creates a new private directory, its own Python environment and PostgreSQL cluster. It never modifies the scientific `.venv`, installed Titan, project library or existing port 8000/55432 service.

```sh
python3 deploy/accounts/scripts/local.py init --directory /tmp/titan-accounts-demo
python3 deploy/accounts/scripts/local.py start --directory /tmp/titan-accounts-demo
python3 deploy/accounts/scripts/local.py status --directory /tmp/titan-accounts-demo
python3 deploy/accounts/scripts/local.py stop --directory /tmp/titan-accounts-demo
```

Defaults: issuer `http://127.0.0.1:18081`, PostgreSQL `127.0.0.1:55433`. `init --port … --pg-port … --pg-bin …` selects alternatives; existing directories are refused. Reuse the directory to retain signing key, epoch and sessions across a cold restart. Stop uses the recorded PID only after checking the process command owns that directory. The PostgreSQL trust-auth cluster is loopback-only and strictly for local development. No autostart is installed. If initialization/start fails, inspect that directory's private logs and stop its own PostgreSQL process before retrying; do not kill another server to free a port.

`service.json` is private and should never be printed, committed or attached. To run a management command with this launcher configuration:

```sh
python3 - /tmp/titan-accounts-demo dev_mail <<'PY'
import json, os, subprocess, sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
env=dict(os.environ, **json.loads((root/'service.json').read_text()))
subprocess.run([str(root/'venv/bin/python'), 'manage.py', *sys.argv[2:]],
               cwd='services/accounts', env=env, check=True)
PY
```

`dev_mail` lists outbox IDs only. Pass `<id> --output /tmp/private-message.eml` to export one local message to an exclusive 0600 file; open it locally to verify registration/recovery and delete it afterward. No HTTP debug mailbox exists. Production refuses this command. A desktop test build must compile this exact issuer and use a distinct app identifier/project directory; see the native evidence checkpoint. An unconfigured release remains guest-capable and provides no working login until an issuer is configured.

## Build and configuration

The Dockerfile pins the official multiarch Python image by SHA-256. `compose.yaml` pins PostgreSQL 17 by SHA-256. Digests were resolved from the official Docker registry on 2026-11-12. Python production dependencies are the hash-checked export of `services/accounts/uv.lock`:

```sh
uv export --project services/accounts --frozen --no-dev --no-emit-project --format requirements-txt --no-header --output-file deploy/accounts/requirements.txt
uv run --no-project --with PyYAML==6.0.3 python deploy/accounts/scripts/check.py
docker build -f deploy/accounts/Dockerfile -t titan-accounts:review .
```

The image build contains no credentials. Before any rollout, inspect the built image, record its immutable registry digest, and set `ACCOUNTS_IMAGE=registry/name@sha256:…`. A local tag is only for build validation. Image publishing and any server execution require the later authorized deployment task.

Copy `env.example` into **two private files outside git**: Compose interpolation `.env` and runtime `service.env`. Use a private directory (0700), env files (0600), strong distinct random DB/admin/SMTP/Django secrets, a stable external random session epoch and a private RSA key. The mounted key must be readable by container UID 10001; set its host ownership appropriately and keep mode 0600. Avoid shell tracing and `docker compose config` output in shared logs, because expanded config contains credentials; use `docker compose config --quiet`.

Production `ACCOUNTS_DEBUG=0` requires explicit issuer, secret, key, epoch, single exact allowed host, every PG connection field, SMTP sender/host/port/user/password and at least one exact gateway IP. Issuer must be an HTTPS origin. SMTP cannot silently remain disabled; STARTTLS is required. `ACCOUNTS_TRUST_PROXY` is obsolete. `ACCOUNTS_TRUSTED_PROXY_IPS` must contain exact comma-separated IPs, never a subnet/wildcard. No production domain or mail credentials are supplied in this repository.

The initial database bootstrap creates separate roles:

- `titan_accounts_admin`: PostgreSQL initialization/backup-restore administration; never passed to API or worker.
- `titan_accounts_owner`: NOLOGIN database/schema owner.
- `titan_accounts_migrator`: schema migration role with owner membership; its default privileges grant runtime DML and sequence use.
- `titan_accounts_app`: runtime API/worker role, no CREATE/schema ownership/cluster administration.

Bootstrap runs only on a **new** `titan_accounts_database` volume. Changing env values does not rotate existing PostgreSQL passwords. Never delete/reinitialize a volume to repair credentials. Run migrations using the separate migrator secret, then bootstrap the public client using runtime credentials. For example, after loading private Compose variables and exporting the migrator's `PGPASSWORD` in a private operator shell:

```sh
docker compose -f deploy/accounts/compose.yaml run --rm -e PGUSER=titan_accounts_migrator -e PGPASSWORD api python manage.py migrate --noinput
docker compose -f deploy/accounts/compose.yaml run --rm api python manage.py bootstrap_accounts
docker compose -f deploy/accounts/compose.yaml run --rm api python manage.py check --deploy --fail-level WARNING
docker compose -f deploy/accounts/compose.yaml run --rm api python manage.py check_accounts_deployment
```

Run these only in the authorized deployment environment. API/worker entrypoints also run both checks before serving or dispatching. The last command reads actual PostgreSQL role/schema permissions and rejects administrator/migrator credentials. A successful check does not test SMTP delivery. Plan daily `cleanup_accounts` under the runtime role and supervise failures; cleanup is separate from the 5-message mail batch worker.

## Networks, gateway and budget

Compose declares an internal accounts-only database network, a separate SMTP egress network and an external **dedicated** `titan_accounts_gateway` network. No app/database ports are published by default. `compose.preview.yaml` optionally exposes only `127.0.0.1:18080`; it is for health inspection and does not bypass production HTTPS authentication. Do not add another public 80/443 binding or public PostgreSQL port.

The supplied gateway fragment targets an existing containerized Caddy joined to that dedicated network with a reserved, exact IP. Before use, inventory the actual gateway packaging/version/config path, address space, all existing sites, certificate storage, service manager and health endpoints. If the existing Caddy runs on the host or another topology, adapt and independently review the topology before use; do not blindly attach or replace it. Do not enable Caddy's admin API to simplify deployment.

The gateway must overwrite `X-Titan-Client-IP` using its TCP peer address, remove client forwarding headers and set forwarded proto to HTTPS. The application trusts that value **only** when the immediate peer equals its configured gateway IP, rejects malformed/multiple addresses and drops all other forwarding headers. Gunicorn blanket proxy trust is disabled. A CDN/load balancer in front of Caddy needs a separately reviewed source-address contract; the template intentionally limits based on Caddy's TCP peer, never an arbitrary forwarded chain. The dedicated network must contain only this account API and the gateway; Docker network access is part of the trust boundary.

No gateway access logs, request bodies, URLs, OAuth values or email bodies should be logged. Caddy error/debug logging also needs review for URI exposure. API/worker container logs rotate at 2 × 5 MiB. The DB suppresses SQL statement logging in errors. The fragment blocks public admin and health routes. All public browser mutations retain Django CSRF and secure host-only sessions.

Configured hard limits: API 144 MiB + PostgreSQL 160 MiB + worker 80 MiB = **384 MiB**; equal memory/swap caps, bounded process counts and CPU quotas. One API worker has two threads. One mail worker sends at most five messages per iteration, waits 30 seconds, uses the existing 10-second SMTP timeout/five-attempt backoff and never overlaps itself. A file heartbeat detects a stuck worker. These values are an experiment, **not a demonstrated safe capacity**. No Docker/Podman runtime was available locally. Before launch, measure summed cgroup memory/peak/OOM events under concurrent password hashing, registration/login, migration, DB restart, email outage/backlog and backup. Include gateway/host headroom separately. If the cap fails, revise the budget or architecture explicitly; do not reduce password hashing or silently raise limits.

## Existing admin-off Caddy: reversible operator procedure

This is a future procedure, not a script executed on ECS. The existing gateway owns public 80/443 throughout. Because admin is off, do not assume `caddy reload` works.

1. Record old product public/private health URLs and status/body expectations. Make read-only GET requests before changes; record timestamps/status and non-sensitive body hashes. Confirm no regression before changing anything. Do not guess endpoints.
2. Copy the **complete current** Caddy configuration and service/container definition to a versioned private backup; preserve owner/mode and certificate mounts. Compose a candidate by adding the account fragment while retaining every existing site/global option. Record current and candidate SHA-256 in the release manifest.
3. Validate the **complete candidate** with the same installed Caddy version and environment: `caddy validate --config <candidate> --adapter caddyfile`. Check site collisions, ports, upstream DNS and certificate configuration. Offline structure checks in this repo do not substitute for this validation.
4. Review the resulting full diff and release manifest. Prepare the exact existing service-manager/container cold-restart command and matching rollback command from the inventory. Have the previous account image and gateway config ready. Do not run a generic `docker compose down`, remove volumes, replace the old product stack or restart unrelated services.
5. After deployment authorization and maintenance timing, atomically replace the current config from a same-filesystem staging file preserving owner/mode, then **cold restart only the existing Caddy service/container** with its existing configuration and certificate mounts. Admin-off implies a brief gateway interruption; communicate it. No second gateway is started.
6. Immediately recheck every old-product health endpoint and the new discovery/JWKS/login flow. If checks fail, restore the exact old config atomically and cold restart that same gateway once; recheck old-product health. Stop account API/worker only if needed. Leave the database/volume intact for diagnosis. Keep the old config/certificates until the release is accepted.

## Backups, restore and rollback

Install the official `age` CLI and matching PostgreSQL 17 client tools on the operator host. Keep the age identity offline/separate from the database and application host; backup needs **only the recipient public key**. Backups stream directly from `pg_dump` through age into an exclusive 0600 encrypted file; no plaintext dump file is created. Metadata contains only source DB name, timestamp and ciphertext checksum. Back up signing/Django configuration independently under the same secret-handling policy, but **never reuse the backed-up session epoch after a restore**.

```sh
# PG* identifies source DB using a read-capable runtime role; never put passwords in argv.
python3 deploy/accounts/scripts/backup_restore.py backup --output /private/backup.dump.age --recipient age1...
# PG* now identifies an isolated target cluster and a role allowed to CREATE DATABASE.
python3 deploy/accounts/scripts/backup_restore.py restore --input /private/backup.dump.age --identity /offline/backup.agekey --database titan_accounts_restore_20261112 --epoch-file /private/restored.env
```

Restore always requires a fresh `titan_accounts_restore_*` name, refuses an existing DB/source name/epoch file, checks ciphertext checksum, uses `pg_restore --single-transaction --no-owner --no-acl`, and creates a fresh random epoch only after successful decryption/restoration. It never starts a service or switches live data. Failed restores may leave an empty/partial **isolated** destination for inspection; never treat it as accepted. Restored objects belong to the restoration role; production promotion requires reapplying/reviewing the owner/migrator/runtime grants and passing runtime preflight. Do not promote a database while the app still uses the old epoch. Keep ordinary restart epoch stable; restore/key rollover requires new epoch and reauthentication. Test key restoration, retention, restore duration and delivery separately.

`rehearse_restore.py` automates a local drill using its own disposable source+target databases. It creates synthetic credentials, encrypts/restores, proves old access/refresh/code/browser/reset credentials fail under the new epoch, verifies the user remains, rejects duplicate target restore, then removes only those two databases. It leaves encrypted backup/identity/epoch in its private directory and deletes its temporary old-credential JSON on success. Failure leaves private evidence/databases for explicit inspection.

```sh
PATH="/path/to/age:/path/to/postgresql/bin:$PATH" PGHOST=127.0.0.1 PGPORT=55432 \
  /path/to/accounts-venv/bin/python deploy/accounts/scripts/rehearse_restore.py --directory /tmp/accounts-restore-drill
```

Create a per-release record using `release_manifest.py --image …@sha256:… --previous-image …@sha256:… --candidate-gateway <file> --previous-gateway <file> --output <new-file>`. Omit previous image for initial deployment. It records commit, image(s), gateway hashes, application migration names and a digest of migrations plus the dependency lock and gates; it deploys nothing. It contains no env/secret values. A final operator record must additionally attach container measurement, schema plan, health and SMTP evidence.

`rollback.py --current <manifest> --target <prior-manifest> --output <new-override.json>` only prepares an override containing **api/worker image digests**. It refuses differing migration digests and never edits DB/volumes/epoch/gateway or invokes Docker. After separate compatibility review, an operator may use that override with `compose up -d --no-deps api worker`. A schema-changing rollback requires a reviewed forward recovery/data restore procedure; this script deliberately cannot perform it. Gateway rollback is the distinct config restoration above.

## CI and remaining acceptance

`accounts.yml` defines Linux PostgreSQL service tests, dependency audit and Docker build (no push), Windows/Linux native library tests/executable compilation, and a Windows installer build using the existing packaging workflow with updated dependency notices. Native compile jobs override resource bundling rather than fabricate engine resources; the Windows package job builds the actual engine. The workflow has not run on GitHub in this task. CI compilation is not actual Credential Manager, default-browser, callback/firewall, installer or restart acceptance. Windows native acceptance remains pending; Linux desktop packaging is outside this product's current packaging support.

See [local evidence](../../docs/checkpoint-reports/accounts/task-5-local.md). Production domain/DNS, SMTP delivery, authorized gateway inventory/swap, container limits, target-server load, production Keychain signing/ACL, and Windows native validation remain explicit release gates.
