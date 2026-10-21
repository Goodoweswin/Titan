# Titan WB 开发检查点

本文件为唯一 CP 状态记录。日期：2026-10-21；版本：0.1.0 内部试用版。

| CP | 交付 | 当前状态 | 证据 |
|---|---|---|---|
| CP0 | 已批准的 macOS/Tauri 方案、WB 方法与参考核心 | 已通过 | [报告](checkpoint-reports/CP0.md) |
| CP1 | Tauri、Rust IPC、内置 Python 引擎 | 实现/自动测试/构建通过；原生启动关闭待验收 | [报告](checkpoint-reports/CP1.md) |
| CP2 | TIFF/PNG、独立预览、原图保真、项目保存重开 | 实现/自动测试通过；原生文件对话框待验收 | [报告](checkpoint-reports/CP2.md) |
| CP3 | 原图坐标 ROI、背景、缩放、撤销、样本映射 | 实现/自动与浏览器测试通过；原生交互待验收 | [报告](checkpoint-reports/CP3.md) |
| CP4 | 指定区域候选条带与人工纠错 | 实现/自动测试通过；真实图像性能待 CP10 | [报告](checkpoint-reports/CP4.md) |
| CP5 | 净积分、QC、复核门槛 | 实现/合成真值测试通过；实际实验有效性待 CP10 | [报告](checkpoint-reports/CP5.md) |
| CP6 | 参考、技术重复、生物学单位、IBC | 实现/层级数值测试通过；用户实验映射待 CP10 | [报告](checkpoint-reports/CP6.md) |
| CP7 | 分析块图表、描述统计、受限两组统计 | 实现/自动测试通过；原生图形与真实设计待验收 | [报告](checkpoint-reports/CP7.md) |
| CP8 | 多图计算、完整导出、原子保存/备份恢复 | 实现/自动测试通过；原生关闭/恢复流程待验收 | [报告](checkpoint-reports/CP8.md) |
| CP9 | arm64 .app/.dmg、独立引擎测试、版本/许可清单 | 构建/独立引擎/保存重开/导出/hash/本地签名通过；原生安装流程待权限 | [报告](checkpoint-reports/CP9.md) |
| CP10 | 用户真实 WB、人工参照与使用验收 | 待真实数据；尚未提供 | [报告](checkpoint-reports/CP10.md) |

通过规则：必要检查未运行不算完整通过。浏览器交互、源码单测、安装包内置引擎检查与真实 macOS 窗口验收分别记录。当前不宣称 CP1–9 整体完成。

工具仍返回 `Computer Use was not approved to use Titan WB`。已收到用户允许操作的意愿，但工具权限尚未生效；没有绕过该限制操作电脑。

[设计](superpowers/specs/2026-10-21-wb-app-design.md) · [实施计划](superpowers/plans/2026-10-21-wb-app-tauri.md) · [使用说明](USER_GUIDE.md) · [审阅修正](checkpoint-reports/review.md)
