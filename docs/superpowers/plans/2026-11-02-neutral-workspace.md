# Neutral Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Deliver the approved neutral, compact Titan chrome and WB assembly surface, then install the verified local App.

**Architecture:** Extract a focused presentation-only `WorkspaceHeader` from App, retain App's existing handlers and disabled conditions, and put shared chrome styling in one stylesheet loaded after existing styles. Keep WB state/persistence code unchanged except for presentation of its document actions and empty state.

**Tech Stack:** Existing React/TypeScript, CSS, Playwright, Tauri and packaged Python engine.

**Spec:** `docs/superpowers/specs/2026-11-02-neutral-workspace-design.md`

## Global Constraints

- Keep data algorithms, project formats, ROI colors, brand assets and app identity unchanged.
- System fonts and rem sizing preserve standard/large text mode; visible keyboard focus and disabled/readonly states.
- White #ffffff, rail #f6f6f5, ink #202123, muted #6b6d6b, line #e6e7e5, image interaction blue #4167c4.
- Compact title/action row plus unnumbered main navigation; WB layout remains canvas-first.
- User authorized planning and immediate execution, including the previously established local App update workflow. Retain this non-main checkout and unrelated untracked assets; do not merge/push/publish.

## Review Focus

- Context-specific header actions must preserve existing save/copy/import/analysis protections.
- WB empty state must permit exactly one creation action, including after saving/removing rows and readonly opens.
- Keyboard focus, long experiment names and large text must remain usable without viewport overflow.
- Switching an active protein/navigation must preserve draft cancellation semantics.
- Installed application must actually contain the new chrome and packaged WB commands.

## Task 1: Compact shell and global controls

**Files:** Create `src/WorkspaceHeader.tsx`, `src/chrome.css`, `tests/browser/workspace-chrome.spec.ts`; modify `src/App.tsx`, `src/style.css`, `src/main.tsx`, `src/ProjectLibrary.tsx` if needed to accurately represent WB navigation.

**Interfaces:** Header consumes project/name/read-only/dirty, text-size setting, busy flags, and App's existing save/copy/import/analyze/export/undo handlers. It cannot mutate project data directly. Main navigation keeps existing button names for guided/manual modes and uses current-page semantics without step numbers.

- [x] Add failing browser assertions: single compact experiment heading, unnumbered navigation, correct view actions, large text and long-name desktop/narrow layout, save/copy accessible names.
- [x] Run targeted browser test and confirm baseline fails before implementation.
- [x] Extract header, consolidate title/actions and protein navigation, move status metadata to footer, update neutral tokens and shared control styles; maintain handlers and guards.
- [x] Run frontend unit tests, production build and targeted shell browser cases; inspect rendered workbench and results screenshots; commit.

## Task 2: WB document surface and visual acceptance

**Files:** Modify `src/WbFigureEditor.tsx`, `src/wb-figure.css`, `tests/browser/workspace-chrome.spec.ts`; retain current WB source/render/state modules.

**Interfaces:** Existing WB editor props/IPC and operation guards remain intact. Empty view has one create action, aligned group, conditional saved-document selector; editor view has local save/export toolbar.

- [x] Add failing empty-state/create-count/center-alignment tests and screenshot cases, including large text, edit/cancel navigation and narrow width.
- [x] Run tests to confirm the reported duplicate-action/alignment defects.
- [x] Replace dashed empty container and duplicate action; scope h3 alignment and neutralize WB inspector/text/line colors using shared tokens. Preserve effective DPI and integrity/confirmation messages.
- [x] Run targeted WB and chrome browser tests, inspect empty/editor screenshots and commit.

## Task 3: Review, regression and local installation

**Files:** Add `docs/checkpoint-reports/neutral-workspace.md`; update usage documentation only where commands visibly change.

- [x] Run all Python/frontend/browser suites, production build and diff checks; commission one fresh independent whole-change review.
- [x] Fix material review findings with failing regressions, rerun affected/full checks and capture final screenshot evidence.
- [x] Rebuild desktop app with existing packaged engine and notices; run packaged acceptance, stage signed App, preserve old /Applications/Titan.app backup, install and launch.
- [x] Verify actual native title/navigation/WB view and installed binary hashes. Record limited native-verification scope, mark plan complete, commit and leave App ready for use.

Completion: source changes committed in cf30d5f and 699b4e7. 194 Python tests + 5 subtests, 62 frontend tests, 45 browser tests, production/App builds and packaged acceptance passed. Local App installed and original saved experiment restored. One browser-only intermediate-width title-layout minor deferred; see checkpoint report.
