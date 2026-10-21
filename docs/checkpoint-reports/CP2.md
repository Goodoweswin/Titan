# CP2：原图与项目

版本 0.1.0，2026-10-21；完整 CP 状态见 ../checkpoints.md。

实现：原始灰度 TIFF/PNG 保留位深、hash 和原字节；预览独立拉伸；项目复制原图，以 session 锁和 revision 控制写入，manifest 原子替换并保留上一份备份。

自动验证：tests/test_projects.py：uint16 的 12345 保真、RGB/多页拒绝、中文路径、移除外部源图后重开、hash 篡改、版本冲突、锁、只读、释放与损坏备份恢复。

最终完整回归命令：`.venv/bin/python scripts/check_cp.py FINAL`（四层退出码记录于 artifacts/checkpoints/FINAL/checks.json）。浏览器命令：`npm run test:e2e`，3 项通过；日志 artifacts/checkpoints/browser-final.log。源码与浏览器检查不等同于安装后的原生 GUI 验收。早期失败用例日志集中保留在 artifacts/checkpoints/CP1/cp*-red.log。

边界与待验收：原生导入/保存文件选择器、多窗口与操作系统中断注入尚未验收。
