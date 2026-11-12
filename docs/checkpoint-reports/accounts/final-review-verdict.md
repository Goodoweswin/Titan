# Titan accounts final local review verdict — 2026-11-12

Local code and deployment-material review is complete through `ea226b0`. All identified local code/configuration findings are addressed. **Release acceptance is not complete: current macOS persistent login failed with OSStatus -25293.** No merge, push, deployment, installed-app replacement or user project modification was performed during this account implementation.

## Reviewed changes

| Review | Result |
| --- | --- |
| Whole branch `2309e8b..3848520` | Three Important findings: cross-process credential ownership, session-list snapshot propagation, missing real device metadata; one Minor password-report wording issue. |
| Fix `3848520..f73ee43` | All four addressed. New Important: account lock I/O failure blocked guest startup. |
| Narrow correction `f73ee43..f1aa960` | Guest-startup finding addressed; no new Critical/Important. Actual shared startup factory and scientific engine health exercised under two account-only filesystem failures. |
| CI preparation `f1aa960..ea226b0` | Missing root scientific environment provisioned for Linux/Windows native-tests; scoped review accepted, no new issue. Offline inspection only. |

The final two corrections were explicitly recorded as rulings rather than silently broadening the work. All seven execution rulings, their reasons and reversible costs remain verbatim in [implementation verification](implementation-verification.md). Detailed reviewer reports and test logs remain in this plan's ignored recovery directory; the managed worktree is retained while platform/UI handoff is unfinished.

## Evidence and limits

- Final product code `f1aa960`: Rust **42 passed, 1 ignored**, frontend **123 passed**, production TypeScript/Vite build passed. The ignored test is real service/OS credential integration, not a success result.
- Service at `f73ee43`: **102 passed** on disposable PostgreSQL databases; no service changes afterward. Relevant headless account browser tests: **4 passed**, mocked native IPC.
- Unchanged scientific engine: prior controller **346 passed + 5 subtests**. Synthetic engineering tests do not certify experimental scientific accuracy.
- Actual earlier native acceptance: default Chrome login/callback, explicit memory-only account use, nickname/device UI, logout, and guest WB save/export/restart/reopen passed. That QA bundle predates the final fixes; no final-binary GUI acceptance is claimed.
- Current real Keychain writes failed in the QA app and independent fresh-namespace test. Historical earlier success does not override the current -25293 failure. No OS/Keychain or real user password was entered; the browser test used a synthetic local account.
- CI prerequisites were structurally validated, including platform paths and failure propagation; neither remote GitHub CI nor Windows packaging/native acceptance was executed.

Existing font/chunk/dead-code warnings and all external/excluded boundaries remain documented in [implementation verification](implementation-verification.md) and the [native report](native-macos-2026-11-12.md).

## Retained work and next acceptance

The user deferred ECS, domain/DNS and real mail setup. [Deployment materials](../../../deploy/accounts/README.md) are prepared for that later task; Docker/Caddy/capacity/old-product health and real mail delivery remain unperformed.

Controller-owned local Gunicorn8000 and PostgreSQL55432 were verified and stopped; data/private config were retained. Before future live local acceptance, start the database, apply migration0004 and cold-start updated service code. The new application/data-root credential namespace requires a fresh login and does not migrate/delete old v1 items.

The Mac remained locked at the GUI cleanup handoff. The isolated test app and owned browser tabs have not been confirmed closed. Their cleanup and actual final native persistent-login/restart/rotation acceptance remain pending; installed Titan and its library were not targeted.

This final handoff changes documentation only. No product suites were repeated for the record update.
