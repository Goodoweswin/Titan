# CP3：ROI 与工作台

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：SVG 工作台使用原图坐标；手绘、移动/调整、背景、数值编辑、缩放、撤销/重做、样本表；编辑递增版本并使复核/旧结果失效。

自动验证：src/state.test.ts：缩放坐标、不可变历史、审核失效、保存/导入晚到、撤销后的磁盘基线、不同项目结果隔离。tests/browser/workflow.spec.ts：缩放后画框、撤销、延迟真实复核不覆盖新输入。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：浏览器交互连接真实 Python；尚未在 macOS WebView 重做这些交互。
