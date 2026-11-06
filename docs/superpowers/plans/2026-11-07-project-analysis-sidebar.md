# Titan 项目与分析侧栏实施计划

> **For agentic workers:** Use the executing-plans skill for inline implementation. Work through the checkboxes in order. Keep the current WB/IF working changes intact when choosing the implementation base.

**目标** 让用户手动创建课题项目，将独立分析像 thread 一样归类、切换和续做，从左栏直接打开正式图与导出文件。

**架构** 保留 WB、IF 分析目录作为各自数据真源。在共享项目库的 `index.json` 中增加课题集合和分析归属，统一使用现有锁及原子写入。项目下的产物按来源分析汇集，读取已有图形版本，另登记成功导出的外部文件。

**技术栈** React/TypeScript、Tauri、Python，沿用 pytest、Vitest 和 Playwright。

**设计** `docs/superpowers/specs/2026-11-07-project-analysis-sidebar-design.md`。规划基线是本机可核对的 0.4.0 发布源码 `1940dc6`，该工作树另有未提交的 WB/IF 指引改动。执行使用独立工作树，基于该发布源码和本设计提交。独立统计模块由已提交的本地预览源码 `a4c0711` 提供，原工作树的未提交改动未纳入。

## 共用约束

- 项目只需名称。每条分析只能归入一个项目，或显示为「未归类」。项目与分析名称允许重复，以 ID 区分。
- 分析目录和已有项目格式原地保留。课题归类是本机视图，另存整个分析仍沿用该模块的现有可携带格式。
- 复用原有 WB/IF 新建、打开、自动保存、关闭和文件锁。只要无法安全离开当前分析，就留在原视图。
- 图、表及导出来源对应实际产出的分析版本。浏览历史和外部文件不触发重新计算或覆盖文件。
- 归属和置顶在索引级写入，项目成员及工作台的科学设置分别持久化。

## 验证重点

1. 旧索引升级、同 ID 另存和路径重新定位时，每条分析维持独立身份。
2. 索引并发写入、创建失败后重试和取消对话框时，没有半登记的课题或分析。
3. WB/IF 保存失败、迟到的打开响应和切换模块时，续做位置不会登记到错误分析。
4. 两种 WB 图形目录部分损坏、IF 导出后重测、外部文件移走时，其他项目仍可读，旧产物仍有明确来源。
5. 搜索、展开、置顶及自动保存同时发生时，列表位置稳定。

## 1. 扩展本地索引与命令

**文件** `backend/titan_wb/library.py`、`backend/titan_wb/engine.py`、`backend/titan_if/service.py`、`src/types.ts`、`tests/test_library.py`、`tests/test_if_projects.py`。

**契约** `library_list` 保留现有数组返回，新增 `library_workspace()` 返回 `{projects, entries}`。课题记录使用 `{id, name, pinned, created_at}`，分析登记新增可选 `collection_id` 与 `resume`。`resume` 使用 `{view, artifact_id?}`，`view` 为 `workspace | results | figure`。`artifact_id` 只指应用内有版本的正式图，省略时打开模块现有的组图工作区。外部文件不写入续做位置。`library_create_collection(name)`、`library_update_collection(id, patch)`、`library_remove_collection(id)`、`library_assign(entry_id, collection_id)` 和 `library_set_resume(entry_id, resume)` 分别操作课题、归属和续做位置。空归属写 `null`。

- [x] 在测试中以旧版 `index.json` 同时登记一个 WB 和一个 IF，断言 `library_workspace` 返回两个「未归类」条目，读取后索引字节保持一致。登记后模拟同科学 ID 的另存、跨项目移动、重定位并断言两个 `entry_id` 各自独立。
- [ ] 在测试中并行执行登记和移动，断言索引保留两项更新。模拟一个已失效的目标课题 ID，断言操作报错且旧归属保留。分别模拟保存失败和索引提交前失败，断言没有半创建的课题或登记。取消故障后重试，断言只出现一条分析。
- [x] 实现旧索引字段缺省读取及新命令，所有修改使用现有 `.index.lock` 与原子写入。移出课题在一次写入中解除成员归属。把排序时间拆成显式打开和后台登记，自动保存传入 `touch_opened=False`。保留旧调用的默认行为。
- [x] WB `library_create` 和 IF `if_new` 接受 `collection_id`，同一对话框新建归属时允许以 `new_collection_name` 代替。已有课题与新课题参数互斥。成功登记时一次写入课题与分析关系。提交失败时回收本次新建且未登记的目录，保留已登记文件。另存登记可带 `source_entry_id`，在锁内继承其课题归属。已有路径保持原归属。
- [x] 运行 `.venv/bin/pytest -q tests/test_library.py tests/test_if_projects.py tests/test_projects.py`，检查项目库、同 ID 副本和两种格式的回归，再单独提交索引与接口改动。

## 2. 左栏、新建入口与续做

**文件** `src/ProjectLibrary.tsx`、`src/useProjectLibrary.ts`、`src/App.tsx`、`src/if/IFWorkspace.tsx`、`src/style.css`、`src/chrome.css`，新增 `src/LibraryCreateDialog.tsx`，扩展 `tests/browser/library-figures.spec.ts` 与 `tests/browser/if-workflow.spec.ts`。

