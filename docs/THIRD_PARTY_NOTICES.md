# 第三方依赖与许可

Titan WB 原创代码采用 MIT 许可证。Python、JavaScript、Rust 依赖和随包提供的库继续遵循各自许可证。

确切版本分别锁定在 `requirements.lock`、`package-lock.json` 与 `src-tauri/Cargo.lock`。发布构建会从已安装依赖中收集版本、声明许可和可用的许可原文，生成 `release/third-party/inventory.json` 及对应文本。该目录随应用资源打包，并作为发布附件归档。

清单包括开发、测试及非活动平台依赖，比实际运行时依赖范围更广，不是精确的运行时 SBOM。清单提供溯源信息，不能把所有第三方内容重新许可为 MIT。

重新收集：

```bash
mkdir -p artifacts
cargo metadata --manifest-path src-tauri/Cargo.toml --format-version 1 > artifacts/cargo-metadata.json
.venv/bin/python scripts/collect_notices.py
```

Windows 使用 `.venv\Scripts\python.exe`。请保留发布包内的 `LICENSE`、`THIRD_PARTY_NOTICES.md` 与 `third-party` 资源。CPython、NumPy、SciPy、Matplotlib、Pillow、React、Tauri 等组件的具体声明和原文以该发布环境生成的附件为准。
