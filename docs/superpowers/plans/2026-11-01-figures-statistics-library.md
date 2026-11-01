# Publication figures, independent multigroup statistics and project library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use checkbox steps; no implementation agents. One fresh scoped review at the end.

**Goal:** 给Titan补齐可自定义论文柱图、解释清楚的独立多组统计，以及自动保存/可回找的项目与图形左栏。
**Architecture:** 保持原始像素/ROI/归一化合同；多组计算用独立模块和独立输出字段；图形设置为显示元数据，复用单一Matplotlib渲染器；本地库和图形快照以便携.titanwb为真源。前端只组织交互，后台校验统计设计、图形配置与文件事务。
**Tech Stack:** React/TypeScript、Python NumPy/SciPy1.17.1/Matplotlib/openpyxl、Rust/Tauri2；按需携带OFL中文字体与许可。
**Spec:** docs/superpowers/specs/2026-11-01-publication-figures-multigroup-design.md（已批准；左栏与自动保存补充已在聊天中说明并由用户选择）。

## Global Constraints
- 继续“内参→目标→结果”，图形与统计设置折叠，无第四个工作流页。
- 用户已选择只保留更新包，禁止替换或重启当前/Applications/Titan WB.app。
- 保留0.2.1已验证产物；新交付0.3.0，在当前隔离分支开发，不修改原源码工作目录或用户实验。
- 图形修改不影响原始测量/复核；推断只使用明确设计的独立生物学单位，不把泳道当n。
- 原两组Welch/配对t及其跨终点Holm家族行为保留；新多组结果不得混入旧Holm循环。
- 预览/PNG/SVG/Excel嵌图同一渲染器；图形与统计配置、家族、源版本必须可导出追溯。
- 原图hash、旧版本拒绝、锁/只读、v1另存升级、原子文件写入、不覆盖已有导出目录继续有效。
- 历史图冻结其源分析；重设样式与更换数据源分离。

## Review Focus
- 全缺失、n=1、零方差、跨独立组共享bio_id：保留位置和原因，不伪造误差线/p。
- Welch+Games–Howell仅显示对照时，调整家族仍为全两两；同时CI和图上每组均值CI不混同。
- 一个面板一种数值模式，缺对照不混用fold/raw；截断/裁剪必须显式标记。
- 项目切换/自动保存/晚到渲染/索引并发：不能覆盖新编辑或串图。
- 外部同名项目、同project_id副本、移动路径、图形历史与另存整体：不能丢身份、原图或历史。

### Task 1: 多组统计与描述性数值
**Files:** Create backend/titan_wb/multigroup.py, tests/test_multigroup.py; Modify analysis.py, types.ts, state.test.ts.
**Interfaces:**
- MultiGroupSpec: id, analyte, membrane_id, groups:string[], control_group:string|null, method:'descriptive'|'anova'|'welch_anova', scope:'control'|'all', scale:'raw'|'log2'. Optional project.settings.multigroup_comparisons[].
- compare_multigroup(values:list[BioValue],spec) -> {omnibus:dict, comparisons:list[dict]}; output rows include id, analyte, membrane/analysis block, scale, method, groups/n, effect and CI, p_adjusted, adjustment_method/family, rng_seed0 where applicable.
- AnalysisResult optional multigroup_omnibus[], multigroup_comparisons[]; old statistics[] untouched. Error returns explicit blocked row with reason, never silent group drop.
- group_summary(values) -> {n,mean,sd,sem,ci95}; n<2 error measures null, n0 mean null. CI uses t(n−1).
- Infer from .value (not .fold); require same single membrane, all selected groups n>=2, no duplicate/shared bio IDs, finite inputs, explicit positive log2. ANOVA ordinary df K−1/N−K; Welch df from weights formula. Tukey/GH effect B−A reverses SciPy i,j A−B CI endpoints. Dunnett is treatment−control, rng0 numerical integration. CI is simultaneous95%; log2 also returns consistently back-transformed ratio/CI.
- [x] RED: hand-derived F7/p.027 and WelchF6/p.0625; SD/SEM/tCI; control/all pair sets, B−A sign, simultaneousCI/p ranges, seed repeatability; n0/n1/zero variance, shared/duplicate IDs, cross-membrane, missing control, positive log2; existing Holm regression.
- [x] Implement pure helper and integrate only after design_confirmed; use locked SciPy APIs; method-specific adjustment metadata, no second hidden adjustment. Include trustworthy published fixed posthoc test vectors or independently derived distribution checks with tolerances.
- [x] GREEN: pytest multigroup/statistics/analysis/normalization; add state result validity test; commit scoped code.

