# Excel 与结果可视化补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 补齐已授权结果/导出流程中遗漏的真正 Excel 工作簿与直接可见的结果图。
**Architecture:** 复用既有全精度计算结果、Matplotlib PNG/SVG、过期版本与原子导出校验；新增单一 Excel writer，主结果页直接展示同一渲染器的图像与导出入口。不增加新页面。
**Tech Stack:** React/TypeScript、Python/Matplotlib、openpyxl（新增锁定依赖）。
**Spec:** 用户要求结果 Excel、可视化和导出模块；沿用已批准的简洁三步 UI 与科学约束。下列工作簿布局为实现选择。

## Global Constraints
- 保持“内参 → 目标 → 结果”，不增第四个模块页。
- results.xlsx 必须为真实 OOXML 工作簿，数字为数字，未检出为空且保留状态，文本不能成为 Excel 公式。
- 工作簿包含说明、泳道结果、原始测量、参考归一化、生物学汇总、统计、样本、图像来源和导出图；未确认实验设计不生成生物学 n。
- PNG/SVG、Excel 内图及屏幕预览来自同一渲染器；原始像素积分不变。
- 原图哈希、过期结果拒绝、已有目录不覆盖、临时目录原子提交与审计 SHA256 继续有效。

## Review Focus
- 首泳道或中间泳道缺失时，表格/Excel/图保留位置，不画成 0；全缺失仍可导出。
- 中文和以 =/+/-/@ 开头的样本/蛋白名称保留为文本，数值单元格不变。
- 没有生物学汇总和没有统计时，Excel 仍有表头/说明，不暗示有效 n。
- 图像/样本改变后不得展示晚到预览或导出旧版本。
- 打包后 openpyxl/Pillow 可用，Excel 图像/数值/导出审计独立验证。

### Task 1: 一体化结果与导出
**Files:** Create backend/titan_wb/workbook.py, tests/test_workbook.py, src/ResultVisualization.tsx; Modify backend/titan_wb/export.py, src/LaneResults.tsx, src/App.tsx, src/ExportPreview.tsx, src/style.css, requirements.lock, tests/browser/lane-workflow.spec.ts, scripts/verify_release.py, scripts/verify_lane_release.py.
**Interfaces:** write_workbook(project,result,root) writes results.xlsx after plot.png exists. ResultVisualization accepts project/result/onExport; uses existing export_preview RPC with revision guard.
- [ ] Write and run RED: xlsx contents, numeric values, missing cells/state, literal formula-like text, embedded chart and all-missing plot; browser shows graph and new direct export button.
- [ ] Implement Excel writer and missing-slot plot handling; add compact result graph/export action and modal content list, keep dimensions advanced in existing dialog.
- [ ] GREEN: pytest, Vitest, build, browser; packaged workbook readback and existing preview/export byte consistency.
- [ ] Fresh scoped review, fix Important findings in one pass, verify changed behavior.
- [ ] Build version 0.2.1, verify signed independent bundle and ZIP, install with recoverable 0.2.0 backup if not running; update guide/report. Native GUI/Fiji/Windows evidence limits remain explicit.
