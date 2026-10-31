# Titan WB 泳道优先分析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 通过“内参 / 目标 / 结果”三个主步骤完成稳定泳道测量与归一化；同步简化 UI，并解决导入延迟与灰度显示兼容问题。

**Architecture:** 保留现有原始像素、ROI/背景积分、样本与归一化合同；新增独立泳道几何布局与按蛋白分组的测量状态。常驻 worker 和缓存承接分步交互，识别只提出候选，确认后才成为正式测量输入。

**Tech Stack:** Tauri 2 / Rust / Tokio、React 19 / TypeScript、Python 3.11 / NumPy / Pillow / tifffile；沿用现有统计与绘图依赖，不引入深度学习模型。

**Spec:** [2026-10-31-lane-first-analysis.md](../specs/2026-10-31-lane-first-analysis.md)。数值与边界以此设计为准；性能数字均为待验收目标。

## Global Constraints

- 保留多页选择、页码、原文件 SHA256，以及单文件 50 MiB / 每页 2500 万像素限制。
- 同一原始泳道的目标与内参共用 lane_id。不同膜分别建布局，禁止依据图片顺序或相近位置自动跨膜绑定。
- 未检出保持该泳道的空位，结果为空并附原因；未检出不自动等同数值 0，不重新排列后续泳道。
- “显示反色”不改变原始像素、分析极性、ROI、有效结果和复核状态。
- UI 与算法在同一轮交付；只保留“内参 / 目标 / 结果”三个主步骤，泳道设置并入内参页，不增加独立工作台或平行导航。
- 当前任务面板默认最多 4 个可编辑字段、同时只显示 1 个主要动作。正常流程使用拖选/拖动，不要求输入像素坐标，不要求展开高级设置；重复样本关系与未变化的测量不重复填写、确认。
- 数值阈值、平滑、内部 ID、IBC 等按需展开；缺失信号方向/编码上界等测量阻塞须在当前步骤明确提示。简化界面不能隐去缺失值或跳过必要的科学确认。
- 首轮沿用确认背景 ROI 并集均值的净积分；不悄悄更换背景算法。
- 旧 v1 项目首次迁移保存写入新副本；保留原项目和已有 ROI 的人工编辑能力。
- 本轮以直泳道为主；不实现弯曲泳道自动展开、大角度校正或原图重采样。
- 保留现有 macOS 14+ Apple Silicon / Windows x64 支持范围；跨平台声明依赖实际构建与验收。
- 当前工作区已有大量未提交修改。执行前保留当前内容并建立可复现基线；不能直接从 HEAD 开工而遗漏已安装的多页更新，不能 reset/stash/整体覆盖现有修改。
- 本计划仅规划；编写计划不执行产品修改、提交、发布或覆盖安装。

## Review Focus

1. 中间泳道弱信号/缺失：其余样本保持身份，人工确认数量冲突。归 Task 4/6/7。
2. 同膜多张裁剪图尺寸或偏移不同：每图使用原始坐标，手动对齐不改变像素。归 Task 3/6。
3. 反向灰度 LUT 与 16 位页面同时存在：显示方向不能误改计算方向。归 Task 2/8。
4. worker 崩溃、超时、取消或切换项目：缓存/响应不能写错项目，退出无孤儿进程。归 Task 1/7。
5. v1 项目里只有手画 ROI、没有泳道布局：仍可检查原数据，不猜边界，不覆盖旧项目。归 Task 3/8。

## 执行顺序与交付点

| 顺序 | 工作 | 可独立检查的交付 |
|---|---|---|
| 1 | 常驻引擎、资源打包与缓存 | 保持旧功能，安装版交互不再重复冷启动 |
| 2 | 灰度调色板、MINISWHITE、显示反色 | 用户 TIFF 两页均能按明确语义处理 |
| 3 | 稳定泳道/测量集合模型、旧项目迁移 | 位置与样本身份分离，缺失可被记录 |
| 4 | 自动建议泳道 | 可调整并确认的一组纵向泳道 |
| 5 | 泳道曲线、候选峰和背景 | 每个泳道独立测量，积分与原合同一致 |
| 6 | 三步简洁 UI、内参优先与逐目标对齐 | 无需像素坐标或重复样本配置的完整流程 |
| 7 | 自动关联、结果失效与归一化 | 正确样本的目标/内参比值及异常状态 |
| 8 | 独立对照、原生验收与打包安装 | 有证据的更新包和操作说明 |

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8。每阶段先通过验收再扩展下一阶段；本轮先采用直接依赖明确的顺序执行。

