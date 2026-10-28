# CP5：净积分与 QC

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：原始积分减面积×背景并集均值；亮/暗极性显式处理；保留负值；显式 ADC 上界；饱和、非正值、未复核等阻止比例计算并保留记录。

自动验证：tests/test_engine.py、test_analysis.py、test_scientific_boundaries.py：手算 80、暗/亮信号等价、负数 -20、4095 clipping 0.25、重叠背景并集、未知上界、越界与背景重叠拒绝。合成示例 24 测量/12 目标/1 阻止/6 生物学单位，treated fold 均值约 1.993978549。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：数字未饱和不代表实验线性；linear_validated 是用户声明，尚无真实 WB 准确性结论。
