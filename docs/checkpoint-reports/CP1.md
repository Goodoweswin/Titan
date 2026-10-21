# CP1：Tauri、Python引擎与最小安装验证

状态：进行中（尚未完成原生安装包启动验收）。

已观察RED：引擎4项合同测试失败、前端2项项目身份测试失败。
已观察GREEN：Python25项（含参考21项）、前端2项、冻结引擎真实净积分80；Rust检查日志见artifacts目录。

架构：Tauri→Rust受限命令→冻结Python引擎，stdin/stdout JSON；无常驻端口。单次请求60秒超时，子进程kill_on_drop。

环境：macOS arm64、Python3.11、Node22。NumPy/SciPy当前解析wheel要求macOS14，因此安装包最低系统设为14.0。完整版本锁在requirements.lock、package-lock.json、Cargo.lock。

最小.app正在构建；只有实际启动并确认净积分80后，CP1才可通过。