UI 的默认流程以 Spec 的“简化 UI 的具体约束”为准。Task 2 随图像兼容性增加轻量显示控件；Task 4/5 的输出用于可编辑覆盖层和按需曲线；Task 6 整合三步主流程；Task 7 将结果和异常直接接回当前步骤。最终交付包含整套 UI，不将其留作算法更新后的额外项目。

---

### Task 1: 消除重复冷启动并建立受控缓存

**Files:** Modify `src-tauri/src/lib.rs`, `src-tauri/Cargo.toml`, `src-tauri/tauri.conf.json`, `src-tauri/tauri.windows.conf.json`, `backend/entry.py`, `backend/titan_wb/engine.py`, `backend/titan_wb/images.py`, `packaging/build_engine.py`, `scripts/verify_release.py`, `vite.config.ts`; Create `src-tauri/src/engine_worker.rs`, `backend/titan_wb/image_cache.py`, `tests/test_engine_server.py`, `tests/test_image_cache.py`, `scripts/benchmark_import.py`; extend `tests/test_packaging.py` and release workflow resource paths.

**Interfaces:**
- Preserve frontend `callEngine<T>(command, payload): Promise<T>` and existing one-request stdin JSON CLI.
- Add `serve(input_stream, output_stream) -> None` selected by `--stdio-server`; line envelopes contain `request_id`, `ok`, `data`, `error`. Runtime protocol remains 1 for existing commands; advertise `transport_version: 2` separately in health to avoid conflating command compatibility with framing.
- Rust `EngineWorker::request(request: Value) -> Result<Value, String>` owns one child, request IDs, a bounded queue of 32 and a 60 s execution timeout. Add Tokio sync support. Child exits with App; restart after failure applies to the next request, without automatic replay of save/export mutations.
- `ImageCache.get_pixels(path, sha256, page_index) -> ndarray` validates file hash before quantitative use; LRU pixel limit 256 MiB, previews/profiles combined 32 MiB. Cache keys include page and numerical inputs.
- onedir engine resources resolve through Tauri resource_dir on macOS/Windows; development continues using the local Python source.

- [x] **Step 1 — Write regression tests:** server handles two sequential requests in one PID; malformed/oversized line produces a bounded error; unknown request IDs cannot satisfy another caller; worker death/timeout allows a fresh later health check; shutdown terminates child. Cache tests assert different pages never share pixels, changed source raises despite cached data, and eviction obeys the byte limit.
- [x] **Step 2 — Run red:** `PYTHONPATH=backend .venv/bin/python -m pytest tests/test_engine_server.py tests/test_image_cache.py tests/test_packaging.py -q`; Rust worker tests through `cargo test --manifest-path src-tauri/Cargo.toml`. Verify failure is from missing behavior.
- [x] **Step 3 — Implement worker and packaging:** keep the existing dispatch allowlist; stdout carries protocol only, stderr carries diagnostics. Process one request at a time, match IDs, cap messages at 20 MiB. Build onedir resources with full runtime files and update verification/CI paths together. Cache only immutable decoded arrays; retain hash checking.
- [x] **Step 4 — Verify green and measure:** run Step 2 plus `scripts/benchmark_import.py` against the installed/copied bundle from a clean PATH. Record 5 cold starts and 5 warm import sequences. Targets: ready ≤3 s; warm page listing ≤1 s, preview ≤1 s, selected-page import ≤2 s for the local 12 MB fixture. Include startup count=1 per uninterrupted App session. Investigate misses before claiming speedup.
- [x] **Step 5 — Stage scoped deliverable for review:** show exact files and measured before/after report; retain source-only and native-package measurements separately. Commit only this task's files when committing is authorized.

### Task 2: 兼容灰度调色板并分离显示反色

