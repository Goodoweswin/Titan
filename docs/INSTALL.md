# 安装、校验与更新

请先从仓库首页选取与电脑匹配的 Beta 安装包。下载页提供各版本的安装包、SHA-256 校验文件和第三方许可归档。[选择安装包](../README.md#下载-beta) · [查看所有版本](https://github.com/Goodoweswin/Titan/releases)

| 系统 | 安装包 | 后续更新 |
| --- | --- | --- |
| macOS 14+，Apple Silicon（M 系列芯片） | `*-macos-arm64.dmg` | 应用内 Beta 更新，也可下载 DMG |
| Windows 10/11，x64 | `*-windows-x64-setup.exe` | 下载并运行新版 EXE |

## 校验下载

从同一个版本下载安装包和 `SHA256SUMS.txt`。运行相应命令，将文件名替换为实际下载的文件名，再与校验表中该文件的摘要对照。摘要一致后安装。

macOS 终端示例

```sh
shasum -a 256 "Titan-0.4.9-macos-arm64.dmg"
```

Windows PowerShell 示例

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath ".\Titan-0.4.9-windows-x64-setup.exe"
```

## 安装

- **macOS** 打开 DMG，把 Titan 拖到「应用程序」，再从「应用程序」打开。公开 Beta 使用临时签名。系统提示无法验证开发者时，先核对下载来源和文件摘要，再参照 Apple 的说明。 [Apple 的应用安全说明](https://support.apple.com/zh-cn/102445)
- **Windows** 打开 EXE 并按安装向导操作。当前公开安装包没有商业代码签名，系统可能显示发布者提示。由单位管理的电脑请遵循该设备的安装要求。

更新前先保存工作并退出正在运行的旧版本。支持应用内更新的 Mac 可使用 Titan 左下方的「更新并重启」。[应用内更新说明](releases/IN_APP_UPDATES.md)

安装后可直接开始本地分析。[快速上手](QUICKSTART.md)