### Task 2: 图形配置、分组数据与单一渲染器
**Files:** Create backend/titan_wb/figures.py, tests/test_figures.py, src/figure-settings.ts; Modify export.py, engine.py, models.py, types.ts, image-display/state tests; add licensed font asset and package data if required.
**Interfaces:**
- FigureSettings separate from legacy four-number PlotSettings. Fields: kind bar_points/bar/scatter, value_mode normalized/fold, error sd/sem/ci95/none, error_direction both/above, colors/borders/display_labels keyed by explicit group key, group_order[], point_marker circle/square/triangle, hollow, point_size, jitter, error_width/cap, bar_width, axis_width, title/title_italic,x_label,y_label,label_angle,y_min/y_max/y_step nullable, annotations none/p/stars, comparison_ids[], panel_key optional.
- validate_figure_settings(input,project,result) canonical settings; finite bounds/type/hex/labels/order validation, safe literal text. Project.figure_settings and optional project.plot_settings display metadata excluded from calculation fingerprint. The existing PlotSettings.font_size remains the single authority for font size, avoiding conflicting font controls. Invalid edits remain local UI draft.
- figure_data(project,result,settings) returns panels with declared expected groups (from target records/project, not only eligible biological), raw/fold arrays, n, summaries, clipping warnings and matching computed comparisons; no within-panel fallback; descriptive fold uncertainty caveat.
- plot_results retains legacy result/root/settings arguments and accepts optional figure_settings/project; export_preview/export payload gets separate figure_settings, response returns canonical figure_settings plus existing dimensions. Export snapshot/audit record settings and figure data; plot settings protocol remains compatible.
- [x] RED: mean/bar/point/error exact data, n0/n1/ND/NA, group order/colors stable, no mixed modes, missing fold, bad hex/NaN/range, deterministic jitter, B−A annotations use adjusted pairwisep not omnibus; style change retains measurement/review. PNG preview/export equality.
- [x] Implement renderer with reference yellow/gray style, free colors/details, explicit truncation notes; no fake significance. Offline CJK/Latin glyphs and font licensing; preserve old interactive legacy source plot.
- [x] GREEN: figures/export/workbook/format tests, unit build; commit.

### Task 3: 自动项目库与冻结图形文档
**Files:** Create backend/titan_wb/library.py, tests/test_library.py; Modify projects.py, engine.py, src-tauri/src/lib.rs, vite.config.ts; define TypeScript library/figure DTOs.
**Interfaces:**
- Rust session adds fixed library_root from app_local_data_dir()/library; writer ownership remains pid/token (do not let incidental context fields destabilize existing locks). Integration session injects mkdtemp test root, removed when server closes.
- library_list(session) -> entries[{entry_id,project_id,name,path,last_opened,figures:[metadata]}]; no arbitrary disk scan. Index keyed by entry ID/canonical path, not just scientific UUID; atomic JSON plus process-safe index mutex. Corrupt list errors visible, not empty overwrite.
- library_create(name,session) -> {project,entry}, save_project under root/Projects/UUID.titanwb. library_register(path,session) metadata reads, dedup canonical path; missing external path marked unavailable with relocation. Removal only drops index entry, not files.
- save_figure(project,result,settings,name,session,figure_id=None,expected_version=None) -> FigureDocument; only successful complete files committed under project/figures; snapshot source project/result, renderer PNG/SVG and settings/hashes. load_figure(path,id,session) -> frozen source project/result/settings/preview + metadata. History source version stored, editing styles appends a document version; replacing source only via explicit update action. Stable IDs and expected_version prevent concurrent overwrite.
- save_project to another directory carries figure catalog/history and referenced immutable originals; old project and history retained. Figure catalog independent of project scientific revision; source snapshots resolve original files relative to project root with traversal/hash guards.
- [x] RED: create/autosave/reopen, dedup and sameUUID copies, index interleave/corruption/missing path, readonly/foreign lock, safe paths, figure valid/stale source/re-style/explicit update, copy project with historical assets, failed render no official entry.
- [x] Implement library/figure documents with staged atomic commits, safe rollback of self-created temp files, no deleting user data. Original project source remains authoritative.
- [x] GREEN: library/projects/migration/engine tests, Rust tests. Integration cannot write user library. Commit.