**Files:** Modify `backend/titan_wb/images.py`, `src/types.ts`, `src/state.ts`, `src/ImagePagePicker.tsx`, `src/Workspace.tsx`; Create `src/image-display.ts`, `src/image-display.test.ts`; extend `tests/test_image_pages.py`, `src/state.test.ts`, `tests/browser/image-pages.spec.ts`.

**Interfaces:**
- Extend ImageAsset with `display_inverted: boolean` and optional immutable photometric/LUT metadata; old assets default to normal display.
- `decode(path, page_index=None)` continues returning original 2D numeric data. Palette input returns source indices, never RGB-rendered pixels. An internal metadata reader separately reports grayscale-vs-color LUT and suggested display direction.
- Preserve inspect/preview/import command names; inspection explicitly states page format, support and reason. UI applies display inversion locally without another engine call.

- [x] **Step 1 — Write regression tests:** grayscale inverted palette fixture has equal R/G/B LUT channels and source indices `[0, 64, 255]`; decode must return exactly those indices. LZW palette decoding works without imagecodecs through a value-preserving Pillow path. MINISWHITE uint16 `[0, 4095, 65535]` values stay unchanged. Color LUT is not silently made quantitative. Display toggle preserves measurement, valid result and review state, including after save/reopen.
- [x] **Step 2 — Run red:** `PYTHONPATH=backend .venv/bin/python -m pytest tests/test_image_pages.py -q`; `npm test -- src/image-display.test.ts src/state.test.ts`.
- [x] **Step 3 — Implement compatibility and controls:** use original P-mode indices for palette LZW fallback, validate bit depth/shape, distinguish “显示反色” from “原始信号方向”. Exclude display-only fields from numerical invalidation/cache keys; preserve source metadata for export. Preview reflects LUT direction without mapping LUT values into measurement data.
- [x] **Step 4 — Verify green:** rerun Step 2 and `npx playwright test tests/browser/image-pages.spec.ts`. Check the user's TIFF locally: both pages are identified accurately, its 8-bit gray LUT is accepted, 16-bit display can be reversed without numerical changes. Do not add the user's file to git.
- [x] **Step 5 — Review scoped deliverable:** compare raw arrays, display settings and result revisions before/after. Include only these files in any authorized commit.

### Task 3: 保存稳定泳道布局和逐蛋白测量状态

**Files:** Modify `backend/titan_wb/models.py`, `backend/titan_wb/projects.py`, `src/types.ts`, `src/state.ts`, `src/test-project.ts`; Create `backend/titan_wb/migrations.py`, `tests/test_lane_models.py`; extend `tests/test_projects.py`, `src/state.test.ts`.

**Interfaces:**
- Implement the Spec's `LaneLayout`, `BandSet` and assignment types with exactly its field names/statuses; Project v2 adds `lane_layouts` and `band_sets`. ROI links `lane_layout_id` / `band_set_id` remain optional for legacy manual ROIs.
- `migrate_project(data: dict) -> dict` creates an in-memory v2 copy of v1, initializes new arrays empty, retains original IDs and marks upgrade-copy saving as required. Already-v2 input is validated; future versions are rejected.
- Layout columns reference existing lane IDs. BandSet reference_set_id must identify a reference-role set on the same membrane; assignments/ROIs must agree on lane/image/analyte/role and cannot silently duplicate one formal measurement.

- [x] **Step 1 — Write regression tests:** moving L3's rect retains L3/sample identity; a not_detected L3 assignment has roi_id=null and L4 stays L4. Reject duplicate columns, overlapping/out-of-bounds confirmed lane rectangles and cross-membrane references. A v1 fixture preserves all original IDs/ROI values, gains empty layouts, and saving its migration requires a different project path.
- [x] **Step 2 — Run red:** `PYTHONPATH=backend .venv/bin/python -m pytest tests/test_lane_models.py tests/test_projects.py -q`; `npm test -- src/state.test.ts`.
- [x] **Step 3 — Implement schema and persistence:** normalize missing legacy display metadata; migrate on open without overwriting disk. Keep legacy ROIs editable without fabricating geometry. Geometry/source-page/sample changes invalidate affected approval and numerical results; display toggles do not. Update existing schema assertions to v2 and retain explicit v1 migration fixtures.
- [x] **Step 4 — Verify green:** run Step 2, save/reopen independent copies, check originals hashes and page indices. A new save must leave the old v1 manifest/asset bytes unchanged.
- [x] **Step 5 — Review scoped deliverable:** inspect v1→v2 manifest difference and an incomplete-lane example; include only relevant files in any authorized commit.

