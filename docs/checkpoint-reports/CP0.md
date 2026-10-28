# CP0：基线与设计准备

日期：2026-10-21。

已确认：原始WB TIFF/PNG、可双击安装的桌面App、macOS优先、每个CP完成后测试。

实际基线检查：

```text
工作目录 wb_research/code
命令 python3 -m unittest discover -v
退出码 0
Ran 21 tests
OK
```

这些检查覆盖参考实现，不包括桌面App。现有工作区没有Git仓库或项目AGENTS.md；尚未安装PySide6、tifffile、SciPy、PyInstaller，也未构建GUI。

当前机器架构核查结果：arm64。

设计与实施计划已起草，CP0的完整通过仍取决于设计核查与用户对完整范围的确认。后续通过时更新本记录及唯一CP状态表，不把本基线等同于产品完成。

独立builder check已完成。3项主要问题已修订到设计和计划：CP9工程验收与CP10真实数据验收分开；跨膜先膜内技术均值再IBC、膜间等权；v1多条带分别作为独立终点，不隐式合计多个ROI。
