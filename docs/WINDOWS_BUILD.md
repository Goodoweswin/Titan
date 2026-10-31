# Windows x64 安装包构建

目标：Windows 10/11 x64，NSIS `-setup.exe`，当前用户安装。缺少 WebView2 时安装程序联网下载运行库。Python 和科学计算依赖随引擎打包，使用者不必自行安装。

## GitHub 构建

将当前源码上传到指定仓库，在 Actions → Windows installer → Run workflow 运行。独立分支 `codex/windows-installer` 的推送也会自动触发。成功后下载 `Titan-WB-Windows-x64` artifact ZIP，解压得到安装程序。本工作流不自动发布 Release；安装程序未配置商业代码签名。

## Windows 本地构建

需要 x64 Python 3.11（带 py launcher）、Node.js 22、Rust MSVC、Visual Studio Build Tools 的 C++ 桌面开发组件和 Windows SDK。使用 PowerShell 在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

脚本安装项目依赖、执行测试、打包 Python 引擎，再生成安装包。输出：
`src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/*-setup.exe`。

## 验证边界

必须以 Windows 构建成功及产物为准，macOS 上通过测试不代表 Windows 安装验收已完成。安装后检查合成示例、曲线、候选确认、中文路径保存/重开、PNG/SVG 导出，再用真实 WB 数据核对结果。

## 当前公开版本

请从 [GitHub Releases](https://github.com/Goodoweswin/Titan/releases/tag/v0.1.0-beta.2) 下载当前预发布包，并使用发布附件 SHA256SUMS.txt 核对。下面的首次构建记录仅为历史记录，其 hash 不用于新版。

## 首次 Windows 安装包

- 版本：0.1.0，Windows x64，2026-10-26 构建。
- 源码提交：`90aa736207010188d39a70ac03bf6aeb102c60d7`，分支 `codex/windows-installer`。
- [成功构建记录](https://github.com/Goodoweswin/Titan/actions/runs/40274718213)。Windows runner 上 74 项 Python 测试和 39 项前端单元测试通过。
- 文件：`release/windows/Titan WB_0.1.0_x64-setup.exe`，NSIS 安装程序。
- SHA-256：`7c9c65af71f09fd19014059efcae2452371eaad7d8c477dd01e65196645f32ad`。
- 尚未完成真实 Windows 桌面的安装及界面操作验收，未配置商业代码签名。