### Task 4: 自动建议纵向泳道，人工确认后固定身份

**Files:** Create `backend/titan_wb/lanes.py`, `tests/test_lane_detection.py`; Modify `backend/titan_wb/detection.py`, `backend/titan_wb/engine.py`, `src/types.ts`, `src/workflow.ts`, `src/workflow.test.ts`.

**Interfaces:**
- `propose_lanes(pixels, window: Rect, *, excluded_regions: list[Rect], expected_count: int | None, polarity: str, ceiling: float | None) -> dict`.
- Result: `columns: [{rect: Rect, confidence: high|low, reasons: string[]}]`, `expected_count`, `requires_review: bool`; proposals have no committed lane IDs yet.
- Add engine command `detect_lanes` with image_id/window/excluded_regions/expected_count. `acceptLaneLayout(project, proposal, mapping) -> void` creates or reuses explicit lane IDs only after user confirms one-to-one sample mapping.

- [x] **Step 1 — Write regression tests:** synthetic five-lane reference fixture has five known centers; very bright excluded marker cannot suppress weak sample candidates; middle weak/blank lane with expected_count=5 remains an uncertain slot. Close/merged peaks or flat data require manual review. Accepted columns are ordered, disjoint and bounded. Filtering candidate 3 must not rebind candidate 4 to sample 3.
- [x] **Step 2 — Run red:** `PYTHONPATH=backend .venv/bin/python -m pytest tests/test_lane_detection.py -q`; `npm test -- src/workflow.test.ts`.
- [x] **Step 3 — Implement proposals:** operate on a detection-only copy of the selected region; use local background correction, horizontal projection, noise-aware local maxima, spacing/valley evidence and optional expected count. Do not threshold all lanes against the single brightest peak. Low-confidence inferred slots stay visibly uncertain; no hidden automatic acceptance.
- [x] **Step 4 — Verify green:** run Step 2; on the user's image, select analysis region and marker exclusions, compare proposed count against a manually confirmed count. Record proposals/corrections, without guessing actual sample identities.
- [x] **Step 5 — Review scoped deliverable:** inspect weak/missing/merged scenarios and mapping stability; include only relevant files in any authorized commit.

### Task 5: 每泳道曲线、候选峰、背景与精确积分

**Files:** Create `backend/titan_wb/bands.py`, `tests/test_lane_profiles.py`, `tests/test_band_detection.py`; Modify `backend/titan_wb/profiles.py`, `backend/titan_wb/engine.py`, `backend/titan_wb/quantify.py`, `src/types.ts`, `src/SignalProfile.tsx`.

**Interfaces:**
- `lane_profile(project: dict, layout_id: str, lane_id: str, window: Rect | None=None) -> dict`: returns project_id/input_revision/layout_id/lane_id plus display samples containing y/mean/sum/min/max. Full-resolution data remains the source for measurement.
- `propose_bands(project: dict, band_set_id: str, settings: dict) -> list[dict]`: each proposal carries lane_id, candidate rect/background rectangles, status and ambiguity reasons. It does not create accepted ROIs.
- Formal accepted ROI measurement continues through `measure(image, roi, backgrounds, polarity, ceiling)` with the existing union-background definition.

- [x] **Step 1 — Write regression tests:** for a 4×4 bright patch of value 3000 over background 1000, corrected integral is 32000. Doubling lane width with duplicated pixels doubles integral, not just curve mean. Full curve sum minus its matching constant background baseline equals measure. Two peaks require explicit selection; no peak gives no fake zero measurement; narrow peaks survive display decimation and full-resolution integration.
- [x] **Step 2 — Run red:** `PYTHONPATH=backend .venv/bin/python -m pytest tests/test_lane_profiles.py tests/test_band_detection.py tests/test_profiles.py tests/test_scientific_boundaries.py -q`.
- [x] **Step 3 — Implement profile and peak proposals:** restrict search to the user-specified protein window within each confirmed lane; use local noise/prominence and minimum width to propose full peak intervals. Keep tails inside the accepted interval, recommend separate background regions and expose invalid overlap/other-band conflicts. Use the existing measurement function for all official integrals.
- [x] **Step 4 — Verify green:** run Step 2; compare positive/negative net signals and clipped pixels against pre-existing numerical behavior. Background suggestions and peak proposals remain editable and unreviewed until accepted.
- [x] **Step 5 — Review scoped deliverable:** inspect curve/ROI/background correspondence and exact-sum equivalence; include only relevant files in any authorized commit.

