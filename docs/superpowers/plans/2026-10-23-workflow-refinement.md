# Titan workflow refinement Implementation Plan

> **For agentic workers:** Use executing-plans to implement task-by-task. User approved the six recommendations in this conversation; proceed inline.

**Goal:** Preserve valid reviews, streamline the workbench, add batch editing and source navigation, and improve readable results.
**Architecture:** Keep schema v1 and the Python analysis contract. Derive affected reviews from before/after project dependencies; carry valid reviews to the new revision. Keep computed results only for metadata-only rename. Extract batch operations, issues, comparison settings, and source tracing into focused modules.
**Tech Stack:** React 19, TypeScript, Vite, Vitest, Playwright, Python, Tauri.
**Spec:** Approved recommendations in this conversation (2026-10-23).

## Global Constraints
- Preserve original pixels, backend math, audit/export contracts, existing work and light palette (#f6f8fc, #edf1f7, #ffffff, #26354b, #406de4, #a67639).
- Retain PingFang/SF typography; offer standard/large text. No added dependencies.
- Work in current checkout to retain the in-progress UI changes; no automatic commits or deployment to /Applications.
- Main workspace: left assets/ROI list; central canvas; right contextual properties first. One top workflow navigation. Mobile panels stack.
- Real WB verification requires user data and remains explicitly pending.

## Review Focus
- Rename must preserve calculations and export revision consistency; analytical edits must reject stale results.
- Changing one ROI/reference must not silently approve affected data or invalidate unrelated lanes; undo must not restore obsolete approval.
- Batch actions must be atomic, bounded to image coordinates, and refuse ambiguous reference matches.
- Spreadsheet paste must reject unknown lanes, conflicting shared samples, malformed/empty identifiers without partial updates.
- Read-only projects, small viewports, focused inputs, and async edits must remain safe.

### Task 1: Dependency-aware edits
Files: src/state.ts, src/state.test.ts, src/App.tsx.
- [x] Add failing tests for rename, scoped ROI/image/lane changes, settings changes, undo and result reuse.
- [x] Implement editProject + retainResult; preserve stale async rejection and disk revision semantics.
- [x] Run npm test.

### Task 2: Batch workbench and samples
Files: src/workflow.ts, src/workflow.test.ts, src/Workspace.tsx, src/SampleEditor.tsx.
- [x] Add failing tests for background candidates, matching, move/size/copy, TSV transaction checks and issues.
- [x] Implement atomic helpers, multi-selection, batch size/move/backgrounds, copy to new lanes, reference suggestions, sample paste and group/membrane fill.
- [x] Add fit/pan, arrow nudging, undo/redo shortcuts excluding focused form fields.
- [x] Run npm test and build.

### Task 3: Structure, quality and results
Files: src/App.tsx, src/ComparisonEditor.tsx, src/QualityPanel.tsx, src/Results.tsx, src/style.css, tests/browser/workflow.spec.ts.
- [x] Add browser regressions for rename/result retention, changed statistics preserving reviews, issue/source navigation, batch and readonly interactions.
- [x] Remove duplicate navigation, place assets/ROI list on left and selected properties first on right; compact header and independently scroll panels.
- [x] Move comparisons before calculation; add quality issue links, row/point source tracing and effect CI display.
- [x] Add persisted standard/large text preference, improve density and responsive layout.
- [x] Run browser workflow tests, inspect desktop/narrow screenshots, fix issues.

### Task 4: Release and documentation
Files: docs/USER_GUIDE.md, this ledger.
- [x] Update guide for invalidation, batch operations, paste format and traceability.
- [x] Run full frontend/Python/browser checks and macOS app build.
- [x] Fresh review and fix actionable issues, then deliver app and verification evidence.

## Execution ledger
- Baseline: npm test, 11 passed. Existing UI files modified by earlier authorized work; retained.
- Ruling: Continue in current checkout and execute approved scope without another confirmation; no new independent worktree that omits the existing UI.
- Ruling: Keep schema v1; all saved edits increment revision, valid review stamps advance only when their dependencies are unchanged. Numerical analysis still recomputes as a whole, avoiding a premature cache.

- Task 1: RED→GREEN scoped invalidation: rename, settings, ROI/reference, image, samples, undo, stale result protection.
- Task 2: RED→GREEN batch transactions, bounds, sample paste conflicts, reference matching, numbering.
- Task 3: Browser verification covers navigation, provenance, CI, paste/copy, readonly, keyboard, and large text at 1080/768/390 px. Screenshots inspected at 1440/1080/390.
- Final review: independent fresh reviewer found candidate ID collision after numbering, membrane '+' ambiguity, and reference flags routing to target. All fixed with regression tests.
- Final review re-grade: cancelling last batch checkbox treated as Important (could edit an explicitly deselected ROI), reproduced in browser and fixed by clearing selection consistently.
- Ruling: Existing project schema and full calculation engine retained. Only result-compatible metadata changes reuse a result; analytical changes still calculate the whole project. Cost: no incremental compute acceleration.
- Validation remaining: real WB data and native macOS window interaction require separate acceptance. Browser UI and packaged engine tests do not substitute for those.
- Final verification: npm test 38/38; pytest 62/62; Playwright 12/12 (actual Python engine). Rename-retained result exactly equals recomputation and exports successfully.
- Final build: TypeScript/Vite and Tauri macOS app succeeded. Independent copied bundle with clean PATH: health, probe, demo, analyze, save/open, export (10 output entries and checksums), lock release, codesign strict verification all passed.
- Evidence: artifacts/checkpoints/workflow-selected-1440.png; workflow-large-{1080,768,390}.png; artifacts/workflow-release-check/release-verification.json.
- No unresolved review findings. Work remains in the existing checkout without a commit; /Applications copy was not replaced. Current deliverable is src-tauri/target/release/bundle/macos/Titan WB.app.
