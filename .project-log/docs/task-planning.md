# Task Planning Rules

## 任务层级

- `goal`：业务结果；
- `milestone`：可以独立展示的阶段结果；
- `task`：可独立验收的生产工作；
- `spike`：降低不确定性的限时试验；
- `repair`：修复缺陷或对齐问题；
- `research`：形成可决策的证据。

## Ready 条件

任务进入 `ready` 前应满足：

- 依赖完成；
- 阻塞问题解决；
- 需要的业务和架构信息足够；
- C 级决定已确认；
- done_when 和验证策略明确。

## Done 条件

`done` 必须同时满足：

- 输出已产生；
- done_when 全部满足；
- verification 为 passed 或明确 not-applicable；
- 偏离已记录；
- 业务原子和测试引用已更新；
- 无隐藏 critical alignment finding。
