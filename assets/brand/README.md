# Titan 品牌资产

- `titan-fist-master.png`：用户确认的平滑曲线单拳原图，1254 × 1254，白底深蓝，通过内置 image_gen 生成并确认。此文件是正式导出的原始素材。
- `../icon.svg`：应用图标容器母版，保留上述位图原形，圆角外部透明。SVG 内嵌的是 PNG，不是描摹的矢量拳头。
- `../icon.png`：1024 × 1024 桌面图标母版。
- `titan-app-icon-128.png`、`titan-favicon-32.png`：分别供工作台与网页图标使用的小尺寸导出，避免运行时加载高分辨率母版。
- `titan-head.svg`：用户选择用于加载状态的抽象猩猩头，源自 `titan-v4` 的路径，使用界面蓝色。

运行 `npm run brand:icons` 可从已确认的母版重新生成 `assets/icon.svg`、`assets/icon.png` 和 `src-tauri/icons/` 下的平台图标。脚本使用项目现有 Playwright 与 Tauri CLI，不会重新生成或改变拳头画稿。

应用在导入、复核、识别、定量等现有忙碌状态显示猩猩头，并使用轻微呼吸动画。动画随处理状态结束而消失，保留原有状态文字与取消等待操作，尊重系统减少动态效果设置。