**契约** `useProjectLibrary` 消费 `library_workspace()`，提供当前快照、刷新及索引操作。新建对话框提交 `{kind, name, collection_id?, new_collection_name?}`，`kind` 为 `collection | wb | if | stats`。分析打开传入 `entry_id`，沿用模块专属加载入口，成功后才登记续做位置。

- [ ] 增加端到端场景。新建「皮肤衰老」，同项目建 WB 与 IF 分析，取消另一条创建，断言列表无新增。将 IF 移到「水凝胶」，重新载入，断言 WB 与 IF 各有原分析且无副本。置顶「水凝胶」，搜索一条 WB 图名后清空，断言手动展开状态恢复，后台自动保存时置顶顺序及最近打开时间保持。
- [x] 增加保存失败与迟到响应场景。保存失败后尝试跨模块打开另一分析，断言原分析、输入与续做记录保留。拦截较早的打开响应，后选分析仍高亮。
- [x] 把三个模块的 `＋`、打开已有分析和主页新建按钮接入同一流程。保留各模块工作台按钮，左栏统一使用 `entry_id` 选择、移动和恢复。项目内创建时预选当前项目，其他入口选「未归类」。
- [x] 实现折叠、当前项高亮、置顶、改名、移到项目和移出项目。临时搜索展开与手动展开分别记录，清空搜索回原列表。恢复上次成功打开的工作台、结果或组图，找不到时回工作台。新建和首次打开都更新索引，后台自动保存保留原排序。
- [x] 运行 `npm test`、`npm run build` 和 `npm run test:e2e -- tests/browser/library-figures.spec.ts tests/browser/if-workflow.spec.ts`，确认两模块可续做并提交。

## 3. 正式图和导出入口

**文件** `backend/titan_wb/library.py`、`backend/titan_wb/engine.py`、`backend/titan_wb/figure_documents.py`、`backend/titan_wb/wb_figures.py`、`backend/titan_if/service.py`、`src/ProjectLibrary.tsx`、`src/App.tsx`、`src/if/IFWorkspace.tsx`、`src/WbFigureEditor.tsx`、`src-tauri/src/lib.rs`、`tests/test_library.py`、`tests/browser/library-figures.spec.ts`。

**契约** 每个产物行至少包含 `{id, entry_id, title, kind, source_revision, document_id?, version_id?, files?, available}`。`kind` 为 `wb_plot | wb_figure | stats_plot | if_figure_export | result_export`，WB 条带组图的源版本可用现有 `version_id` 和源图清单代替分析修订号，此时 `source_revision` 为 `null`。图使用已有冻结版本。导出记录使用实际成功响应中的文件清单和调用时的源标识。`library_record_export(entry_id, record)` 以同一分析、产物种类和规范化输出路径去重，失败时可重试登记。

- [ ] 增加测试。保存 WB 柱图与条带组图并导出 IF 图和 Excel，断言项目下可查到名称、来源和版本，移动分析后相关产物随之移动。模拟找不到导出文件及单个图形目录损坏，断言其余列表可用。模拟导出后立即修改分析，断言旧产物仍指向原版本。
- [x] 复用 WB 的 `figures/catalog.json` 和 `figures/wb/catalog.json`，各目录独立读取与报错。整合现有 WB 柱图的 `export_origin`，一笔导出显示一行，可打开图版本或输出位置。升级仅恢复已有可验证来源记录的产物。后续成功导出的 IF 图和结果从正式导出入口登记。
- [x] WB 与 IF 导出成功后登记一个包含各格式文件的产物记录。使用真实输出清单，区别文件与目录。登记失败时保留导出成功提示和路径，提供只重试登记的入口。未保存预览不登记。
- [x] 左栏项目下渲染「分析」「图表与导出」。按原分析的 `entry_id` 解析归属，旧图打开其版本，IF 导出文件使用原文件。「打开源分析」单独跳转。文件离线或移动时仍显示其名称和来源。通过限定于已登记分析或导出记录的 Tauri 命令调用系统文件管理器，支持 macOS 和 Windows。
- [x] 完成完整 Python、前端、Rust 和浏览器回归并提交产物导航与用户指南。
- [ ] 用旧索引副本完成 macOS 和 Windows 的重新定位、文件管理器跳转及可携带项目原生验收。

## 4. 接入独立统计与绘图

**依赖已满足：** 独立统计预览的持久化与导出契约在 `a4c0711`，使用 `.titanstats`。在此基础上接入共用项目库，保留 WB 来源身份与统计历史运行版本。

- [x] 为统计文档接入 `library_workspace` 的分析与产物契约，使用自己的 `entry_id`、归属和重开适配。统计文档持久化稳定后在 `＋` 中增加「新建统计分析」。
- [x] 用一个项目内同时有 WB、IF 与统计分析的夹具，验证重新打开、移动归属、结果与图表来源仍可追溯。交付时明确统计接入是否已满足发布条件。

执行记录：WB、IF 与统计均已接入。统计索引故障不阻断自动保存；另存和登记一并提交，失败可重试。来源定位、历史运行导出和单条记录损坏的隔离有回归覆盖。Windows 原生验收仍待执行。

验证：Python 289 项及 5 项子测试、Vitest 80 项、Rust 7 项、Playwright 63 项通过。macOS Apple Silicon 验收包已构建并通过签名完整性检查。独立原生窗口用合成数据验证了课题菜单预选、跨模块打开、图形快照的搜索与恢复、关闭取消时保留写入锁；未完成 Windows 原生验收和 macOS 文件管理器定位的可视确认。
