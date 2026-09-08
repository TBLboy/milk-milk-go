# 轻量插件行为

`.opencode/plugins/vibe-workflow.ts` 当前只做两件低风险工作：

1. 在上下文压缩前注入 current-session、workflow、task-list 和开放业务问题；
2. 提供只读工具 `vibe_workflow_status`，供 Agent 快速恢复项目状态。

插件不会自动修改业务逻辑、推进阶段门、执行部署、把任务标记完成或静默更新 Skills。
