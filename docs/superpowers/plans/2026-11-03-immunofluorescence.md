# Titan Immunofluorescence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax.

**Goal:** Complete the approved 2D IF import, measurement, segmentation, manual revision, batch, figure and portable project workflow alongside WB.

**Architecture:** Independent titan_if Python package and src/if React workspace. Shared engine and project library route by module. Background process jobs stage immutable masks/results, followed by explicit signature-checked acceptance.

**Tech Stack:** React 19, TypeScript, Tauri 2, Python 3.11, NumPy, SciPy, tifffile, scikit-image 0.25.2, Pillow, openpyxl.

**Spec:** ../specs/2026-11-03-immunofluorescence-design.md

## Global Constraints
- Raw/display/segmentation separate; biological sample is independent n.
- Retain existing WB behavior and project schema; no private image accuracy claims.
- Four channels, 4096² pixels/plane, 2 GiB/file, 256 MiB raw, 1 GiB working budget.
- Persistent confirmed uint32 masks; cancellable jobs never activate stale output.

## Review Focus
- Ambiguous axes or RGB data must never silently become quantitative channels.
- A new threshold or manual mask edit must invalidate old quantitative results.
- Async completion must not overwrite newer edits or user cancellation.
- Source relocation/portable save must preserve originals and manual mask versions.
- Batch grouping must not pool incompatible thresholds/batches or treat cells as n.

### Task 1: Image reading and quantitative algorithms
Files: backend/titan_if/images.py, analysis.py; tests/test_if_images.py, test_if_analysis.py.
Interfaces: exact signatures and field contracts in Spec.
- [ ] Write hand-derived failures for axes, dtype, ROI intensity and negative correction; run RED.
- [ ] Implement inspect/import/plane decode, region measurements, watershed, edits, aggregation.
- [ ] Verify compression, calibration, ambiguous dimensions, no signal, dense/edge nuclei, display invariance; run GREEN.

### Task 2: Portable projects, jobs, library and engine integration
Files: backend/titan_if/models.py, projects.py, jobs.py, service.py; engine.py/library.py, backend/entry.py; tests/test_if_projects.py, test_if_jobs.py.
Interfaces: Spec engine API and Python task contracts.
- [ ] Write failures for project locking, signature staleness, cancellation and mask persistence.
- [ ] Implement immutable artifacts, portable original copying, job process lifecycle and acceptance.
- [ ] Add module-aware library; retain WB defaults. Verify real subprocess job lifecycle and engine protocol.

### Task 3: Independent IF figures and result exports
Files: backend/titan_if/figures.py, tests/test_if_figures.py.
Interfaces: Spec figures APIs; images.load_channels and analysis.aggregate_results.
- [ ] Write failures for source-linked panels, no-calibration scale bars, shared ranges, SVG text and CSV/XLSX counts.
- [ ] Implement backend shared preview/export layout, crop, inset, merge, scale bars, sample scatter.
- [ ] Verify render dimensions, editable labels, export consistency and original pixel invariance.

### Task 4: React workspace and module routing
Files: src/if/*; src/App.tsx, src/ProjectLibrary.tsx, src/types.ts; browser and unit tests.
Interfaces: Spec engine API. Preserve WB shell and leave its model unchanged.
- [ ] Write behavior tests for displayed IF entry, synthetic workflow, ROI coordinates, stale job rejection.
- [ ] Implement module switch, IF library, metadata import dialog, channel display, original-coordinate ROI and label tools, results/figures.
- [ ] Add recipe freezing/application, cancellable progress, auto-save and project reopen; verify browser flow.

### Task 5: Integration validation and documentation
Files: requirements.lock, packaging/build_engine.py, docs/IF_USER_GUIDE.md, docs/checkpoint-reports/immunofluorescence.md.
- [ ] Run complete Python/TS/build/browser and Rust checks; fix demonstrated regressions.
- [ ] Verify packaged macOS engine and available native app workflow; record Windows/real-image gaps honestly.
- [ ] Fresh code review of complete branch; address important findings with regression tests.

## Execution decisions
- Approved design plus explicit implementation request authorizes execution without another plan approval.
- Component ownership is disjoint so image/analysis, figures, and React work may proceed concurrently after shared contracts are fixed; root owns persistence/jobs/integration.
- Work is isolated in codex/immunofluorescence. Keep original checkout/untracked branding intact.
