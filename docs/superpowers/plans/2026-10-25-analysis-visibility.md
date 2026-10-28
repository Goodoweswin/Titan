# Analysis Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add inspectable signal profiles, faithful export previews and explicit candidate acceptance.
**Architecture:** Pure Python profile calculation and shared chart rendering exposed through existing engine dispatch; focused React panels own asynchronous preview state, while App owns project mutations.
**Tech Stack:** Existing React / TypeScript / SVG, Tauri, NumPy, Matplotlib. No new dependencies.
**Spec:** docs/superpowers/specs/2026-10-25-analysis-visibility.md

## Global Constraints
- Preserve original pixel depth, signed corrected signals, revision invalidation, and existing unsaved changes.
- Preview is read-only. No ML dependency. Current checkout; no automatic git commit of mixed prior changes.
- Font sizes inherit current standard/large setting; light palette.

## Review Focus
- Dark polarity requires explicit ceiling; profile and measure agree (task 1).
- Missing/overlapping background must not imply valid correction (task 1).
- Out-of-order responses and project switching cannot display stale previews (tasks 1, 2).
- Candidate cancellation and intervening edits cannot mutate old projects (task 3).
- Render settings invalid/out of bounds cannot cause huge output allocations (task 2).

### Task 1: Signal profile
Files: backend/titan_wb/profiles.py, engine.py; src/SignalProfile.tsx, types.ts, Workspace.tsx, style.css; tests/test_profiles.py; tests/browser/workflow.spec.ts.
Interface: profile(project, roi_id) returns project_id/input_revision/roi_id, samples[{y,mean,min,max}], rect, background_mean|null, measurement|null, warning|null. Reuses read_pixels/_oriented/measure. UI requests on selected ROI/revision with debounce and stale guard.
- [x] Write failing Python tests for bright/dark 16-bit, signed signal, union background, missing/invalid background, bad hash and bounded sample count; run `.venv/bin/python -m pytest tests/test_profiles.py -q` (expected FAIL before implementation).
- [x] Implement engine command and panel; selected range shaded, baseline dashed, raw/corrected switch; show exact measure readout. Profile empty/error explicit.
- [x] Run targeted Python and browser selection/stale tests (expected PASS).

### Task 2: Faithful chart preview
Files: backend/titan_wb/export.py, engine.py; src/ExportPreview.tsx, App.tsx, types.ts, style.css; tests/test_export.py; tests/browser/workflow.spec.ts.
Interface: export_preview(project,result,settings) returns PNG data URI, pixel width/height, validated settings. export accepts same settings. Settings: panel_width 3..8 inch, height 3..8 inch, font_size 8..24 pt, dpi 72..300. Maximum 20 million raster pixels. Default 5/4/11/220.
- [x] Write failing tests for matching PNG preview/export, settings audit, invalid bounds and stale result; run targeted suite (expected FAIL).
- [x] Refactor shared render function, temporary preview, stale guard and native modal with settings and confirmation. Settings do not modify project. Preserve export bundle contract.
- [x] Run Python and browser preview tests (expected PASS).

### Task 3: Candidate acceptance
Files: src/App.tsx, Workspace.tsx, types.ts, style.css; tests/browser/workflow.spec.ts.
Interface: staged detection contains project id/revision/image/analyte/role/boxes. Workspace toggles indices; App confirms only current revision. Existing appendCandidates remains authoritative, exclusions applied before call.
- [x] Write failing browser test: detection leaves ROI count unchanged, overlay visible, unchecked candidates excluded, cancel leaves count unchanged, acceptance undoable; revision change discards stage.
- [x] Implement staged preview and explicit accept/cancel; handle no detections.
- [x] Run browser suite (expected PASS).

### Task 4: Integration and review
- [x] Update USER_GUIDE with profile meaning, export settings, candidate confirmation.
- [x] Run npm test, pytest, npm run build, npm run test:e2e; inspect screenshots at desktop and narrow/large type. Expected all pass with readable controls.
- [x] Fresh code review of this change, fix material findings with regression tests.
- [x] Build desktop app and run release engine verification if build tools available. Record actual limitations.

## Execution ledger
- Ruling: User explicitly requested planning then execution; proceeding without another approval gate. Current checkout preserves prior uncommitted work; no commits of mixed changes. Cost: changes remain combined in working tree for review.
- Task 1: Python RED (7 unsupported-command failures) → GREEN (7/7); browser selection/stale-response RED → GREEN. Production build passed.
- Task 2: Python RED (2 missing-preview failures) → GREEN (5/5 export tests); browser preview/settings RED → GREEN. PNG pixel equality checked against actual export.
- Task 3: Ruling: Retain original candidate indices when excluding candidates, so later candidates retain their existing lane association. Existing duplicate guard remains; skipped count is explicit. Cost: mapping is still a draft that users must review, not automatic lane identity inference.
- Task 3: Regression for candidate index preservation RED → GREEN (21/21 workflow tests). Browser acceptance fixture uses a new analyte because the existing demo already contains TARGET in every lane; the existing duplicate guard correctly prevented duplicate creation.
- Final review: fresh read-only reviewer found no critical/important issue; two findings initially marked minor were regraded for this task. Tiny axis labels directly violate the user's large-font requirement; hidden baseline undermines the new negative-signal explanation. Both treated as material and fixed in one pass.
- Final fixed: narrow/large-text axis labels — browser label-height regression RED (10 px) → GREEN (>=12 px); responsive SVG coordinates now honor current text scale.
- Final fixed: off-chart background baseline — actual-engine negative-signal browser fixture RED (y=-52) → GREEN (within plotted bounds), including background-subtracted mode.
- Final fixed: export confirmation below viewport — 1080x800 viewport assertion RED → GREEN after constraining image preview height and keeping actions visible.
- Final Ruling: review set aside real WB accuracy, native dialogs, bundled execution, screenshots and pre-existing scientific lane/plot policy. Bundled execution and screenshots are verified by this task; native window/dialog acceptance and real WB accuracy remain explicitly unverified. Existing lane association remains a reviewable draft; no change to scientific policy. Cost: users must still verify lane identity and real data suitability.
- Deferred minors: none from this review remain; all identified display issues affect the requested usability and were fixed.

- Final suites: `npm test` 39/39, `.venv/bin/python -m pytest -q` 71/71, `npm run test:e2e` 16/16. Production TypeScript/Vite and Tauri .app build passed. Updated screenshots visually inspected at 1080px large text and desktop. `git diff --check` passed.

- Release verification complete: independent app copy with clean PATH passed health, pixel probe, synthetic analysis, profile/measurement equality, preview/export PNG equality, save/reopen, exported-file hashes and codesign verification (exit 0). Evidence: artifacts/visibility-release-check/release-verification.json. Native window and real WB accuracy remain unverified.
