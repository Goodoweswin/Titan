# Titan 版本注册表

公开发布审计日期 **2026-11-13（Asia/Shanghai）**。本表登记公开发布、本机构建和安装事件。按 Git 标签或表中的构建编号识别具体版本。多个构建可以显示同一个应用版本号，例如 `0.4.0`。功能变更见 [CHANGELOG](../../CHANGELOG.md)。

## 正在准备

`v0.4.2-beta.1`（显示版本 `0.4.2`）正在构建和验证，尚不作为已公开产物登记。[发布说明](v0.4.2-beta.1.md)列明管理员登录已接通及邮件功能尚未开放的边界；两平台的实际附件和校验结果将在发布完成后登记。

## 公开发布

以下为 GitHub 当前公开的测试版，均有 macOS Apple Silicon 和 Windows x64 附件。发布日按北京时间登记。安装包、`SHA256SUMS.txt` 和许可附件可从对应发布页取得。

| 发布标签 | 发布日 | 标签对应提交 | 发布验证与校验记录 |
| --- | --- | --- | --- |
| **[v0.4.1-beta.3](https://github.com/Goodoweswin/Titan/releases/tag/v0.4.1-beta.3)** | 2026-11-07 | `a13b349` | [验证报告](v0.4.1-beta.3-verification.json) |
| [v0.4.0-beta.3](https://github.com/Goodoweswin/Titan/releases/tag/v0.4.0-beta.3) | 2026-11-07 | `80d552c` | [验证报告](v0.4.0-beta.3-verification.json) |
| [v0.3.4-beta.1](https://github.com/Goodoweswin/Titan/releases/tag/v0.3.4-beta.1) | 2026-11-02 | `5af3814` | [验证报告](v0.3.4-beta.1-verification.json) |
| [v0.3.3-beta.2](https://github.com/Goodoweswin/Titan/releases/tag/v0.3.3-beta.2) | 2026-11-02 | `6f6bcfb` | [验证报告](v0.3.3-beta.2-verification.json) |
| [v0.3.2-beta.1](https://github.com/Goodoweswin/Titan/releases/tag/v0.3.2-beta.1) | 2026-11-01 | `d0bfca4` | [验证报告](v0.3.2-beta.1-verification.json) |
| [v0.3.1-beta.2](https://github.com/Goodoweswin/Titan/releases/tag/v0.3.1-beta.2) | 2026-11-01 | `ac96c01` | [验证报告](v0.3.1-beta.2-verification.json) |
| [v0.1.0-beta.2](https://github.com/Goodoweswin/Titan/releases/tag/v0.1.0-beta.2) | 2026-10-28 | `e6eb0fb` | [验证报告](v0.1.0-beta.2-verification.json) |

### 已打标签但未公开发布

| 标签 | 标签对应提交 | 发布流程停止的位置 |
| --- | --- | --- |
| `v0.4.1-beta.2` | `2781dd5` | Windows 免疫荧光后台状态文件读取发生短暂权限冲突，测试失败。[Windows 构建日志](https://github.com/Goodoweswin/Titan/actions/runs/42282907086/job/128116215443) |
| `v0.4.1-beta.1` | `e9a1f15` | Windows 统计组件测试使用了 POSIX Python 路径，构建失败。[Windows 构建日志](https://github.com/Goodoweswin/Titan/actions/runs/42282192428/job/128113755430) |
| `v0.4.0-beta.2` | `3d8872c` | Windows 免疫荧光任务检查失败。[记录](v0.4.0-beta.3.md) |
| `v0.4.0-beta.1` | `abe8725` | macOS 14 构建环境退役，任务取消。[记录](v0.4.0-beta.2.md) |
| `v0.3.3-beta.1` | `de36ab7` | Windows 中文 WB 组图保存检查失败。[记录](v0.3.3-beta.1-verification.json) |
| `v0.3.1-beta.1` | `e5b250b` | Windows 常驻引擎身份检查失败。[记录](v0.3.1-beta.2.md) |
| `v0.1.0-beta.1` | `368ccd4` | 第三方许可 ZIP 归档因时间戳失败。[记录](v0.1.0-beta.1.md) |

## 本机构建

这些编号用于注册表。以下本机记录的目标平台均为 macOS arm64。整合构建显示 `0.4.1`，历史构建显示 `0.4.0`。

| 构建编号 | 源码与基础版本 | 主要范围 | 验收及分发状态 |
| --- | --- | --- | --- |
| `local-20261113-release-042` | `93fe85e` · 显示版本 `0.4.2` | 账户／菜单整合版本及双平台发行配置 | 本地 Mac App／DMG、实际打包引擎保存与导出、版本／issuer／签名和许可清单检查通过；未替换本机安装。GitHub 双平台发布仍在进行。[本地验证记录](v0.4.2-beta.1-local-verification.json) |
| `local-20261113-context-menu` | `codex/unified-context-menu` · `7d748b9` · 账户整合基线 `5ce46de` · 显示版本 `0.4.1` | 项目、分析、图表与导出的统一右键／省略号菜单；统计明确排除／恢复 | 已安装 `/Applications/Titan.app`；旧应用和项目库已备份。140 项前端、106 项完整浏览器、346 项 Python 检查及本机打包通过；账户服务、Windows／Linux 原生测试和 Windows 安装包构建通过。合成原生验收覆盖菜单、取消、键盘、数值、撤销和快照只读；系统访问确认后，最终安装版已核对旧 WB、IF、关联统计、冻结图和来源只读菜单；登录状态保留，结束时恢复首页。[验证记录](local-20261113-context-menu-verification.json) |
| `local-20261112-account-activity` | 账户工作区 · `e4538ee` · 显示版本 `0.4.1` | 账户中栏、正方形活动格、每日／每周／累计总量；保留统计 PNG/PDF 导出 | 曾安装并启动 `/Applications/Titan.app`。签名、主程序哈希、打包 WB 保存／重开和统计 PNG/PDF 导出通过；原生窗口核对账户中栏及三种活动视图，旧应用和数据已备份。[本机验证报告](local-20261112-account-activity-verification.json) |
| `local-20261112-sidebar-appearance` | `codex/sidebar-system-appearance` · `b274098` · 基础 `v0.4.1-beta.3` | 左栏、搜索框、选中行及项目菜单跟随系统明暗外观 | 曾安装至 `/Applications/Titan.app`。GitHub 完整 84 项浏览器、88 项前端、346 项 Python 检查及 Mac 构建通过；原生窗口已核对日间浅色左栏。用户确认系统访问后，旧项目及未确认的 TIFF 选页窗口已恢复。[本机验证报告](local-20261112-sidebar-appearance-verification.json) |
| `local-20261112-navigation-panels` | `codex/independent-project-workspace` · `bb39acc` · 基础 `v0.4.1-beta.3` | 固定前进／后退导航、独立折叠左右栏、紧凑项目字体 | 曾安装至 `/Applications/Titan.app`。GitHub 完整 83 项浏览器、88 项单元及 346 项 Python 检查通过；原生窗口已显示紧凑左栏。用户完成系统验证后，已打开既有 WB 分析。[本机验证报告](local-20261112-navigation-panels-verification.json) |
| `local-20261112-navigation-panels-preview` | `codex/independent-project-workspace` · `924c700` · 基础 `v0.4.1-beta.3` | 前进／后退、分析位置恢复和左右面板折叠 | 曾安装至 `/Applications/Titan.app`。GitHub 完整 82 项浏览器、88 项单元及 346 项 Python 检查通过；原生窗口已核对前进／后退和左右面板。[本机验证报告](local-20261112-navigation-panels-preview-verification.json) |
| `local-20261112-page-cards` | `codex/independent-project-workspace` · `b635b56` · 基础 `v0.4.1-beta.3` | TIFF 页面改为整卡选择，加大卡片和状态方框，区分选中与预览 | 曾安装至 `/Applications/Titan.app`。82 项单元检查及 6 项页面选择、项目回归检查通过；原生窗口已恢复原 TIFF 页面选择。[本机验证报告](local-20261112-page-cards-verification.json) |
| `local-20261112-system-appearance` | `codex/independent-project-workspace` · `959169b` · 基础 `v0.4.1-beta.3` | WB、IF、统计工作区和弹窗跟随系统夜间外观，保留科学图像及论文图配色 | 曾安装至 `/Applications/Titan.app`。82 项单元检查、22 项浏览器检查通过；原生窗口已打开既有 WB、IF 和关联统计分析，结束时恢复原 IF 页面。[本机验证报告](local-20261112-system-appearance-verification.json) |
| `local-20261110-stable-sidebar` | `codex/independent-project-workspace` · `76ec5c6` · 基础 `v0.4.1-beta.3` | 固定项目左栏、拖动栏宽、统计与 IF 工作区导航 | 曾安装至 `/Applications/Titan.app`。原生窗口已核对调宽、复位和统计工具切换。[本机验证报告](local-20261110-stable-sidebar-verification.json) |
| `local-20261108-independent-project` | `codex/independent-project-workspace` · `e7da547` · 基础 `v0.4.1-beta.3` | 独立项目工作区、项目资料副本和项目包搬迁 | 曾安装至 `/Applications/Titan.app`。打包引擎通过跨库恢复与 WB 导出验证，原生窗口已核对首页和 WB 工具入口。[本机验证报告](local-20261108-independent-project-verification.json) |
| `local-20261107-integrated-041` | `codex/titan-0-4-1` · `0dd290b` · 基础 `v0.4.0-beta.3` | 项目侧栏、WB／IF 来源关联、统计与出图、精度修复 | 曾安装至 `/Applications/Titan.app`。隔离 macOS 窗口已通过关联表保存及冻结图重开。[本机验证报告](v0.4.1-beta.1-local-verification.json) |
| `local-20261107-sidebar` | `codex/project-analysis-sidebar` · `e440e48` · 统计基础 `a4c0711` | 课题侧栏、WB／IF／统计分析归类和续做、冻结图与导出记录 | 独立验收包 `com.titan.wb.sidebarqa`。构建记录包含 63 项浏览器回归及 macOS 原生新建、搜索、冻结图恢复与取消关闭。Windows 原生待验收。[验收记录](../superpowers/plans/2026-11-07-project-analysis-sidebar.md) |
| `local-20261107-stats-source` | `codex/statistics-v04` · `bba4d7f` · 基础 `a4c0711`。候选包同时包含工作区中的图像指引改动 | 从 WB／IF 按指标取数、版本化来源快照、统计关联表保存的浮点精度修复 | 候选包 `com.titan.wb` 已构建。记录包含打包引擎验证及精度修复前的原生流程检查。最终包安装后保存与重开、浏览器和 Windows 原生验收待做。证据在统计工作区的 `docs/checkpoint-reports/project-results-statistics.md` 和同名 JSON。 |
| `local-20261107-stats-main` | `2c10023` · 基础 `v0.4.0-beta.3` | 独立统计工作区合入 Titan 主应用，支持表格、分析和冻结图 | 曾安装至 `/Applications/Titan.app`，现为历史安装。[安装记录](../checkpoint-reports/titan-main-installation.json) |
| `local-20261107-stats-preview-beta3` | `2c10023` · 基础 `v0.4.0-beta.3` | 独立统计工作区的 beta.3 预览 | 独立预览包 `com.titan.stats.preview`。已检查打包引擎及 macOS 原生打开旧统计项目和恢复冻结图。[验收记录](../checkpoint-reports/statistics-beta3-integration.json) |
| `local-20261107-stats-preview-beta2` | `7cd9690` · 基础 `v0.4.0-beta.2` | 首个独立统计与绘图预览 | 独立预览包 `com.titan.stats.preview`。已检查打包引擎及 macOS 原生统计、出图和快照。验收记录见 `7cd9690` 中的 `docs/checkpoint-reports/statistics-v04.md`。 |

侧栏构建和最新统计候选构建分属两条分支。历史侧栏验收包尚未纳入 `bba4d7f`。整合构建 `local-20261107-integrated-041` 包含两条分支。更早的本地版本和功能变更见 [CHANGELOG](../../CHANGELOG.md)。

### 本机产物校验

统计工作区是主 Titan 工作区下的 `artifacts/statistics-v04`，侧栏工作区对应分支 `codex/project-analysis-sidebar`。下表文件名和路径相对于各自工作区。对于应用目录，校验对象精确到主程序或内置引擎。

| 构建编号或安装位置 | 校验对象 | SHA-256 |
| --- | --- | --- |
| `local-20261113-context-menu` | `/Applications/Titan.app/Contents/MacOS/titan-wb` | `bd0e5596665de9cf155cfd4e8e0277e592d5f06d6ef9159ec85114810dc80ff0` |
| `local-20261113-context-menu` | `/Applications/Titan.app/Contents/Resources/engine/wb-engine/wb-engine` | `25c5f7ba4e2b4d48de8ad025ced2632e0027a883318ba248a3f3f66240d245e7` |
| `local-20261112-account-activity` | `/Applications/Titan.app/Contents/MacOS/titan-wb` | `6d326a37c23667fccce37c81d2dc23dc74ee791d96c585a94291cbdd0fcd6aa8` |
| `local-20261112-account-activity` | `/Applications/Titan.app/Contents/Resources/engine/wb-engine/wb-engine` | `25c5f7ba4e2b4d48de8ad025ced2632e0027a883318ba248a3f3f66240d245e7` |
| `local-20261107-sidebar` | `artifacts/Titan-Sidebar-macOS-arm64-QA.zip` | `26f5e4159c59abae15ac860890666ba7ccf7a2137839b1150296bccc6f2c7f91` |
| `local-20261107-stats-source` | `src-tauri/target/release/bundle/macos/Titan.app/Contents/MacOS/titan-wb` | `ac9505716aac276a95ca841ca081c5360d1aa21ade7752427d78c69cdc31a61b` |
| `local-20261107-stats-preview-beta3` | `artifacts/Titan_0.4_beta3_Stats_Preview_macos-arm64.zip` | `88bb4c70a10e5c2fd773979bafee12c8b5cbee2d474d1663cd8fb68f0b332c75` |
| `local-20261107-stats-preview-beta2` | `artifacts/Titan_0.4_Stats_Preview_macos-arm64.zip` | `9dce70ed70a2dbc6a4607c7ea6fb8a037a0c7f382ab4ef28395a683f62b7a416` |
| 前一版本机安装 | `Contents/MacOS/titan-wb` | `035ddfcd129fdcaae7dbb2d9e3b3698b036aad00200ab2859939963d4e416519` |
| 前一版安装及 `local-20261107-stats-source` | `Contents/Resources/engine/wb-engine/wb-engine` | `d13f9642d4e1ce29bca86580ccd90aaabb8c3cf1bbb01530b5e88a35eff6682c` |

## 本机安装记录

| 日期（北京时间） | 位置与应用标识 | 安装状态 |
| --- | --- | --- |
| 2026-11-13 04:37 | `/Applications/Titan.app` · `com.titan.wb` | **当前安装** `local-20261113-context-menu`，显示版本 `0.4.1`，源码 `7d748b9`；主程序签名和哈希已核对，内置引擎保持前版，安装后项目库索引未变。系统访问确认后，旧项目与登录已恢复，原生菜单核对通过，结束时恢复首页。[校验值与备份](local-20261113-context-menu-verification.json) |
| 2026-11-12 21:58 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261112-account-activity`，显示版本 `0.4.1`，源码 `e4538ee`。原生已验证账户中栏、正方形日历和每日／每周／累计切换，活动记录和配色保留；项目库文件哈希未变。[校验值和备份位置](local-20261112-account-activity-verification.json) |
| 2026-11-12 12:38 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261112-sidebar-appearance`，显示版本 `0.4.1`。旧应用和项目库已备份；已核对实际浅色左栏，已恢复原 WB 分析及未选择页面的 TIFF 窗口。[校验值和备份位置](local-20261112-sidebar-appearance-verification.json) |
| 2026-11-12 03:54 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261112-navigation-panels`，显示版本 `0.4.1`。旧应用及项目库已备份，主程序和内置引擎校验通过。[校验值和备份位置](local-20261112-navigation-panels-verification.json) |
| 2026-11-12 03:45 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261112-navigation-panels-preview`，原生验证前进、后退及左右面板折叠通过。[校验值和备份位置](local-20261112-navigation-panels-preview-verification.json) |
| 2026-11-12 03:01 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261112-page-cards`，显示版本 `0.4.1`。旧应用和项目库已备份；已恢复原 WB 分析和 TIFF 页面选择窗口。[校验值和备份位置](local-20261112-page-cards-verification.json) |
| 2026-11-12 02:13 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261112-system-appearance`，显示版本 `0.4.1`。旧应用和项目库已备份；本机打开原 IF、WB 和统计分析成功。[校验值和备份位置](local-20261112-system-appearance-verification.json) |
| 2026-11-10 18:21 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261110-stable-sidebar`。旧版和项目库已备份。当时桌面来源等待 macOS 重新授权。[校验值和备份位置](local-20261110-stable-sidebar-verification.json) |
| 2026-11-08 23:41 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261108-independent-project`。已备份前版应用及本地项目库。[校验值和备份位置](local-20261108-independent-project-verification.json) |
| 2026-11-07 03:25 | `/Applications/Titan.app` · `com.titan.wb` | 此前安装 `local-20261107-integrated-041`。主程序和内置引擎均与本地构建匹配。旧项目库已备份。macOS 签名变更后，打开桌面来源需在系统提示中重新授权。[本机验证报告](v0.4.1-beta.1-local-verification.json) |
| 2026-11-07 | `/Applications/Titan.app` · `com.titan.wb` | 前一版包含 WB／IF 结果对接统计，精确提交未单独登记。此前精度修正包与前一版的内置引擎哈希一致，主程序哈希不同。证据见统计工作区 `docs/checkpoint-reports/project-results-statistics.json`。 |
| 2026-11-07 01:44 | `/Applications/Titan.app` · `com.titan.wb` | 曾安装 `local-20261107-stats-main`，备份了此前的 `0.3.4` 和项目库。[安装记录](../checkpoint-reports/titan-main-installation.json) |

本轮结果对接前的备份位于主 Titan 工作区的 `artifacts/local-installations/before-project-results-20261107-021953`。

## 登记方式

1. **构建完成**时登记唯一编号、应用显示版本、源码提交、基础标签、目标平台和应用标识。如构建包含未提交改动，记录涉及范围。为归档包记录 SHA-256，为应用目录注明核对的是哪个文件。
2. **验收完成**时链接检查报告，分开记录自动化、打包引擎和原生窗口验证。保留待验证项目。
3. **公开发布**时登记真实下载页和校验文件，并保留同一提交对应的构建记录。流程停止时保留标签与原因。
4. **本机安装**时追加日期、安装位置、对应构建编号、主程序及内置引擎的哈希和备份位置。安装中断时按磁盘上实际存在的应用登记。
