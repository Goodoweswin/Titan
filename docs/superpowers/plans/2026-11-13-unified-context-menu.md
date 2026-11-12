# Titan 统一右键菜单实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 项目、分析、图表使用一致的管理菜单；统计单元格通过菜单明确选择排除或恢复。

**Architecture:** 用一个共用菜单组件承载右键与「⋯」入口，两种入口共用相同操作定义。沿用现有项目管理、打开图形、来源追溯和统计编辑逻辑；菜单打开与关闭只改变交互状态。

**Tech Stack:** 现有 React、TypeScript、CSS、React Portal、Vitest、Playwright，无新增依赖。

**Spec:** 本文件的「交互约定」，对应用户 2026-11-13 的请求。用户已授权实施、本机更新与 GitHub 同步。

## Global Constraints

- 保持简单：菜单只有一层，复用现有管理能力，保留左键打开及「⋯」入口。
- 首版覆盖共用左栏中的项目、分析、图表与导出记录，以及统计数据表的数值单元格。
- 显示菜单本身不打开分析、不切换项目、不修改数值或统计排除状态。
- 排除只切换参与统计的标记，原始数值保留；复用现有撤销、保存和结果过期机制。
- 复用现有移出项目确认及文件保留语义。
- 保留当前紧凑字号、可调栏宽、明暗外观、浏览导航、账户及 WB／IF／统计模块。
- 执行前重新核对最新整合源码和本机安装版本。勘察时安装版对应源码在 `titan-account-login/Titan`；本计划保存于原侧栏工作树，实施基线须包含最新整合功能。

## 交互约定

| 对象 | 菜单项 |
| --- | --- |
| 项目 | 打开项目、新建分析、重命名、置顶／取消置顶、移出项目列表 |
| 分析 | 打开分析、移到项目、移出项目（已归属项目时）、在文件管理器中显示 |
| 图表与导出记录 | 打开图表／导出、打开源分析、在文件管理器中显示（有可定位文件时） |
| 未排除的统计数值 | 排除此值 |
| 已排除的统计数值 | 恢复此值 |

- 右键作用于鼠标所在行，当前打开分析和浏览历史保持原样，直到用户选择操作。
- 「⋯」和右键显示相同内容；旧 WB 图表记录也补齐统一的「⋯」入口。
- 图表的打开沿用现有 `onArtifact`，保留原版本及冻结数据；文件缺失等状态沿用现有可用性判断。
- 统计菜单只覆盖数值单元格。锁定来源和历史快照显示禁用操作与简短只读说明；处理过程中关闭菜单并禁止执行操作。
- 点击菜单外、按 Esc、切换页面或对象、滚动或调整窗口时关闭；重复右键直接替换为新对象的菜单。
- 支持方向键、Enter、Esc、Shift+F10／菜单键。关闭后恢复触发位置的焦点。
- 使用全局明暗主题和 13px 字号；菜单浮在内容上方，在窗口边缘自动调整位置，避开左栏与表格的滚动裁切。

## Review Focus

1. 右键非当前分析或图表时，操作目标必须准确，打开菜单不触发原来的左键行为。
2. 菜单打开后，分析、数据表、冻结图或行列发生变化时，旧操作不能修改新对象。
3. 长左栏、窗口四角、窄窗口中，菜单仍完整可见并可以通过键盘退出。
4. 锁定来源、历史快照、处理状态和缺失文件，保持原有可用性与数据保护规则。
5. 取消菜单、取消移动或移出确认，数据、项目归属及浏览历史均保持原样。

## 文件与职责

- 新建 `src/ActionMenu.tsx`、`src/action-menu.css`：共用单层菜单、定位、关闭、键盘和焦点行为。
- 修改 `src/main.tsx`：接入菜单提供器与样式。
- 修改 `src/ProjectLibrary.tsx`：项目、分析、图表及导出记录的操作定义和两种入口。
- 修改 `src/stats/StatsWorkspace.tsx`：数值菜单及按稳定行列 ID 执行排除／恢复。
- 修改 `src/chrome.css`、`src/sidebar.css`：将旧弹层样式收敛到共用菜单，保留左栏布局。
- 新建 `tests/components/action-menu.test.ts`、`tests/browser/context-menu.spec.ts`，按需更新现有相关断言。
- 更新 `docs/USER_GUIDE.md`、`docs/releases/INDEX.md` 及本机验收报告。

## Task 1: 共用菜单

**Interfaces**

- 导出 `ActionMenuProvider`、`useActionMenu`、`ActionMenuItem`。
- `ActionMenuItem` 包含 `id: string`、`label: string`、`disabled?: boolean`、`onSelect: () => void`。
- `useActionMenu()` 提供 `openMenu({items, origin, position, label, id?})`、`closeMenu()` 与 `activeId`；`origin` 为触发控件，`position` 为窗口坐标，`label` 为菜单的可访问名称。
- 全应用同时显示一个菜单；消费者在上下文切换、目标失效或进入处理状态时关闭菜单，执行回调时再次检查有效性。

