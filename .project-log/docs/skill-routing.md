# Skill Routing Map

| 情况 | 首选 Skill | 可联动 Skill | 主要落库 |
|---|---|---|---|
| 用户描述模糊、规则不全 | business-clarify | solution-research | atoms/open-questions |
| 准备冻结当前范围 | requirement-baseline | business-clarify | requirements/baseline |
| 不确定用库、框架、SDK还是自研 | solution-research | architecture-decision | research/decision |
| 模块、接口、数据流不清 | architecture-decision | solution-research | architecture/decision |
| 目标太大，不知道先做什么 | task-decompose | requirement-baseline | task-list |
| 实现前仍需猜测技术细节 | engineering-spec | solution-research | specs |
| 正式改代码或配置 | engineering-landing | verification | task/result |
| 需要证明满足需求 | verification | business-code-align | task/atoms evidence |
| 怀疑需求、代码、测试不一致 | business-code-align | business-clarify | alignment/tasks |
| 项目阶段完成 | retrospective | operator-distill | retrospective |
| 想让工作流学习自己 | operator-distill | retrospective | distillation |
| 记录高信号思维-行动-结果链 | work-trace | project-log | work-trace |
| 将批准经验编码为能力 | skill-evolution | operator-distill | evals/proposals |
| 安全更新工作流 | workflow-update | project-log | backups/changelog |
| 快速读论文或准备复现 | paper-reading | solution-research | researches/papers |

## 路由原则

- 主 Agent 只加载当前阶段 Skill。
- 子 Agent 不应拥有无关 Skill 权限。
- 业务澄清只有在技术可行性影响业务选择时调用 solution-research。
- 对齐审计默认只读，修复由主 Agent 另建任务执行。
