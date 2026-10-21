# Titan WB

macOS Tauri桌面WB分析工具。React/TypeScript界面，Python本地计算引擎；原始TIFF/PNG保真定量、可编辑ROI、背景/QC、参考归一化、技术重复与IBC、受限两组统计、可追溯导出。

- [使用说明](docs/USER_GUIDE.md)
- [检查点与真实状态](docs/checkpoints.md)
- [设计](docs/superpowers/specs/2026-10-21-wb-app-design.md)
- [实施计划](docs/superpowers/plans/2026-10-21-wb-app-tauri.md)
- [WB方法资料](wb_research/README.md)

## 开发

Python3.11环境 `.venv`，Node22，Rust及macOS命令行开发工具。

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
npm ci
npm run desktop:dev
```

## 检查与构建

```bash
.venv/bin/python scripts/check_cp.py FINAL
npm run test:e2e
.venv/bin/python packaging/build_engine.py
npm run desktop:build
.venv/bin/python scripts/verify_release.py --app 'src-tauri/target/release/bundle/macos/Titan WB.app' --output artifacts/release-check
```

所有合成示例均标记非实验数据。当前不将合成测试或浏览器测试当作真实WB准确性、完整macOS原生GUI验收的替代。
