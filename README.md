# Titan

Titan 是免费使用的本地实验图像分析桌面应用，提供 Western blot、免疫荧光以及统计与绘图功能。

## 下载

请到 **[GitHub Releases](https://github.com/Goodoweswin/Titan/releases)** 下载 Mac 或 Windows 安装包。Beta 表示测试版，更新内容与验证范围以对应版本说明为准。

| 系统 | 安装包 |
| --- | --- |
| macOS 14+，Apple Silicon | `*-macos-arm64.dmg` |
| Windows 10/11，x64 | `*-windows-x64-setup.exe` |

发布页面同时提供 `SHA256SUMS.txt` 和第三方许可归档。macOS 当前采用临时签名，Windows 未配置商业签名；尚未提供 Intel Mac、Windows ARM 或 Linux 安装包。

分析和项目保存继续在本地进行。源码管理调整不增加强制登录、付费、设备绑定或联网使用限制。更新方式请看对应版本说明。

## 源码与许可

后续产品源码已迁入私有开发仓库。本公开仓库继续保留安装包下载、更新说明、[问题反馈](https://github.com/Goodoweswin/Titan/issues)和历史开源代码。

已按 MIT 发布的源码及其既有授权继续保留，例如 [v0.4.5-beta.1 历史源码](https://github.com/Goodoweswin/Titan/tree/v0.4.5-beta.1)。该历史许可不代表后续安装包中的所有新增内容都采用 MIT；请查阅安装包附带的许可与第三方声明。

新版本公开标签指向 `distribution` 分支的发布元数据。GitHub 自动生成的 Source code ZIP/TAR 对这些新标签提供的是元数据，不包含后续私有产品源码。

## 使用与反馈

- [使用指南](docs/USER_GUIDE.md) · [免疫荧光指南](docs/IF_USER_GUIDE.md) · [统计指南](docs/STATS_USER_GUIDE.md)
- [问题反馈](https://github.com/Goodoweswin/Titan/issues) · [安全报告](SECURITY.md)

仓库里的旧设计、截图和开发文档描述历史版本，当前界面以实际安装包为准。软件仍处于 Beta 阶段；自动化测试不等同于真实 WB/IF 科学准确性或完整原生操作验收。
