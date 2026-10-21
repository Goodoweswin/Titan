# CP7：统计与图表

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：默认描述性；显式 Welch/配对 t、raw/log2、双侧 B−A 效应与 95%CI、Holm family。生物学散点按终点/分析块分开；支持配对线；导出图标明均值±SD。

自动验证：tests/test_statistics.py、test_scientific_boundaries.py：配对 log 差 [1,2,3] 的 t=3.464101615/df=2；Holm [.03,.06,.06]；共享 bio、缺配对、多膜普通 t、零方差、非正 log2 拒绝。src/plot.test.ts、tests/test_export.py：图表不混合分析块。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：屏幕图提供散点/均值；导出图使用 SD，尚未提供 SD/CI 切换控件。中文字体和原生窗口图形仍需实机验收。
