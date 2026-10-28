# 最终分支审阅与修正记录

2026-10-21，Tauri 0.1.0 内部试用版。由独立审阅代理检查当前完整分支；发现 0 项 Critical、5 项 Important。进行一次集中修正，再执行完整回归，没有循环重复审阅。

| 问题 | 修正 | 验证 |
|---|---|---|
| 保存/复核/导入的晚到响应可能覆盖新编辑 | 保存只合并磁盘基线/路径；复核严格比对项目与版本；导入仅追加新资产 | state 单测及真实 Python 的延迟复核浏览器回归 |
| 撤销可能还原旧 saved_revision/路径，造成后续保存冲突 | 撤销内容但保留最新磁盘元数据，revision 单调递增 | state 撤销后磁盘基线测试 |
| 导出图可能混合不同膜/分析块 | 图形按 analyte 与 analysis_block 分面 | export 和 plot 分组测试 |
| IBC 的探索性 QC 标记丢失 | IBC 及参考标记传播到行与生物学汇总 | IBC clipping/linearity 标记回归 |
| 恢复路径不尊重锁或用户无法调用备份恢复 | 检查活跃外部写入者；有效备份恢复到新副本；界面开放恢复入口 | 活跃锁拒绝与损坏原文件保留测试 |

另在最终独立发行包检查中实际发现 `No module named 'matplotlib.backends.backend_svg'`。PyInstaller 构建日志证明自动扫描只选中 Agg，SVG 保存时动态加载的模块未收录。打包脚本增加该模块的 hidden import；重新构建，并以相同独立路径测试重跑完整导出流程。最终结果以 CP9 报告为准，不用源码环境通过代替安装包检查。

原生窗口权限未开放、真实数据未提供属于未执行的验收项，不能作为已通过项目。自动保存、原生关闭处理和恢复入口需要进一步原生实机检查。

独立包的完整性检查还发现默认 linker ad-hoc 签名未封装 App 资源（Info.plist 未绑定，Sealed Resources none）。对生成副本执行本地 ad-hoc 签名后相同严格检查退出 0，因此将 macOS signingIdentity 设为 `-`，使 App 与 DMG 构建可重复包含完整的本地签名。验证脚本现在对签名失败返回失败，不能只记录后继续判定成功。这不构成 Apple 开发者签名或公证。

签名集成测试进一步证明 Tauri 默认附加 hardened runtime，与无 Team ID 的 PyInstaller 解包运行库不兼容；本机内部 ad-hoc 版本显式使用 hardenedRuntime=false，并再次完整测试。没有修改系统安全设置；公开分发需单独配置开发者证书、运行库与公证。
