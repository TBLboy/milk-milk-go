# TASK-095 Android 证据照片 EXIF 解析安全加固

## 1. 背景

Android Lint 发现平板端仍使用 `android.media.ExifInterface` 读取现场照片方向。该平台实现存在已知安全缺陷，AndroidX 已提供兼容和安全修复更完善的替代实现。

照片方向解析直接参与证据照片归一化，属于扫码、称重和 BUG 反馈共用的图片处理链路。本任务只替换实现，不改变业务行为。

## 2. 范围

- 增加 `androidx.exifinterface:exifinterface` 依赖。
- 将 `MainActivity.kt` 的 `ExifInterface` 导入切换到 AndroidX。
- 保持现有 EXIF 方向枚举和旋转/镜像处理逻辑不变。
- 不修改照片拍摄、压缩、水印、上传或后端存储协议。

## 3. 验收标准

- Android Debug 构建通过。
- Android Lint 不再报告 `android.media.ExifInterface` 安全告警。
- 原有方向归一化代码路径仍通过编译。
- Project Log、差异检查和 Loop 校验通过。

## 4. 非目标

- 不升级其他 AndroidX 依赖。
- 不调整启动图标、横屏策略或 Compose 性能提示。
- 不生成新的正式 APK。
