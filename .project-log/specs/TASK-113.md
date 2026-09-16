# TASK-113 移除 APP 类型确认扫码自动缩放

## 1. 背景

APP 类型确认使用 ML Kit 的 `ZoomSuggestionOptions`，识别到二维码后会通过 CameraX `setZoomRatio` 自动放大镜头。现场扫码时镜头反复变化，影响操作人员稳定对准二维码。

## 2. 业务规则

- 类型确认扫码期间镜头倍率不随二维码检测结果自动变化。
- 移除 ML Kit 自动缩放建议和所有 CameraX 自动变焦调用。
- 保留现有实时二维码识别、正式标签校验、自动抓拍上传和无码申请流程。
- 二维码检测提示改为提示用户保持镜头稳定，不出现“自动放大”文案。

## 3. 实施范围

- 删除 `ZoomSuggestionOptions` 的导入、构建和回调。
- 删除自动变焦相关的状态、计数、节流、最大倍率及 `setZoomRatio` 调用。
- 保留 1280x720 分析分辨率和 CameraX 固定相机绑定。

## 4. 验收条件

- 代码中不再存在 `ZoomSuggestionOptions` 或 `setZoomRatio` 调用。
- 类型确认扫码功能仍可构建并保持正式标签解析逻辑。
- Android Kotlin 编译和 Lint 通过。
- Android `1.0.10` APK 构建、v2/v3 签名和 SHA-256 校验通过。

## 5. 验证结果

- Android Kotlin 编译和 Lint 通过。
- 自动缩放相关代码和文案静态检查无残留。
- Android `1.0.10`（`versionCode=11`）签名 APK 已生成。

## 6. 限制

真实平板仍需确认扫码过程中镜头倍率保持不变，并回归二维码识别、无码申请和照片上传。