### Task 6: 三步简洁 UI、内参优先与逐目标模板对齐

**Files:** Create `src/LaneSetup.tsx`, `src/LaneLayoutEditor.tsx`, `src/BandSetEditor.tsx`, `src/LaneProfilePanel.tsx`, `src/lane-workflow.ts`, `src/lane-workflow.test.ts`, `tests/browser/lane-workflow.spec.ts`; Modify `src/App.tsx`, `src/Workspace.tsx`, `src/ProjectNavigator.tsx`, `src/SampleEditor.tsx`, `src/workflow.ts`, `src/style.css`.

**Interfaces:**
- `acceptLaneLayout` from Task 4 persists the confirmed layout. `createBandSet(project, layoutId, analyte, role, referenceSetId?) -> string` creates complete pending assignments for all layout lanes.
- `alignLaneLayout(project, layoutId, {dx, dy, scaleX, anchorX}) -> void` updates raw-coordinate rectangles with integer rounding; `setLaneRect(project, layoutId, laneId, rect) -> void` edits one lane. Invalid overlap/out-of-bounds changes are rejected atomically.
- `acceptBandAssignments(project, bandSetId, choices) -> void` creates ROIs only for explicitly accepted candidates; missing/excluded choices preserve lane slots. Never use candidate array index as the final sample mapping.
- Frontend workflow has exactly `reference | targets | results` main stages; reference stage includes lane setup. A single context panel owns the current primary action; selected-lane curves and advanced settings expand in place. Reuse the existing visual theme and common controls.

- [x] **Step 1 — Write regression tests:** browser workflow builds reference layout → confirms reference → creates two targets with the same stable sample IDs. The three main stages are 内参/目标/结果; no separate lane-setup navigation is required. Each default task panel has ≤4 visible editable fields and exactly one primary action. Complete the normal path with pointer region/boundary editing, without numeric y coordinates or opening advanced settings. Adding the second target reuses sample mapping; unchanged confirmed inputs do not prompt again. Whole-strip selection only sets an analysis window, not a formal ROI. Offset/spacing edits update template overlays but raw-image hash/pixels stay unchanged. Cancel/undo restores state; missing middle lane remains visible, read-only blocks editing, legacy manual ROIs remain accessible.
- [x] **Step 2 — Run red:** `npm test -- src/lane-workflow.test.ts`; `npx playwright test tests/browser/lane-workflow.spec.ts`.
- [x] **Step 3 — Implement guided screens:** provide “内参 / 目标 / 结果” stages; embed lane setup in reference. Keep the main canvas dominant, the existing side area limited to a concise protein list and the context panel limited to the current action. Show clear boundary/peak/background overlays, membrane/lane/sample identity during confirmation, and curves only when a lane is selected or expanded. Use region dragging, fixed-position save/undo/zoom/invert controls, and in-place manual adjustment; move thresholds/coordinates/IBC/internal IDs to advanced settings. Reuse same-image layouts directly; another crop/image requires explicit alignment and mapping confirmation. Normal high-confidence suggestions are confirmed together after preview; unresolved lanes stay visibly pending. Preserve manual ROI access without adding a parallel main workflow.
- [x] **Step 4 — Verify green and inspect layout:** run Step 2 and existing workflow browser tests. Capture 1440 px and 1080 px views with standard/large text. Inspect the empty first-use state, reference confirmation, target addition and results. Confirm the three-step path, default field/action limits, no unnecessary metadata/card wall, and no need to open advanced settings in the normal workflow. Primary controls and selected-lane curves remain usable; late profile responses cannot replace a newly selected lane or another project.
- [x] **Step 5 — Review scoped deliverable:** walk through the user's actual TIFF after they confirm the intended reference/target identities; do not infer protein names or group labels from the image. Include only relevant files in any authorized commit.

