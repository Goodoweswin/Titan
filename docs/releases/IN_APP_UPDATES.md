# Titan 应用内更新

支持应用内更新的 Titan 在启动后后台检查一次。发现新版时，左栏底部的账户上方会显示「更新并重启」。点击一次就会下载并校验新版，保存当前工作，然后安装并重启。下载期间可点击「稍后安装」，让下载继续，在准备好时从左栏点「安装更新并重启」。有分析任务、条带候选或组图草稿待处理时，Titan 会保留已下载的更新包，等你处理后再安装。

## 启用 Beta 更新渠道

首次分发时需要安装启用了更新渠道的版本。后续版本从同一个 HTTPS 地址检查更新。已有安装包是在启用前构建的，需要完成一次升级安装才能使用新的入口。

在发布环境使用 Tauri CLI 生成更新签名密钥。将公钥嵌入构建配置，只在签名构建步骤通过 `TAURI_SIGNING_PRIVATE_KEY` 和 `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` 提供私钥及密码。同一渠道的安装包使用同一公钥。macOS Developer ID 签名和公证是独立的发布配置。旧版本的系统文件访问授权是否延续，取决于系统识别到的代码签名身份。[Tauri 更新文档](https://v2.tauri.app/plugin/updater/) · [Apple 代码签名要求](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements/)

给现有 Mac 发布构建追加 `--config <更新配置文件>`。以下值需替换成发布渠道的 HTTPS 地址和 `.pub` 文件内容。普通本地构建使用空的更新配置，启动时跳过联网检查。

```json
{
  "bundle": { "createUpdaterArtifacts": true },
  "plugins": {
    "updater": {
      "pubkey": "<.pub 文件内容>",
      "endpoints": ["https://updates.example.com/titan/beta.json"],
      "requireSignedVersion": true
    }
  }
}
```

保持生产构建的应用标识和安装方式。把 Mac 的 `.app.tar.gz` 及对应的 `.sig` 随版本一起发布。Tauri 构建会将应用版本写入签名，需要让清单的 `version` 与产物的实际版本一致。每次推送更新递增应用的语义版本。公开发布标签可以包含 `-beta` 后缀，清单中的值以客户端二进制的版本为准。

在确认更新附件可下载后，再发布固定地址上的 Beta 清单。`signature` 填 `.sig` 的内容，下载 URL 指向该版本的固定资源地址。GitHub 的 latest 接口会跳过预发布，Beta 渠道需要独立地址。[GitHub Releases API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)

```json
{
  "version": "0.4.4",
  "notes": "这里显示本次更新内容。",
  "platforms": {
    "darwin-aarch64": { "url": "https://example.com/Titan.app.tar.gz", "signature": "<Mac .sig 内容>" }
  }
}
```

公开启用前，用发布配置完成一次从已安装旧版到新版的原生操作，核对旧版启动时显示更新入口、错误签名被拒绝、一键更新和稍后安装，以及重启后可打开已保存的数据。新版启动后，更新入口应隐藏。

Windows 继续通过 NSIS 安装包更新。当前 Tauri 插件会在启动 Windows 安装程序前隐藏主窗口、清理更新资源。安装器启动失败时，应用无法用原窗口重试。修复并实测这一失败路径后，再为 Windows 启用应用内更新。
