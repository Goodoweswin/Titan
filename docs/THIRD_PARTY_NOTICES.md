# 依赖与许可记录

Titan WB 0.1 的确切依赖版本保存在 requirements.lock、package-lock.json、src-tauri/Cargo.lock。本地构建工具版本与环境见 CP 报告。

运行 `.venv/bin/python scripts/collect_notices.py`，根据当前已安装 Python/npm 元数据与 Cargo metadata 收集版本、声明许可和可用许可原文，生成 release/third-party/inventory.json 及分类文本文件。当前清单包含开发、测试和其他平台依赖，比实际 App 中使用的范围更广；不等同于精确运行时 SBOM。

该目录随本地交付保留。公开发布前仍需确认实际分发组件、第三方许可与 Apple 签名公证条件。
