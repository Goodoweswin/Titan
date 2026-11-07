# 独立项目工作区 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 项目独立保存资料和分析归属，可整包搬迁；全局工具入口可直接开始独立分析。

**Architecture:** 保留 v1 本地索引和原有分析文件夹，项目资料使用独立的受管副本。新增可携带项目包和中立界面，模块仍负责各自的工作台、导入与保存。

**Tech Stack:** Python, React, TypeScript, Tauri, pytest, Playwright.

**Spec:** [独立项目工作区](../specs/2026-11-07-independent-project-workspace-design.md)

### 1. 项目资料
- [x] 在 `tests/test_project_materials.py` 先验证原件删除后副本仍可用、项目隔离、旧索引和批次失败。
- [x] 在 `backend/titan_wb/project_materials.py` 实现 `library_material_add(collection_id,paths)`、`library_material_paths(collection_id,material_ids)`、`library_material_remove(collection_id,material_id)`；`library_workspace` 的项目可含 `materials`。
- [x] 运行资料和索引回归。

### 2. 项目包
- [x] 在 `tests/test_project_bundle.py` 先验证跨库搬迁、图表与导出、拒绝不完整的包并保持原数据。
- [x] 在 `backend/titan_wb/project_bundle.py` 实现 `library_export_bundle(collection_id,destination)` 和 `library_import_bundle(path)`。复制已保存的三个分析格式、资料和已登记的可用导出，检查路径并重新绑定包内来源。
- [x] 运行搬迁和跨模块来源回归。

### 3. 工具导入
- [x] 验证有效数据才创建记录，取消和无效输入不登记。
- [x] WB 继续显式选 TIFF 页；IF 继续选择序列、通道和样本；统计继续使用表格解析器。新分析保存到明确选择的项目，或独立保存。
- [x] 运行导入回归。

### 4. 界面与回归
- [x] 先增加浏览器流程：手动新建项目、资料副本、跨工具切换、创建或移动分析、整包搬迁。
- [x] 在 `App.tsx` 管理项目/工具/分析导航；在 `ProjectLibrary.tsx` 和新中立页面统一入口、项目内容和归属提示，保持工作台离开保护。
- [x] 样式沿用 Titan 的字型、浅色背景与现有操作色，项目页用简洁列表展示资料、分析和图表。
- [x] 运行 Python、前端构建、单元和浏览器检查，更新用户指南，复查变更。


执行记录：资料与分析分别保存。项目包携带资料、已保存的分析、图形和可验证的登记产物；包外统计来源冻结为快照。旧 WB／统计恢复备份留在原库。全局工具页未确认的首次导入不创建分析。

验证：Python 346 项及 5 项子测试，前端 82 项，桌面传输 8 项，生产前端构建均通过。完整浏览器回归首轮 65/66；修复首页重复引擎状态后，复跑受影响的 33 项全部通过。未执行安装、发布或真实实验数据验收。
