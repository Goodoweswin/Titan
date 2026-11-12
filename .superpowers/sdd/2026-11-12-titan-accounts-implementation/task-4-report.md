# Task 4 — Account UI integration — 2026-11-12

Implemented on the managed account checkout, based on `bde1e85`. Existing 0.4.1 account/research layout, local guest workflow and styling are retained. This report covers local implementation and validation; independent controller review follows.

## Changes

- Added `src/account-bridge.ts`: typed sanitized native profile, snapshot and device records plus the eight exact Tauri command adapters. No issuer, URL, password, access token or refresh token enters React or browser storage.
- Added `src/useAccount.ts`: status initialization, immediately visible long-running browser login, independent cancellation, explicit memory-only retry, profile save, device listing/revocation, logout and all-device logout. Local operation generations fence delayed login/profile/status results; device requests additionally fence by request order and session identity. Unexpected IPC exception text is discarded. An IPC login failure leaves the pending state so retry remains possible.
- Added `src/AccountSessionPanel.tsx` and integrated the hook into the existing `AccountPage` and sidebar in `App`. Hook lifetime belongs to `App`, so closing/reopening the account dialog preserves a pending login. The panel collects only nickname; browser login handles credentials. Nickname/profile and devices use confirmed service/native responses. Offline profile data is labelled as the last confirmed result. Existing research statistics, calendar, recent-project actions and guest presentation remain.
- The panel provides safe-storage retry and a separate explicit “仅本次登录” choice after `credential_storage_failed`; it never falls back automatically. `credential_invalidation_failed` displays the native restart-restoration warning and a retry, while `credential_cleanup_failed` may accurately say restore was blocked. Local logout always explains that server-side revocation is unconfirmed, because the native command only attempts remote revocation in the background.
- All-device logout has an in-product confirmation, initial focus on cancel, cancellation and Escape handling. `recent_auth_required` offers forced browser authentication (`switchAccount:true`); it does not automatically repeat destructive revocation after login. The user confirms the action again. Current-device and individual-device revoke controls use the native APIs.
- Account dialog key events stop propagation; existing workbench remains mounted. This preserves WB figure drafts, and the existing modal handling continues to block background shortcuts.
- Chinese product copy is used for desktop states, retries and notices. Localized service login/register/recovery/reset/verification titles, form labels/validation prose, navigation, transactional test-mail subject/body and Django `LANGUAGE_CODE`. Updated the verification template's title predicate together with its translated title, preserving its CSRF-protected POST control. These are textual changes only; account authentication logic is unchanged.

## Controller-approved scope refinement

During integration, the existing native HTTP adapter was found to collapse 429 and generic 403 into `service_unavailable`. The controller explicitly assigned the narrow `src-tauri/src/auth/oauth.rs` error-mapping and `types.rs` message refinement to Task 4. The adapter now distinguishes HTTP 401 (`unauthorized`), generic 403 (`forbidden`), 403 `recent_auth_required`, HTTP 429 (`rate_limited`, including a non-JSON body), and retryable service errors. Known `invalid_profile`/`not_found` codes remain preserved. UI/session-error wording distinguishes these failures and offers retry without blocking local tools. No token, discovery, refresh, credential-storage or native session-generation flow was changed.

## RED / GREEN evidence

1. Wrote the first seven hook regressions against an inert hook stub. `npm test -- src/useAccount.test.ts`: **0 passed, 7 failed**, covering configured/browser-preview state, immediate login/cancellation, explicit memory-only choice, uncertain remote logout, stale profile/session after switch, stale initial status after logout and sanitized IPC/session errors. Implemented the hook: **7 passed**.
2. Wrote panel regressions against an empty panel stub. `npm test -- src/account-session-panel.test.ts`: **0 passed, 8 failed**, due to missing visible controls/device/warning behavior. Implemented the panel: **8 passed**. Existing account-page tests remained **3 passed**.
3. Added the real loopback HTTP native mapping table before production mapping changes. `cargo test --manifest-path src-tauri/Cargo.toml --offline auth::oauth::tests::api_distinguishes --lib`: **0 passed, 1 failed**, with HTTP403 returning `service_unavailable` instead of `forbidden`. After the mapping change, **1 passed**, exercising all eight table cases, including both forms of 429.
4. Added an unexpected-login-IPC-failure regression before its recovery fix. `npm test -- src/useAccount.test.ts`: **7 passed, 1 failed**, because the failed login remained `logging_in`. After the fix, **8 passed** and raw exception text stayed absent.
5. Expanded panel retry coverage to literal rate-limit/forbidden/service-unavailable cases. The new service-unavailable case initially failed because it rendered generic operation failure. Added specific service copy; final focused run: **18 passed** across hook/panel tests.
6. Browser integration initially passed the unconfigured/draft test but the mocked-native test crashed before app render: the fixture omitted Tauri `metadata.currentWindow` and event callback support, which existing native-window handling needs. Read the captured trace and corrected only that fixture; rerun: **4 passed**. No production change was made for this fixture problem. The first new service-form-control run also needed the Django `db` fixture for recovery/resend session writes; corrected the test setup, then all six cases passed. These fixture failures are not claimed as production REDs.

## Final verification

