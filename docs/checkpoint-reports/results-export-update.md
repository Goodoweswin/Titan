# 0.2.1 结果 Excel / 可视化 / 导出

2026-11-01。本轮补齐真实 OOXML 工作簿和新结果页的图表入口。用户已明确选择“先保留更新包”，**未安装、未退出或重启当前应用**；`/Applications/Titan WB.app` 仍为 0.2.0。

结果页在泳道表下直接显示当前图表，提供“导出 Excel 与图表”。现有预览可调尺寸、字号和 DPI；导出目录包含 `results.xlsx`、`plot.png`、`plot.svg`、CSV、JSON、原图、标注及哈希审计。工作簿有说明、泳道结果、原始测量、参考归一化、生物学汇总、统计结果、样本、图像来源、图表九个工作表。

数字保留原始计算精度，极小非零值用科学计数法显示；未检出为空值并保留状态。文本按字符串保存，公式形态的样本名不会作为公式运行；测量表使用唯一图像 ID 关联来源哈希，避免同名原图混淆。图表页嵌入与 `plot.png` 字节一致的图片，并非原生可编辑 Excel 图形；数值表可以继续计算。实现参考 [openpyxl 图像接口](https://openpyxl.readthedocs.io/en/stable/images.html)。

逐泳道图保留 ND/NA 的位置。没有确认生物学设计时，不把技术泳道数量当成生物学 n。0.2.1 的推断统计仍为原有两组方法；用户后续提出的 GraphPad 风格与多组统计尚不在此包内。

| 验证 | 结果 |
|---|---|
| Python | 117 tests + 5 subtests 通过 |
| 前端单元 | 49 通过 |
| Rust / doctests | 6 通过（其余 0 用例） |
| 浏览器 + 实际 Python | 21 通过 |
| TypeScript / Vite | 通过 |
| 清空 PATH、独立复制 App 的完整导出 | 通过，11 个审计输出文件 |
| 打包引擎 Excel 重新读取 | 通过；24 原始测量、6 生物学单位；图像媒体与 PNG 一致 |
| 打包泳道夹具 | 净积分 32000 / 8000 = 4；缺失为 null，Excel 空值和状态一致 |
| 实际本地 TIFF 两页 | uint8/uint16 原积分和背景匹配，源文件哈希未改 |
| App 与 ZIP 解压严格签名 | 通过，ad-hoc 签名，未公证 |
| 新版原生窗口与 Microsoft Excel UI | 未验收；未改动正在使用的旧版项目 |

复核无 Critical/Important，指出两个 Minor：小值显示 0、同名图像来源歧义。已以两个失败回归复现并一次修复，无重复复核。完整 Python 回归重新通过。依赖 openpyxl3.1.5 和 et_xmlfile2.0.0 已锁定，许可证纳入打包资源。

阶段性验证脚本曾误将 Worksheet.values 属性写成方法，产品导出本身成功；修正验证脚本，在全新输出目录重跑通过。机器可读证据见 [bundle-verification.json](results-export/bundle-verification.json)、[lane-verification.json](results-export/lane-verification.json)、[package.json](results-export/package.json)。

保留文件：`release/results-export/Titan WB 0.2.1.app`、`release/results-export/Titan-WB-0.2.1-macos-arm64.zip`、`SHA256SUMS.txt`。合成示例 Excel：`artifacts/results-export/lane-verification-final/export/results.xlsx`。用户原始 TIFF 未加入 Git，未推断其真实样本身份或科研准确性。无 push、发布或合并。
