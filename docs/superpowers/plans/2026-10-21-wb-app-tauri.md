# Titan WB Tauri Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. 顺序执行，每CP测试并保留报告，不重复请求常规开发许可。

**Goal:** macOS离线双击启动的WB分析桌面App。
**Architecture:** React工作台→受限Tauri Rust命令→PyInstaller本地Python引擎，JSON stdin/stdout；预览与原始计算分离。
**Tech Stack:** Tauri 2、React、TypeScript、Vite、Python3.11、NumPy/Pillow/tifffile/SciPy/Matplotlib、pytest/Vitest/Playwright。
**Spec:** `docs/superpowers/specs/2026-10-21-wb-app-design.md`。

## Global Constraints

原图不改；矩形为原图0起点、右下不含；显式背景/参考/生物学单位；审核失效按revision传递；禁止零分母与饱和进入归一化；不把技术泳道计为n；默认单文件50MiB/25MP；无云与常驻Web服务；CP9工程与CP10真实数据分别验收。

## Review Focus

- 原图位深、光度编码、极性和预览不混淆（CP2/5）。
- 缩放/撤销/异步晚到不覆盖新状态（CP3/4）。
- IBC与技术重复层级不重复计数（CP6）。
- 统计设计、退化输入与共享分母（CP7）。
- 中文路径、项目锁、原子保存、独立安装包进程恢复（CP2/8/9）。

## 文件与协议

- `backend/titan_wb/{engine,models,images,projects,detection,quantify,normalization,statistics,export}.py`：科学计算与项目文件。
- `src/{App,Workspace,Results}.tsx`，`src/{types,state,bridge}.ts`：界面与可测试状态。
- `src-tauri/src/{lib,main}.rs`：受限命令、超时、sidecar生命周期与原生文件对话框插件。
- `packaging/build_engine.py`：冻结引擎；`scripts/check_cp.py`：测试门槛和记录。
- Python请求 `{command, payload}`，Rust追加可信session标识；响应 `{ok, data, error}`，错误不伪装成功。
- 项目结构使用 `.titanwb`文件夹，manifest为schema_version=1，revision递增；图像/ROI/样本引用用稳定ID。
- 前端 `callEngine<T>(command:string,payload:object):Promise<T>`；测试通过独立本机测试适配器连接同一引擎，发行包不含测试HTTP服务。

### Task 1: CP1 桌面外壳与真实引擎

Files: `package.json`, `src-tauri/`, `backend/titan_wb/engine.py`, `src/bridge.ts`, `src/App.tsx`, `packaging/build_engine.py`。
Interfaces: `dispatch(request:dict)->dict`；`health`返回引擎版本；`probe`在真实NumPy像素上计算4×30−4×10=80；Rust `engine(request:Value)->Result<Value,String>`。
- [ ] 写健康/真实数值/未知命令失败用例，观察RED。
- [ ] 最小实现JSON引擎、React窗口、Rust受限启动及60秒超时；发行模式只用内置binary。
- [ ] pytest、Vitest、cargo test及参考21项GREEN。
- [ ] 打包engine和最小.app并真实启动；通过后报告与本地提交。

### Task 2: CP2 原图与项目

Files: `models.py`, `images.py`, `projects.py`, `src/types.ts`。
Interfaces: `new_project(name)`, `import_image(project,path)`, `save_project(project,path,expected_revision)`, `open_project(path,read_only=False)`；每条命令返回完整校验后的项目。
- [ ] 先测16位12345保真、RGB/多页拒绝、中文路径、坏图/超限/hash错误、manifest中断与第二写入者；观察RED。
- [ ] 实现保真图像、独立PNG预览、复制原图、原子保存/备份、session项目锁。
- [ ] 全量回归、原生导入/保存/重开；报告并提交。

### Task 3: CP3 工作台ROI与样本

Files: `src/Workspace.tsx`, `src/state.ts`, `models.py`。
Interfaces: `editProject(project,event)`递增revision并使审核/结果失效；`screenToImage(rect,view)`保持原坐标；`validate_project`统一校验ID/引用/区域。
- [ ] 先测缩放不改坐标、越界/背景重叠、样本错配、撤销/重做与审核失效。
- [ ] 实现图像平移缩放、目标/背景画框及调整、样本与参考表、撤销/审核。
- [ ] 单元+浏览器真实交互+Tauri窗口实测；报告并提交。

