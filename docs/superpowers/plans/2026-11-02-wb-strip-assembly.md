# WB Strip Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, editable WB strip figure with default layout, preserved source images, and PNG/SVG exports.

**Architecture:** Keep WB documents separate from quantitative Project revisions and statistical figures, under `figures/wb/`. Python validates source snapshots and renders the same physical layout to PNG and SVG; React manages document drafts, cropping and history. Integrate a dedicated project view without requiring an AnalysisResult.

**Tech Stack:** Existing React/TypeScript, Tauri IPC, Python, Pillow, NumPy and Matplotlib font discovery.

**Spec:** `docs/superpowers/specs/2026-11-02-wb-strip-assembly-design.md`

## Global Constraints

- WB remains free and local; no login, payment or network dependency.
- Default width 85 mm, text 8 pt, row gap 3 mm, PNG 300 DPI with optional 600 DPI.
- Continuous rectangular source crops; preserve image aspect ratio, whole-image display mapping and source identity.
- Distinguish expected protein MW text from marker labels anchored in source y coordinates.
- Save/reopen/version documents independently from analysis results; preserve project-copy portability and original hashes.

## Review Focus

- Unanalyzed projects must support manual cropping, saving and export.
- Multi-page/inverted/rotated sources must match source crop coordinates and display mapping.
- Delayed previews, saves or navigation must never replace another document or project.
- A source removed from the current image list must remain available in saved figures and project copies.
- Invalid/oversized layouts, missing sources and old document versions must fail safely without overwriting work.

## Task 1: Source-safe rendering and document persistence

**Files:** Create `backend/titan_wb/wb_figures.py`, `backend/titan_wb/wb_render.py`, `tests/test_wb_figures.py`; modify `backend/titan_wb/engine.py`, `backend/titan_wb/projects.py` if needed for source preservation.

**Interfaces:** `new_document(project) -> dict`; `preview_document(project, document) -> dict` returns validated document, PNG data URL and physical layout; `save_document(project, document, session, expected_version=None) -> dict`; `list_documents(project) -> list`; `load_document(project, document_id) -> dict`; `export_document(project, document, destination) -> dict`. Sources stored in row snapshots; safe project-relative paths on disk, resolved only after containment/hash checks. Schema version 1.

- [ ] Write failing tests for known-pixel crop, rotation/page mapping, label escaping, embedded SVG, DPI/aspect ratio, source hash checks, limits, save/reopen/conflicts/copy and read-only behavior.
- [ ] Run `.venv/bin/python -m pytest tests/test_wb_figures.py -q`; expect missing module/API failures before implementation.
- [ ] Implement physical layout with shared row raster and text positions, authoritative backend validation, atomic document versions and exports, IPC commands with `wb_` prefix. Reuse project locks, original preservation and bundled font.
- [ ] Run `.venv/bin/python -m pytest tests/test_wb_figures.py tests/test_library.py tests/test_projects.py -q`; expect all pass, then commit task files.

## Task 2: Editable figure state and project UI

**Files:** Create `src/wb-figure.ts`, `src/wb-figure.test.ts`, `src/WbFigureEditor.tsx`, `src/WbCropEditor.tsx`, `src/wb-figure.css`; modify `src/App.tsx`.

**Interfaces:** WB types live in `src/wb-figure.ts`, mirroring backend schema. Editor consumes `project`, `onBeforeSave: () => Promise<Project>`, `onDraft: (dirty:boolean) => void`; uses Task 1 IPC methods. Source crop interaction returns integer half-open rects. Default construction and style-reset utilities are pure.

- [ ] Write failing state tests proving crop proposals preserve continuous rectangles, known lane labels use actual coordinates, ambiguous mappings prompt review, and restoring defaults preserves row content.
- [ ] Run `npm test -- src/wb-figure.test.ts`; expect missing exports before implementation.
- [ ] Implement a quiet two-pane workspace: central white figure sheet and source crop preview, compact right inspector, row list, document selector, undo/redo, draft guards. Preserve existing Titan type/colors; avoid new branding or animated decoration. Route global undo to the editor in this view.
- [ ] Run `npm test` and `npm run build`; expect all pass, then commit task files.

## Task 3: Browser acceptance, docs and whole-change review

**Files:** Create `tests/browser/wb-figures.spec.ts`; modify `docs/USER_GUIDE.md`, `README.md`.

**Interfaces:** Use actual integration engine and browser flow with synthetic images; screenshots saved to `artifacts/`. Existing analysis and statistical-figure routes stay compatible.

- [ ] Write/run failing browser tests before integration is finished: create without analysis, crop and confirm, labels/marker editing, save/reopen, SVG/PNG export, guard unsaved navigation and switch documents without stale preview.
- [ ] Complete missing UI integration, run `npm run test:e2e -- tests/browser/wb-figures.spec.ts` and inspect screenshot.
- [ ] Run full Python/frontend/browser suites plus production build; inspect file diff and rendering artifacts.
- [ ] Document operation and actual acceptance boundaries; commission one independent whole-change code review, fix material findings with regression tests, and commit verified changes.

## Execution record

User authorized execution after reviewing the design. Continue inline in the existing `codex/results-ui-polish` checkout, preserving unrelated untracked brand explorations. No merge, push or release is part of this task. No further plan confirmation is required.
