# WB 分析与 App 研发资料包

本资料将 WB 理解为 Western blot。整理日期：2026-10-21。

用户已确认首要输入为原始 WB 图像（TIFF/PNG）。参考实现优先支持单平面灰度图；彩色通道、多页及仪器专有格式需要显式适配。

建议阅读顺序：

1. [详细protocol与研发建议](WB分析流程与研发资料.md)：图像、背景、归一化、统计、QC、数据结构与验证。
2. [一手资料、开源项目与代码使用](代码与开源资源.md)：论文/文档/源码链接、使用方式与限制。
3. [Python参考实现](code/wb_reference.py)：可运行定量核心和局部候选检测。
4. [检查用例](code/test_wb_reference.py)与[合成示例生成器](code/make_demo.py)。

已附的演示：

- `demo/SYNTHETIC_ONLY.tif`：纯合成16位输入，非实验数据。
- `demo/SYNTHETIC_review_overlay.png`：目标、参考与饱和ROI示意。
- `demo/config.json`：样本与ROI配置。
- `demo/unreviewed_proposals.json`：待审核候选，未参与正式测量。
- `demo/results/`：三张CSV表与审计JSON。

运行检查：

```bash
cd wb_research/code
python3 -m unittest discover -v
```

代码仅依赖NumPy、Pillow。外部开源项目没有在本机安装；本次交付是资料与参考代码，尚未开始构建完整App，也未在用户的真实WB数据上验证。
