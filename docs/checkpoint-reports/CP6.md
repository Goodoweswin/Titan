# CP6：归一化与重复

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：目标显式引用相同原始泳道参考；膜内技术比值均值→IBC 桥接→同样本跨膜等权；IBC 不计 n；分组与膜完全混杂时禁止合并。

自动验证：tests/test_normalization.py：技术泳道数不改变生物学权重、跨膜结果为 4 而非 10/3、缺少 IBC 拒绝、IBC 探索性 QC 随行/汇总传播。test_analysis.py：错 lane 参考、未复核目标被阻止。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：真实多图的样本/膜/参考配对与 IBC pool 身份须用户实验记录确认，不能由图像推断。
