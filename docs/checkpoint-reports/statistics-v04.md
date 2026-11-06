# v0.4 统计与绘图预览检查点

> 此文件保留 beta3 整合时的验收记录。当前主应用及项目结果对接记录见 [项目结果对接](project-results-statistics.md)。

日期：2026-11-07。基础标签 `v0.4.0-beta.3`，基础提交 `80d552c52be86bfd661166fb9268eeac375fc673`。开发分支 `codex/statistics-v04`。本次将 beta3 合入已有统计预览，保留两侧提交历史。

## beta3 整合

- 合入 IF 后台任务 JSON 的显式 UTF-8 读取及 Windows 默认编码回归测试。
- 合入 IF 项目切换保护：旧项目保存完成前暂停导入；保存失败保留当前项目。
- 保留三个并列模块、WB 向统计项目传递数据、原统计项目与冻结快照。
- 新增三个组件回归：保存期间禁止导入、保存失败取消项目切换、进入统计模块等待 IF 保存。
- 预览窗口标题与统计页脚标明 beta3 基础；内部应用版本仍为 `0.4.0`，未新增正式发布标签。

## 已完成

- 通用统计数值核心与旧 WB 适配层；旧统计结果保持兼容。
- 独立统计项目、宽/长表与 XLSX 工作表导入、表格编辑、分析、图形与快照。
- 两组/多组统一标注，真实图幅、组对选择、样式编辑、PNG/SVG/PDF/Excel 导出。
- WB 来源只读、显式更新、返回 WB，项目库多模块导航。
- macOS arm64 独立预览包，标识 `com.titan.stats.preview`，不改现有 Titan 的安装与数据目录。

## 实际验证

| 项目 | 结果 |
| --- | --- |
| TypeScript / Vite 生产构建 | 通过 |
| Vitest | 80 项通过（含真实 Python 引擎的统计流程、IF 切换与保存组件测试） |
| pytest | 273 项及 5 个 subtests 通过 |
| Rust | 7 项通过（离线构建） |
| 打包引擎独立运行 | 统计创建、ANOVA、保存、重开、长表、各格式导出通过；IF 后台分割、9 个核测量、移动后重开、图形与表格导出通过 |
| macOS app 构建和签名验证 | 构建通过；本地临时签名 `codesign --verify --deep --strict` 通过 |
| macOS 原生操作 | beta3 标题启动，WB/IF/统计入口，IF 合成视野测量与自动保存，IF→统计切换，旧统计项目重开、F=7/P=.027、60×50 mm 冻结图形恢复 |
| 小图视觉检查 | 旧三组图快照在整合版恢复；原预览已检查字号间距、组对选择与过密阻断 |
| Playwright | 本轮未运行；此前因本环境监听 `127.0.0.1:1420` 被拒绝而受阻。保留 beta3 和统计模块浏览器回归，使用组件测试与原生实测补充验证 |
| Windows 原生 / Prism 实机 | 未验收 |

本地临时签名不等于 Apple 公证。没有发布正式版本，也没有替换当前已安装应用。已完成的是首个可运行预览；剩余功能见 [指南](../STATS_USER_GUIDE.md)。

可复现命令：

```sh
npm test
.venv/bin/python -m pytest -q
npm run build
PYINSTALLER_CONFIG_DIR="$PWD/artifacts/pyinstaller-cache" MPLCONFIGDIR="$PWD/artifacts/mpl-cache" .venv/bin/python packaging/build_engine.py
CARGO_NET_OFFLINE=true cargo test --manifest-path src-tauri/Cargo.toml
CARGO_NET_OFFLINE=true npm run desktop:build -- --config src-tauri/tauri.stats-preview.conf.json
.venv/bin/python scripts/verify_stats_engine.py 'src-tauri/target/release/bundle/macos/Titan Stats Preview.app/Contents/Resources/engine/wb-engine/wb-engine'
.venv/bin/python scripts/verify_if_engine.py --engine 'src-tauri/target/release/bundle/macos/Titan Stats Preview.app/Contents/Resources/engine/wb-engine/wb-engine' --output artifacts/beta3-if-verification
npm run test:e2e -- tests/browser/stats-workspace.spec.ts
```

构建产物：`artifacts/Titan_0.4_beta3_Stats_Preview_macos-arm64.zip`。统计引擎检查记录见 `stats-bundled-verification.json`，本轮汇总见 `statistics-beta3-integration.json`。

固定数值基准为合成数据，不代表真实实验。冻结图形与当前数据分开保存；统计校正家族不会因仅显示部分组对而改变。
