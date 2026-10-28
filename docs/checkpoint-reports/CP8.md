# CP8：批量计算、导出与恢复

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：多图导入逐项保留失败提示；同版本项目内全部 ROI 计算；取消等待/输入变更后丢弃晚到结果。CSV/JSON/PNG/SVG/原图/ROI 叠加/hash 导出到新目录。已保存项目空闲自动保存，损坏 manifest 从有效备份恢复至新副本。

自动验证：tests/test_export.py：全部输出 hash、拒绝覆盖、拒绝旧版本。tests/test_projects.py：活跃外部锁不能恢复、坏 manifest 保留并另建恢复副本。前端与真实 Python 浏览器测试覆盖晚到复核和编辑失效。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：尚无最近项目列表。保存结果可重新计算；不恢复上次未导出的结果页面。取消等待不会中止引擎，最长由 60 秒超时收尾。原生退出提示/恢复按钮、自动保存与崩溃情景仍待 GUI 验收。
