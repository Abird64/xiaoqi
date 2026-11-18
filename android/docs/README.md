# 文档索引

> 小栖步数 Android App · 交付文档

| 文档 | 适合谁 | 内容 |
|---|---|---|
| [../README.md](../README.md) | 所有人 | 30 秒上手、功能、协议对齐、构建/测试命令、限制 |
| [01-设计与实现.md](01-设计与实现.md) | 开发/答辩 | 架构、步数算法、前台服务、同步状态机、安全取舍、扩展点 |
| [02-集成指南.md](02-集成指南.md) | 集成/演示 | 零依赖联调、真实后端接入、防火墙、深链、排障表 |
| [03-测试报告.md](03-测试报告.md) | 验收/报告 | 环境、98 项自动化结果、APK 静态检查、未覆盖风险 |
| [04-真机验收清单.md](04-真机验收清单.md) | 真机测试 | 逐条勾选：权限、计步、锁屏、重启、跨零点、断网恢复 |
| [../release/BUILD-INFO.txt](../release/BUILD-INFO.txt) | 交付 | 本次 APK 的版本、SHA256、证书指纹、工具链 |

## 一分钟版

- **APK**：`release/xiaoqi-steps-1.0.0.apk`（Android 8.0+，targetSdk 34，约 190 KB，调试签名）
- **最短验证**：
  ```powershell
  python tools\dev_server.py --port 8765 --token xiaoqi-demo
  adb install -r release\xiaoqi-steps-1.0.0.apk
  ```
  App 设置填 `http://<电脑IP>:8765` / `xiaoqi-demo`，授予身体活动权限，
  走几步后看 `http://127.0.0.1:8765/`。
- **接真实后端**：地址改 `http://<电脑IP>:8000`，令牌从后端控制台或 `/api/token` 取。
- **构建**：`powershell -File tools\build-apk.ps1`（JDK 17 + SDK 34，无需 Gradle/联网）。
- **测试**：`powershell -File tools\test-all.ps1`（需要参考后端 venv 才能跑真实链路）。

## 已知边界（务必先看）

1. **没有真机运行测试**：本环境无设备/模拟器；算法与协议已测，UI/传感器/厂商后台需真机确认。
2. **首次安装从 0 开始**：不把安装前的“开机以来”步数算进今天。
3. **只做步数**：`screen_minutes` / `top_apps` 未实现（D-009 可选扩展）。
4. **明文 HTTP + 调试签名**：仅课程演示/局域网；正式分发需 HTTPS 与正式证书。
5. **国产 ROM 后台策略**：需允许自启动/后台运行/忽略电池优化，不能保证 100% 存活。
