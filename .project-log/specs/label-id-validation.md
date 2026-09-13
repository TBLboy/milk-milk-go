# TASK-071 标签 labelId 校验工程说明

## Scope

将平板的二维码类型确认从“只提交 materialId”改为“同时提交 materialId 和 labelId”，并让后端验证标签确由本系统生成、状态有效且与工单步骤辅料一致。

本任务不实现真实打印机、标签作废页面和贴标后的二次复核。

## Data Contract

自制二维码 payload 继续使用现有字段：

```json
{
  "v": 1,
  "labelId": "LBL-20260913-...",
  "materialId": "MAT-00001",
  "materialCode": "A1",
  "name": "蔗糖",
  "printedAt": "2026-09-13T..."
}
```

类型确认请求新增必填字段：

```json
{
  "label_id": "LBL-20260913-...",
  "material_id": "MAT-00001",
  "evidence_file_id": "FILE-..."
}
```

## Persistence

`type_confirmations` 增加可空字段 `scanned_label_id`，用于保存每次扫码尝试收到的标签编号，包括失败尝试。迁移必须兼容已有数据库，旧记录该字段为空。

不得将标签编号写入照片文件或覆盖二维码 payload；标签记录本身仍是标签状态的权威来源。

## Backend Validation

扫码确认按以下顺序校验：

1. 当前用户可操作当前工单步骤。
2. 步骤状态仍为 `pending` 或 `type_confirmation`。
3. 照片证据存在且属于当前用户。
4. `labelId` 对应 `labels` 表记录存在。
5. 标签状态为 `active`。
6. 标签记录的 `material_id` 与请求的 `material_id` 一致。
7. 请求的 `material_id` 与工单步骤快照一致。

任何失败尝试都保存 `TypeConfirmation(status=rejected)`，但不得把步骤推进到 `weighing`。

稳定错误码：

- `LABEL_NOT_FOUND`：标签不存在。
- `LABEL_NOT_ACTIVE`：标签不是 active。
- `LABEL_MATERIAL_MISMATCH`：labelId 与 materialId 不匹配。
- `MATERIAL_MISMATCH`：辅料与当前工单步骤不匹配。

## Android Client

1. 从同一张现场拍摄照片解析二维码 JSON。
2. 只有同时解析出非空 `labelId` 和 `materialId` 时，才允许点击“确认类型”。
3. 任一项缺失时按无法识别二维码处理，允许填写原因提交照片审批。
4. 请求体同时提交 `label_id`、`material_id` 和 `evidence_file_id`。
5. 工单详情中的类型确认记录展示或保留 `scanned_label_id` 供追溯。

## Verification

后端测试至少覆盖：

- 合法 active 标签通过并写入 `scanned_label_id`。
- 不存在的 labelId 被拒绝且步骤不推进。
- 已作废标签被拒绝且步骤不推进。
- labelId 与 materialId 不一致被拒绝。
- 合法 labelId 但辅料与工单步骤不一致被拒绝。
- 缺失 labelId 的请求返回 422。

客户端验证至少包括：

- 同时识别出两个字段后允许提交。
- 只识别出一个字段时不走扫码通过路径。
- Android debug 构建通过。
