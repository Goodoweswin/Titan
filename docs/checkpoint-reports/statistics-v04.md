# v0.4 统计与绘图预览检查点

日期：2026-11-07。基础标签 `v0.4.0-beta.2`，基础提交 `3d8872c19d9f86c7eef68ec63dbf9e5e6b716c40`。开发分支 `codex/statistics-v04`。

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
| Vitest | 77 项通过（含真实 Python 引擎的组件流程测试） |
| pytest | 273 项及 5 个 subtests 通过 |
| 打包引擎独立运行 | 创建、ANOVA、保存、重开、长表、各格式导出通过 |
| macOS app 构建和签名验证 | 构建通过；本地临时签名 `codesign --verify --deep --strict` 通过 |
| macOS 原生操作 | 已启动，验证合成表、统计设置、F=7/P=.027、图形、60×50 mm、P 标注、快照及重启入口 |
| 小图视觉检查 | 实际渲染并检查三组图；增加基于字号的标注间距、组对选择与过密阻断 |
| Playwright | 本环境监听 `127.0.0.1:1420` 被拒绝，未执行通过；保留新增浏览器测试 |
| Windows 原生 / Prism 实机 | 未验收 |

本地临时签名不等于 Apple 公证。没有发布正式版本，也没有替换当前已安装应用。已完成的是首个可运行预览；剩余功能见 [指南](../STATS_USER_GUIDE.md)。

可复现命令：

```sh
npm test
.venv/bin/python -m pytest -q
npm run build
.venv/bin/python packaging/build_engine.py
npm run desktop:build -- --config src-tauri/tauri.stats-preview.conf.json
.venv/bin/python scripts/verify_stats_engine.py 'src-tauri/target/release/bundle/macos/Titan Stats Preview.app/Contents/Resources/engine/wb-engine/wb-engine'
npm run test:e2e -- tests/browser/stats-workspace.spec.ts
```

固定数值基准为合成数据，不代表真实实验。冻结图形与当前数据分开保存；统计校正家族不会因仅显示部分组对而改变。