### Task 7: 自动关联内参、按样本归一化与结果失效

**Files:** Modify `backend/titan_wb/analysis.py`, `backend/titan_wb/normalization.py`, `backend/titan_wb/export.py`, `src/state.ts`, `src/Results.tsx`, `src/QualityPanel.tsx`, `src/lane-workflow.ts`, `src/App.tsx`; extend `tests/test_analysis.py`, `tests/test_normalization.py`, `tests/test_export.py`, `src/state.test.ts`, `tests/browser/lane-workflow.spec.ts`.

**Interfaces:**
- `linkReferenceSet(project, targetSetId, referenceSetId) -> void` links accepted target ROIs only by the explicit reference set and stable lane_id; same membrane and matching lane identity are mandatory.
- `buildLaneResultRows(project, result)` yields rows by membrane_id/lane_id/sample_id/analyte, including null values and status reasons for missing assignments; original biological and technical replicate aggregation remains unchanged.
- Reuse `analyze` plus project_id/input_revision acceptance. Debounce ready-input edits by 300 ms; input still awaiting confirmation shows pending instead of firing misleading normalization. Display-only edits do not trigger recalculation.

- [x] **Step 1 — Write regression tests:** target net 32000 / reference net 8000 gives exactly 4. A missing lane returns null and leaves the next lane's ratio unchanged. Wrong membrane, multiple unselected reference sets, missing/nonpositive/clipped/unreviewed reference never produce a valid ratio. Changing one reference invalidates its dependents; stale results after edits/project switches are discarded. Display inversion preserves the numerical result. Technical repeats do not increase biological n. Without explicitly configured grouping/replicate identity, lane ratios remain available but the UI does not claim biological n or run a group comparison from provisional IDs.
- [x] **Step 2 — Run red:** `PYTHONPATH=backend .venv/bin/python -m pytest tests/test_analysis.py tests/test_normalization.py tests/test_export.py -q`; `npm test -- src/state.test.ts src/lane-workflow.test.ts`.
- [x] **Step 3 — Implement linking and result readiness:** remove positional matching from the new path; retain the old explicit manual matching route. Default results show lane/sample, reference/target values and ratios; expand raw integrals, background, audit and statistics on demand. Grouping/replicate configuration is only required when asking for biological summaries or group comparisons, never inferred from provisional lane/sample IDs. Make assignment status, missingness and blocked normalization visible and locatable on the source image. Schedule only valid/confirmed inputs; preserve flags and provenance rather than silently dropping rows. Export layouts, source page/LUT, confirmed regions/background, mappings, measurement method and revisions.
- [x] **Step 4 — Verify green:** run Step 2 plus `npx playwright test tests/browser/lane-workflow.spec.ts tests/browser/workflow.spec.ts`. Update a reference measurement and confirm all eligible related ratios refresh, while unrelated sample identities remain fixed. Save/reopen/export must reproduce the same values.
- [x] **Step 5 — Review scoped deliverable:** compare assignment table, source ROIs and exported numerical rows for both complete and incomplete lanes; include only relevant files in any authorized commit.

### Task 8: 独立数值对照、原生验收与更新包

**Files:** Create `scripts/fiji_reference.ijm`, `tests/test_lane_workflow_golden.py`, `docs/checkpoint-reports/lane-first-update.md`; Modify `scripts/verify_release.py`, `scripts/benchmark_import.py`, `docs/USER_GUIDE.md`, `docs/NATIVE_ACCEPTANCE.md`, `CHANGELOG.md`, packaging/release version files as appropriate.

**Interfaces:**
- Fiji macro consumes a known-value grayscale fixture and explicit rectangle/background coordinates; emits RawIntDen/Area/background Mean in CSV. Independent expected net is RawIntDen − Area × BGMean; compare like-for-like, not scaled Gel Analyzer plot area.
- `scripts/benchmark_import.py` emits JSON with platform/bundle identity/file size/page count, cold startup and warm listing/preview/import times, cache state, repeats and worker startup count.
- Release verification consumes an onedir bundle away from the source tree with clean PATH, then checks worker, import, measurement, migration/save/reopen/export and signature/resource integrity.

