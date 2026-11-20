# Titan 应用内更新

支持应用内更新的 Titan 在启动后后台检查一次。发现新版时，左栏底部的账户上方会显示「更新并重启」。点击一次就会下载并校验新版，保存当前工作，然后安装并重启。下载期间可点击「稍后安装」，让下载继续，在准备好时从左栏点「安装更新并重启」。有分析任务、条带候选或组图草稿待处理时，Titan 会保留已下载的更新包，等你处理后再安装。

## 启用 Beta 更新渠道

首次分发时需要安装启用了更新渠道的版本。后续版本从同一个 HTTPS 地址检查更新。已有安装包是在启用前构建的，需要完成一次升级安装才能使用新的入口。

在发布环境使用 Tauri CLI 生成更新签名密钥。将公钥嵌入构建配置，只在签名构建步骤通过 `TAURI_SIGNING_PRIVATE_KEY` 和 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 提供私钥及密码。同一渠道的安装包使用同一公钥。macOS Developer ID 签名和公证是独立的发布配置。旧版本的系统文件访问授权是否延续，取决于系统识别到的代码签名身份。[Tauri 更新文档](https://v2.tauri.app/plugin/updater/) · [Apple 代码签名要求](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements/)

正式 Mac Apple Silicon 和 Windows x64 构建通过 [Beta 配置](../../src-tauri/tauri.beta.conf.json)嵌入公钥和检测地址。普通本地构建使用基础配置，启动时跳过联网检查。检测地址是 `updates` 分支根目录中的 `beta.json`。[Beta 清单](https://raw.githubusercontent.com/Goodoweswin/Titan/updates/beta.json)

1. 更新应用版本和对应的发行说明。从验收过的提交推送 `v<应用版本>-beta.<序号>` 标签。每次应用内更新都需要递增应用版本。
2. [Release workflow](../../.github/workflows/release.yml) 构建 Windows x64 安装包及 Mac Apple Silicon 安装包。Mac 使用 `.app.tar.gz` 更新，Windows 使用 NSIS `.exe` 更新。两个下载都附有 `.sig`，发布流程核对文件签名和签名中绑定的应用版本。
3. Release workflow 从草稿重新下载核对附件和 SHA-256，公开预发行版并确认两种更新包可下载，再更新 `beta.json`。如果构建已成功但发布作业中断，用 `gh run rerun <run-id> --failed` 使用同一次构建的产物重试。已激活版本的签名与地址只能原样重试。

如果需要暂停推送某版，保留 `updates` 分支的 `beta.json` 版本号，将 `platforms` 改为 `{}` 并提交。保留版本号可以阻止旧作业重跑时重新启用同一版本。已经升级的应用会保留当前版本，修复后发布更高版本。

公开启用前，用发布配置完成一次从已安装旧版到新版的原生操作，核对旧版启动时显示更新入口、错误签名被拒绝、一键更新和稍后安装，以及重启后可打开已保存的数据。新版启动后，更新入口应隐藏。

Windows 0.4.5 及更早的安装包需要手动安装首个启用应用内更新的 Beta。Windows 更新前保存当前分析并停止本地引擎，由 NSIS 安装程序负责重启。安装器启动失败时会保留旧窗口和已验证的下载，可继续使用或重试。更新包的 Tauri 签名与 Windows Authenticode 代码签名分别配置。

在 GitHub Actions 手动运行 Release workflow 可在隔离的 Windows runner 实测 NSIS 升级。该入口验证拒绝篡改包、重试、自动重启及重开已保存的分析。测试使用独立的签名和回环清单，手动运行生成的产物保留在 Actions 中。
