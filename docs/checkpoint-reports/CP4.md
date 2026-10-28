# CP4：候选条带

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：仅在用户指定的 y 区域，以两侧局部背景和投影给出候选；不自动判定蛋白身份，不自动通过复核。可移动、删框、补框和编辑映射。

自动验证：tests/test_analysis.py：合成示例给出 12 候选；tests/test_scientific_boundaries.py：空白无候选、水平/垂直梯度背景中识别强弱两个条带；旧 revision 的结果被前端丢弃。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：只验证了有限合成情形；真实条带缺失、smear、邻带干扰与校正率须 CP10 测定。
