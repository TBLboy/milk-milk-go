# TASK-119 构建最新版 Windows 安装包和 Android APK

## 1. 背景

电脑端已完成可搜索动态下拉框等最新改动，Android 端最新版本为 `1.0.14`。需要冻结当前工作区源码，生成可供安装测试的 Windows EXE 和 Android APK，并校验产物。

## 2. 业务规则

- Windows 安装包使用新版本号，不覆盖已有 `1.0.5` 产物。
- Android 使用当前 `versionCode = 15`、`versionName = 1.0.14`。
- Android 安装包必须使用正式发布签名并通过签名校验。
- Windows 安装包必须包含当前 PC 前端、后端代码、演示数据资源、Python 运行时和配置。
- 发布产物统一输出到 `发布版本/`。
- 不推送 Git。

## 3. 实施范围

- 将 PC 版本提升到 `1.0.6`。
- 重建 PC 前端生产产物。
- 构建 `牧衡辅料称重防错系统-Windows-1.0.6-Setup.exe`。
- 构建 `牧衡辅料称重防错系统-Android-1.0.14.apk`。
- 校验文件类型、Android 清单版本、签名和 SHA-256。

## 4. 验收条件

- Windows EXE 存在、文件格式有效且哈希文件与真实文件一致。
- Android APK 存在、清单版本为 `1.0.14`，签名验证通过且哈希文件一致。
- 构建结束后无因版本注入导致的打包错误。
- `git diff --check` 通过。

## 5. 验证结果

- Windows `1.0.6` 安装器构建成功，输出为有效的 PE32 Windows GUI 可执行文件。
- Windows 产物：`发布版本/牧衡辅料称重防错系统-Windows-1.0.6-Setup.exe`，大小 `31,051,725` 字节。
- Windows SHA-256：`ee42405a7db666a1219d243958b0e03d8ff73d124f4e769e78330fe633620df0`。
- Android Release APK 构建成功，`versionCode=15`、`versionName=1.0.14`，v2/v3 签名验证通过。
- Android 产物：`发布版本/牧衡辅料称重防错系统-Android-1.0.14.apk`，大小约 `35 MB`。
- Android SHA-256：`7a1f665b8be93edbf06abc7631d889b99e74da7f1ecdb300034c6ea38b9086a1`。
- 两个 `.sha256` 文件与实体产物重新计算的哈希一致。
- Windows staged payload 中的 `index.html` 和构建资源与当前 `pc/dist` 一致。
- `git diff --check` 通过。
- 证据：`EV-TASK-119-WINDOWS`、`EV-TASK-119-ANDROID`、`EV-TASK-119-VERIFY`、`EV-TASK-119-DIFF`。

## 6. 限制

- 本轮只完成构建产物校验，不在真实 Windows 11 客户机和 Android 平板执行安装验收。
- 真实标签打印机不在本轮范围内。
