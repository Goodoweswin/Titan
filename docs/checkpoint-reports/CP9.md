# CP9：macOS 安装包工程验收

2026-10-21，Titan WB 0.1.0 内部试用版；macOS 14+、Apple Silicon。尚未完成完整原生安装/窗口验收，不将本 CP 标成通过。

## 构建

- `.venv/bin/python packaging/build_engine.py`：退出 0，内置 Python 运行时和科学计算依赖。
- `npm run desktop:build`：退出 0，生成约 54.76 MiB 的 .app 和 47.72 MiB 的 .dmg。
- `hdiutil verify`：退出 0，最终 DMG 的 CRC 校验有效。
- 原件位于 src-tauri/target/release/bundle/，稳定交付副本位于 release/。既有 /Applications/Titan WB.app 未被覆盖。
- 精确构建日志在 artifacts/checkpoints/final-engine-build.log、final-release-build.log、final-dmg-verify.log。

## 源码与浏览器验证

最终 `.venv/bin/python scripts/check_cp.py FINAL`：Python 62 项（含原参考 21 项）、前端 11 项、Rust 2 项以及生产前端构建均通过；四层退出码 0。`npm run test:e2e`：3 项通过，使用真实 Python 引擎。

## 独立包引擎验证

脚本 scripts/verify_release.py 将完整 App 复制到临时目录，工作目录离开源码，PATH 仅 /usr/bin:/bin，不设置 PYTHONPATH，再直接调用 App 内的 wb-engine。依次验证 health、手算净积分 80、合成示例、定量 24/12/1/6、中文路径保存与重开、CSV/JSON/PNG/SVG/原图/叠加导出、所有输出 hash、释放锁；最后记录本地代码签名完整性检查。最终重跑退出码 0：24 测量/12 目标/1 阻止/6 生物学单位，保存重开通过，10 个导出文件 hash 全部一致，严格签名完整性检查退出 0。最终机器报告保存为 docs/checkpoint-reports/release-verification.json，交付目录另附副本。

首次独立包测试发现动态 SVG 模块未收录；已显式加入打包，重建后运行相同流程。详细原因见 review.md。

该检查没有调用系统开发 Python，但并未卸载本机 Python，也没有关闭本机网络；只能证明此路径无需开发解释器、运行流程未依赖网络下载。原生窗口与 Tauri IPC 尚未被此脚本验证。

## 待验收与分发边界

电脑操作工具多次返回 `Computer Use was not approved to use Titan WB`，用户允许意愿尚未使工具权限生效。没有绕过限制执行 GUI。Finder 双击、安装、原生文件对话框、原生编辑/自动保存/退出提示/恢复需要按 docs/NATIVE_ACCEPTANCE.md 完成。

内部包使用 ad-hoc 本地签名，hardenedRuntime=false：Tauri 默认 hardened runtime 会拒绝无共同开发者 Team ID 的 PyInstaller 解包运行库；未修改系统安全设置。对外签名公证须另行配置证书与运行库。

包可作本机内部试用；没有 Apple 开发者身份签名与公证，不能据本地 codesign 完整性通过宣称公开分发就绪。依赖版本锁和许可清单见 docs/THIRD_PARTY_NOTICES.md 与 release/third-party/。真实 WB 定量有效性另按 CP10 验收。