### Task 4: 简洁图形/统计交互与左栏整合
**Files:** Create src/FigureEditor.tsx, src/MultiGroupEditor.tsx, src/ProjectLibrary.tsx, src/FigureDocument.tsx and focused state helpers; Modify App.tsx, LaneResults.tsx, ExportPreview.tsx, ComparisonEditor.tsx, style.css; browser tests.
**Interfaces:**
- FigureEditor uses local valid/invalid draft, one canonical renderer and late-response guard; persist accepted figure settings via onEdit, no numerical recalculation. Common controls visible, advanced collapsed. Save current/Save new/Use current analysis explicit.
- MultiGroupEditor shows explicit groups/control, method/scope/scale and contextual explanations: question/assumptions/n/family/limitations; descriptive default. Only settings change triggers recompute, no automatic method-by-p selection.
- ProjectLibrary shows create/open/search/recent project tree -> workspace/results/figure docs. Inner protein switching remains in workspace. Current project expanded, others collapsed; historical docs show source version and stale badge, load frozen source independent of live project state.
- New experiment creates managed local project, manual save flushes, Save as chooses external copy. Register successful manual opens/saves/exports. First formal saved/generated chart and successful exports appear in tree; preview-slider frames do not create entries. Default formal figure keyed per endpoint, selected variants stored by explicit Save new. Errors retain work and never switch after a newer edit; switching auto-managed dirty project flushes safely or stays on failure. Existing legacy demo/manual interactions and source navigation stay functional.
- [x] RED browser/state: auto project persists/reload opens, left tree fig/data selection, format changes no review loss, three independent groups inference + explanation + colors/CI/annotations, snapshot old source after current data edit, export workbook/image and cancellation/late responses. Existing 21 browser tests remain meaningful (update UI expectations only for deliberate layout changes).
- [x] Implement and visually inspect at standard/large text sizes; screenshot chart+controls and sidebar. No invented user data, fixtures clearly synthetic.
- [x] GREEN Vitest/build/browser and scoped Python; commit.

### Task 5: Excel/审计/包交付
**Files:** Modify workbook.py, scripts/verify_release.py, verify_lane_release.py; add fixture/standalone verification and report; version files0.3.0, guide/changelog/native checklist.
**Interfaces:** Excel adds group summaries, multigroup omnibus and simultaneous pairwise comparisons as separate sheets; existing Holm sheet remains accurately labelled. Include figure settings/source/units, adjustedp and CI methods; missing remains blank and text literal. Archive record links exact exported figure.
- [ ] RED: workbook fixed cells and source IDs, style+method metadata, snapshot export, PNG/Excel media match, p not0; legacy export still complete.
- [ ] Implement export and docs, full pytest/Vitest/Rust/build/browser; one fresh scoped review of whole follow-up diff from a00d80b, fix Important once with regressions.
- [ ] Build signed Mac0.3.0 onedir+App, independent cleanPATH checks of figures/statistics/library/Excel, ZIP extraction+signature/hash, collect notices/font license. Keep0.2.1 and user's installed0.2.0 unchanged.
- [ ] Record exact checks and remaining Prism/native/Windows/real-WB evidence limits, link ready update package. No push/publish/merge or installation.
