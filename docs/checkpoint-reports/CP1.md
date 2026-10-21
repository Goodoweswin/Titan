# CP1：Tauri 与内置计算引擎

版本 0.1.0，2026-10-21。完整 CP 状态仅记录于 ../checkpoints.md。

实现：Tauri→受限 Rust 命令→JSON stdin/stdout→本地 Python 引擎。发行模式只运行 App 内的 wb-engine；无常驻 HTTP 服务。引擎进程有 60 秒超时及 kill_on_drop；原生关闭权限包含 allow-destroy。

初期 RED：引擎 4 项合同测试与前端项目身份测试失败。CP1 首次 GREEN：Python 25、前端 2、冻结引擎净积分 80。日志见 artifacts/checkpoints/CP1/。

最终回归：scripts/check_cp.py FINAL，四层退出码均为 0，实际摘要见 artifacts/checkpoints/FINAL/checks.json；后续各阶段纳入同一完整回归。Rust 2 项响应/错误协议测试通过。

.app/.dmg 构建日志见 artifacts/checkpoints/final-release-build.log。macOS 14+ arm64；NumPy/SciPy wheel 的系统要求决定最低版本。原生启动/关闭及窗口 IPC 尚未实测：电脑操作工具拒绝访问 Titan WB。冻结引擎直接运行不作为原生 IPC 通过证据。