- [x] **Step 1 — 编写失败测试。** 在 `action-menu.test.ts` 挂载真实组件：打开菜单、Esc／外部点击只关闭且不执行回调；方向键跳过禁用项；Enter 只执行一次；焦点恢复；再次打开替换旧菜单。断言真实菜单及目标状态。
- [x] **Step 2 — 运行测试并确认失败。** `npm test -- tests/components/action-menu.test.ts`，失败原因应为待实现的共用组件。
- [x] **Step 3 — 实现共用组件并在入口接入。** Portal 到页面根部，使用 `menu/menuitem` 语义，定位按窗口可用空间限制；处理 Esc、外部点击、滚动、窗口变化和失焦。
- [x] **Step 4 — 验证并提交。** 同一测试通过，`npm run build` 通过；只提交本任务相关文件。

## Task 2: 左栏三个对象共用管理菜单

**Interfaces**

- 使用 Task 1 的组件和类型。
- 复用 `ProjectLibrary` 当前的 `onProject`、`onOpen`、`onArtifact`、`onDialog`、`onPin`、`onReveal` 回调及现有可用性条件。
- 各对象只维护一份操作列表，同时供右键、键盘入口和「⋯」使用。

- [x] **Step 1 — 编写失败流程。** 在 `context-menu.spec.ts` 创建合成项目、分析和图表记录，检查右键与「⋯」的菜单项一致；非当前行只弹菜单；右键另一行替换目标；旧 WB 图表、统计快照及导出记录均可管理。
- [x] **Step 2 — 运行并确认失败。** `npx playwright test tests/browser/context-menu.spec.ts --grep sidebar`。
- [x] **Step 3 — 接入左栏。** 事件限定在对象行；共用操作列表复用既有对话框与打开流程。缺失文件禁用对应操作；打开菜单后列表目标失效时关闭菜单。
- [x] **Step 4 — 覆盖边界。** 四角和滚动裁切、明暗切换、13px 字号、键盘打开／关闭；取消移动和移出确认后归属不变；选择打开后复用现有离开确认和浏览历史。
- [x] **Step 5 — 验证并提交。** 运行 `context-menu.spec.ts` 的左栏用例及 `independent-project.spec.ts`、`library-figures.spec.ts`、`workspace-chrome.spec.ts`、`workspace-navigation.spec.ts` 的相关回归。

## Task 3: 统计单元格明确选择排除／恢复

**Interfaces**

- 使用 Task 1 的菜单；目标记录项目、数据表、行和组的稳定 ID。
- 通过现有 `editD` 编辑 `row.excluded[groupId]`，保持原始 `row.values[groupId]`。

- [x] **Step 1 — 编写失败流程。** 右键已填写数值后，断言排除标记、原值及统计结果仍不变；取消后同样不变。点击“排除此值”才设置标记，右键后出现“恢复此值”，点击才清除标记。
- [x] **Step 2 — 补充边界测试并确认失败。** 锁定来源、历史快照禁止修改；菜单打开后切换表格、移除行列或进入处理状态，旧菜单不可执行。排除／恢复可撤销，原值保留，重新运行前原结果显示过期。
- [x] **Step 3 — 修改事件与说明。** 把当前右键直接切换改为弹出菜单；点击操作时重新查找稳定 ID 和当前只读状态。更新提示文字为“右键选择排除或恢复，原值保留”。
- [x] **Step 4 — 验证并提交。** 运行 `npx playwright test tests/browser/context-menu.spec.ts tests/browser/stats-workspace.spec.ts` 及 `npm test`。

## Task 4: 整体验证与交付

- [x] **Step 1 — 运行生产构建与相关浏览器回归。** `npm run build`；运行右键、项目、图表、统计、外观及浏览导航用例。核对菜单的取消、锁定、缺失和目标变化分支。
- [ ] **Step 2 — 原生核对。** 使用合成数据在本机检查右键事件、窗口边缘和键盘（不将自动化右键等同于物理触控板手势验收）；核对 WB、IF、统计及账户入口继续可用。
- [x] **Step 3 — 同步帮助与记录。** 用户指南说明菜单入口和统计排除行为；登记准确源码、验证范围和实际构建结果。
- [ ] **Step 4 — 按后续执行请求交付。** 本机更新时备份原应用与项目库，核对运行窗口；GitHub 同步时核对真实检查结果。交付记录包含实际安装位置、备份、源码和 GitHub 检查结果。

## 自审

- 菜单范围、简洁要求、已有确认、统计原值和只读规则均有对应任务。
- 五项 Review Focus 分别由 Task 2／3 的目标、取消、布局、状态和撤销用例覆盖。
- 本方案是一个共用交互组件及两处接入，沿用当前业务操作。

## 交付进度与待核对项

- 最终功能源码：`7d748b9`；共用菜单、左栏接入、统计单元格及异步刷新保护已实现。
- 本机 140 项前端、14 项相关浏览器检查及生产构建通过；最终源码 GitHub 完整 106 项浏览器和 346 项 Python 检查通过。
- 合成原生验收覆盖项目、分析、图表菜单、键盘、取消、排除／恢复、撤销及历史快照只读。最终修复包已在 04:37 安装，签名／哈希／账户服务地址和未变的项目库索引已核对，原应用及项目库有备份。
- Mac 再次锁屏后，最终安装版的启动、旧项目桌面访问和账户会话恢复尚待解锁后核对；这些原生核对不记为完成。

- 最终源码 GitHub CI 与账户整合工作流全部通过，包含 Windows 安装包构建；GitHub 源码同步按本次用户授权交付。原生待核对项保持未勾选。