- [x] **Step 1 — Prepare honest acceptance fixtures:** known-value synthetic lanes with hand-derived expected values, weak/missing/merged lanes, a bright excluded marker, grayscale inverse-LUT and 16-bit equivalent pixel fixtures. Include v1 migration and same-membrane offset-layout cases. Keep the user's TIFF local and do not invent its sample count or biological ground truth.
- [x] **Step 2 — Run the full suite:** `PYTHONPATH=backend .venv/bin/python -m pytest -q`; `npm test`; `npm run build`; `npm run test:e2e`; `cargo test --manifest-path src-tauri/Cargo.toml`. Use pytest, not unittest discovery alone, so function-based tests are included. Every failure must be resolved or named in the report.
- [ ] **Step 3 — Run independent/numerical and performance checks:** execute the Fiji macro if Fiji is available; if not, leave independent Fiji comparison pending rather than claiming it passed. For matching ROIs/background, require relative difference ≤1e-6 or absolute difference ≤1e-6 near zero, and explain any unit/rounding discrepancy. Run the Spec's 5-repeat package benchmarks and report actual median/max, not just thresholds.
- [ ] **Step 4 — Build and inspect native workflows:** macOS installed App and Windows artifact/CI must find their resource engine without source Python. Check first import, palette/16-bit page display, reference-first flow, offset target, missing lane, cancellation, worker restart, save/reopen, export and clean exit. Verify original file hashes remain unchanged. Do not claim Windows native interaction without Windows evidence.
- [x] **Step 5 — Deliver reviewable update:** update Chinese guide and changelog with actual behavior and remaining limitations. Create a separately named update artifact, verify signatures/resources, preserve the existing installation until the new bundle is verified. During installation preserve existing projects and do not force-quit an App with unsaved edits. Publishing a release is a separate action, not part of merely producing this plan.

## 完成判据

- 主界面只有“内参 / 目标 / 结果”三个步骤；新用户能不输入像素坐标、不打开高级设置完成正常流程，添加第二个目标不重复配置样本。
- 默认任务面板最多 4 个可编辑字段、1 个主要动作；原图与必要覆盖层占主导，曲线和高级内容按需展开，异常可直接定位处理。
- 同一排的样本形成各自的纵向泳道，不再被一个横向长框合并测量。
- 内参先确认，后续目标复用稳定泳道；中间未检出不会造成后续错位。
- 对同一原图和确认 ROI/背景，新流程积分与现有数值合同一致；给定已知输入的目标/内参比值可独立重算。
- 显示反色不影响定量，用户文件的灰度调色板和 16 位页均按明确语义保留。
- 常驻 worker、安装包资源定位、5-repeat 性能报告及异常恢复有证据。
- 旧项目能检查并另存升级，保存重开/导出保留布局、页码、来源与数值。
- 自动化测试、独立测量对照、原生界面验收分别报告；未做的检查明确留为待验收。

## 自审与执行交接

已将 Spec 的性能、兼容、数据模型、泳道、峰/背景、交互、归一化和交付分别落到 Task 1–8；Review Focus 的五类输入均有对应测试任务。常驻传输以 transport_version 区分，不修改既有 health protocol=1；schema 升级单独处理，不混淆协议与项目格式。

建议在当前聊天顺序执行并在关键交付点独立审查：这些任务共享模型/接口，顺序推进能减少接口返工。执行方式并非用户已选定；本次交付停在更新计划，不开始修改产品或覆盖已安装 App。


## 2026-11-01 执行状态

Task 1–7 已实现并验证；Task 8 的合成数值对照、全量回归、Mac 打包/签名/安装及 5 次性能测量已完成。Fiji 未安装，独立对照留待执行；Windows 本机验证未执行。原生窗口接口对 Titan 与运行中的访达均超时，GUI 操作留待验收，不计为通过。详见 `docs/checkpoint-reports/lane-first-update.md`。上述 Task 8 第 3/4 步保留未勾选，以反映这些剩余验收。
