# Windows x64 安装包构建

目标：Windows 10/11 x64，NSIS `-setup.exe`，当前用户安装。缺少 WebView2 时安装程序联网下载运行库。Python 和科学计算依赖随引擎打包，使用者不必自行安装。

## GitHub 构建

将当前源码上传到指定仓库，在 Actions → Windows installer → Run workflow 运行。成功后下载 `Titan-WB-Windows-x64` artifact ZIP，解压得到安装程序。本工作流不自动发布 Release；安装程序未配置商业代码签名。

## Windows 本地构建

需要 x64 Python 3.11（带 py launcher）、Node.js 22、Rust MSVC、Visual Studio Build Tools 的 C++ 桌面开发组件和 Windows SDK。使用 PowerShell 在项目根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

脚本安装项目依赖、执行测试、打包 Python 引擎，再生成安装包。输出：
`src-tauri/target/x86_64-pc-windows-msvc/release/bundle/nsis/*-setup.exe`。

## 验证边界

必须以 Windows 构建成功及产物为准，macOS 上通过测试不代表 Windows 安装验收已完成。安装后检查合成示例、曲线、候选确认、中文路径保存/重开、PNG/SVG 导出，再用真实 WB 数据核对结果。