- `npm test`: **116 passed, 0 failed**, 20 files. This includes all existing research and workbench tests and the new 8 hook + 10 panel tests. Statistics tests use the real local engine with temporary fixtures.
- `npm run build`: **passed**, TypeScript and Vite production build.
- `npm run test:e2e -- tests/browser/account.spec.ts tests/browser/workspace-navigation.spec.ts tests/browser/workspace-chrome.spec.ts tests/browser/appearance.spec.ts`: **28 passed, 0 failed** in 57.8 seconds. Four new account browser cases cover: unconfigured guest/research UI with unsaved WB figure draft and keyboard isolation; pending login across dialog reopen/cancel/late response; confirmed nickname/sidebar/device list, cancel/confirm/recent-browser-auth guard and logout notice; and explicit memory-only login. Existing navigation tests also verify WB/IF/statistics drafts/history and existing appearance behavior.
- `/tmp/titan-accounts-venv/bin/python -m pytest -q` in `services/accounts`: **55 passed, 0 failed**. Includes the existing account/API/lifecycle/concurrency/operations suite and six browser-form-control checks preserving CSRF, continuation and required fields after localization.
- `cargo test --manifest-path src-tauri/Cargo.toml --offline`: **33 passed, 0 failed, 1 ignored**; main/doc targets also passed. The ignored test is the opt-in real local-service/OS-credential roundtrip already verified during Task 3. The new HTTP mapping test uses a real ephemeral loopback HTTP server.
- `rustfmt --edition 2021 --check src-tauri/src/auth/oauth.rs src-tauri/src/auth/types.rs`: **passed**.
- `git diff --check`: **passed**.
- Reviewed `artifacts/accounts/confirmed-account.png` from the actual Chromium app render: account profile/nickname/device controls fit the existing layout, with research statistics retained below. This is an ignored local QA artifact, not committed.

Final build/unit checks were rerun after the final UI error-recovery wording changes; the 28-browser run preceded those narrow wording/IPC-exception additions, which are covered by the final focused and full unit suites.

Existing nonfatal output: Vite warns about chunks over 500 kB, Cargo warns about the pre-existing `decode_response` dead code, matplotlib reports its existing Noto Sans SC weight fallback, and Playwright reports the environment's NO_COLOR/FORCE_COLOR combination. No test failure remains.

## Boundaries and concerns

- Browser account integration uses a sanitized native-IPC fixture; it does **not** claim actual browser-to-native-to-service GUI acceptance. The UI invokes the same reviewed native contracts; the real native local-service/Keychain roundtrip is Task 3 evidence, not rerun as part of this UI task.
- No packaged/signed-app Keychain acceptance, real denied-Keychain UI, Windows/Linux native acceptance, production domain/mail delivery, ECS/deployment or service memory-budget certification is claimed. These remain controller/follow-on acceptance boundaries.
- Existing running service processes were not restarted for Python-view localization. A newly started service or the isolated test runner sees the localized Python labels; the already-running service may retain imported English view titles until controller restart. Templates are updated on disk.
- The account modal is vertically scrollable at the existing size; device controls precede research statistics. Guest and research content remain usable when account service is absent or failing.
- No installed application or user project library was modified. Science environment links and dependencies were not changed; browser tests use the existing temporary integration library. No credentials were printed or committed. No mail dispatch, ECS changes, deployment or push occurred.
- The controller-owned plan edits were left untouched and excluded from the commit. No scope blocker remains for independent review.

## Integration fix round 1 — same-origin browser form CSRF

The controller's actual native/default-browser GUI acceptance found a blocker that the earlier manually supplied-Origin test clients and mocked native UI did not exercise: Chrome's real basic form `POST /login` sent `Origin: null`, and Django correctly rejected it with HTTP403. Inspection identified `BrowserEpochMiddleware` emitting `Referrer-Policy: no-referrer` on every account form. The controller explicitly expanded Task 4's scope to this narrow middleware policy fix and its regressions.

Changed only the response policy to `same-origin`, with a code comment explaining the browser interaction. This preserves same-origin form Origin/Referer information while suppressing referrers on cross-origin navigation, including native loopback callbacks on a different port. No CSRF middleware, token checks, trusted-origin configuration, null-origin handling or wildcard-origin allowances were relaxed. Authentication/token/credential logic is unchanged.

Primary references verified directly: [MDN Referrer-Policy: directives and effect on Origin](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy) documents that `no-referrer` produces null Origin for basic form submissions and that `same-origin` omits cross-origin referrers. [Django 5.2 CSRF documentation](https://docs.djangoproject.com/en/5.2/ref/csrf/) specifies Origin validation and strict HTTPS Referer fallback, and warns that global referrer suppression breaks unsafe-method CSRF protection.

RED / GREEN and verification:

- Added a response-policy regression to all six account form route cases, plus `test_browser_csrf.py` using the actual `Client(enforce_csrf_checks=True)` middleware. Before the policy fix, `/tmp/titan-accounts-venv/bin/python -m pytest -q accounts/tests/test_browser_forms.py accounts/tests/test_browser_csrf.py`: **6 failed, 8 passed**. All six failures observed `no-referrer` instead of the browser-safe same-origin policy. The strict-CSRF request controls passed before the fix and guard against weakening protection; they do not pretend to simulate browser Origin generation. The controller's real Chrome failure is the end-to-end RED evidence.
- After the policy fix, `/tmp/titan-accounts-venv/bin/python -m pytest -q accounts/tests/test_browser_forms.py accounts/tests/test_browser_csrf.py accounts/tests/test_lifecycle.py`: **26 passed, 0 failed**. Controls prove valid-token, same-origin login succeeds over HTTP and HTTPS; null and foreign Origin remain HTTP403 with no authenticated browser session even with a valid token; HTTPS without Origin still requires a same-origin Referer.
- Final full account service suite, `/tmp/titan-accounts-venv/bin/python -m pytest -q`: **63 passed, 0 failed** in 12.25 seconds.
- `git diff --check`: passed. Frontend and native suites were not repeated for this service-response-header-only change.

No service restart or GUI operation was performed in this round. The controller owns the cold restart and actual Chrome/native GREEN acceptance. Controller-owned plan edits and the unrelated untracked `.venv-native-check/` directory were not touched or staged.
