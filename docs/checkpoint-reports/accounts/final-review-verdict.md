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

Controller subsequently completed the GUI cleanup after handoff: CUA observed the isolated test app exited; owned Chrome tabs1251376197,1251376200,1251376203,1251376206 were closed and none remain; IAB preview absent. Installed Titan and its library were not targeted. Cleanup is DONE; the earlier lock/unlock failure remains historical evidence. This does not repair or rerun Keychain -25293 or constitute final-binary native account acceptance. Actual final native persistent-login/restart/rotation acceptance remains pending.

This final handoff changes documentation only. No product suites were repeated for the record update.


## User-requested account center correction after that review

The latest user correction moves account from a modal into the existing center workspace pane (base `8557e00`). Sidebar selection, global title/history, hidden-pane keyboard isolation, live WB/IF/statistics draft resumption and ordinary guarded navigation are covered by the frontend/browser evidence in [implementation verification](implementation-verification.md#user-corrected-account-center-base-8557e00). Full frontend **123 passed**, build passed, affected browser scopes **34 passed**, and the final strengthened account-only scope **9 passed**. Those account native fixtures remain mocks. Independent scoped review accepted `484879e` for specification compliance and code quality, with no Critical or Important finding. Existing font, chunk and color-environment warnings remain unchanged.

Controller CUA visually verified the current frontend in actual Chrome on local preview1430: account occupies the shell center; sidebar and global navigation remain visible, with no modal backdrop. Clicking sidebar 首页 navigated successfully and global 后退 returned to the account center. This was a browser layout/navigation check without a login fixture or OS authentication; it did not replace the installed app. Controller closed its test tab1251376213 and stopped preview1430 with Ctrl-C. The shareable headless layout screenshot is `artifacts/accounts/account-center.png` (1440px desktop viewport); it is separate from the controller CUA observation.

These new layout/navigation checks do not rerun or pass the failed Keychain gate or final native persistent-login/restart acceptance. No deployment or installed-app replacement occurred.