### Task 4: CP4 自动候选与纠错

Files: `detection.py`, `Workspace.tsx`, `state.ts`。
Interface: `detect(project,image_id,window,settings)->list[ROI]`，reviewed初始false，缺带不补值。
- [ ] RED：空白0框、梯度两带、合成12候选、旧revision丢弃。
- [ ] 实现局部背景投影候选及移动/删除/补框；不自动认定蛋白或样本身份。
- [ ] 回归与交互纠错；报告并提交。

### Task 5: CP5 定量与QC

Files: `quantify.py`, `engine.py`, `src/Results.tsx`。
Interface: `measure_project(project)->measurements`；原数值、面积、背景、净值、clipping及可用状态均返回。
- [ ] RED：手算80、暗图80、负数−20、4095端点比例0.25、背景并集、未知上界、未审核门槛。
- [ ] 实现测量与QC，前端可回到每个ROI；原始像素只在Python计算。
- [ ] 全回归与界面QC检查；报告并提交。

### Task 6: CP6 归一化、重复与IBC

Files: `normalization.py`, `models.py`, `Results.tsx`。
Interface: `normalize(project,measurements)->(rows,biological)`。
- [ ] RED：200/100=2、零分母/错引用拒绝；同bio的1和3先均值2、另一bio4得到控制均值3；跨膜A技术1/3、B6、IBC=1最终4而非10/3。
- [ ] 同膜技术均值→IBC→同sample膜间等权；无有效桥接/混杂不合并；IBC不计n；p/total独立终点。
- [ ] 回归与两图参考匹配实测；报告并提交。

### Task 7: CP7 统计与图表

Files: `statistics.py`, `Results.tsx`, `export.py`图形函数。
Interface: `compare(biological,spec)->StatsResult`；descriptive/welch/paired，raw/log2，family+Holm。
- [ ] RED：配对log差[1,2,3]的t=3.464101615/df2；p[.01,.03,.04]→[.03,.06,.06]；重复bio、缺配对、少于2、退化方差、不支持多膜推断拒绝。
- [ ] 实现双侧检验与区间、标明效应方向；检验使用生物学原比例，不用对照恒1；散点/配对图显示n、SD或CI。
- [ ] 全回归与图表导出核对；报告并提交。

### Task 8: CP8 批处理、导出、恢复

Files: `projects.py`, `export.py`, `state.ts`, `App.tsx`。
Interfaces: `export_project(project,result,destination)->manifest`；批测逐图状态；关闭/重开不使用过期结果。
- [ ] RED：坏图不静默漏项、取消/过期结果、导出不覆盖、CSV/JSON/PNG/SVG/hash一致、只读/损坏恢复、未保存关闭。
- [ ] 实现完整包导出、固定revision、最近项目与恢复、退出时子进程收尾。
- [ ] 完整工作流浏览器E2E及Tauri实测；报告并提交。

### Task 9: CP9 安装工程验收

Files: `src-tauri/tauri.conf.json`, `packaging/`, `scripts/verify_release.py`, `docs/USER_GUIDE.md`。
- [ ] RED：完整流程预期24测量/12目标/1阻止/6bio/处理fold约1.994。
- [ ] 构建内含Python运行时的arm64 .app/.dmg，记录版本/hash/许可证。
- [ ] 全量测试+独立路径Finder双击+无开发Python环境+离线+保存重开导出测试；不能用浏览器测试冒充macOS原生验收。
- [ ] 交付可运行包，明确未签名公证的内部版本；报告并提交。

### Task 10: CP10 真实数据

- [ ] 用户提供原始数据/实验映射/人工参照后，预先确定可接受误差和交互标准。
- [ ] 真实数据与人工对照并记录失败/修正，不补造数据。缺材料保持待验收，不阻止独立通过CP9。

## 测试报告和执行记录

每CP的RED/GREEN日志放 `artifacts/checkpoints/CPn/`，摘要放 `docs/checkpoint-reports/CPn.md`；唯一状态在 `docs/checkpoints.md`。失败不推进。当前工作区是本任务新建项目，无既有Git分支或其他代码，原地初始化独立feature分支，不创建多余worktree。结构性改动和偏离计划写入执行ledger。整体完成后使用独立审阅代理检查全分支。
