# Task List

当前阶段：`task-decomposition`

第一批开发策略：先开发 `pc` 端前端界面和可替换接口适配层，后端真实功能后置；`app` 端暂不进入本批次。

## Implemented, Awaiting Review

### TASK-001 建立 PC 前端工程骨架与可替换接口适配层

- 状态：`implemented-unverified`
- 目标：在 `pc` 文件夹中建立可运行的 React + Vite 浏览器前端，统一页面布局、路由、角色状态、mock 数据和 API adapter 边界。
- 依赖：无
- 完成条件：可启动开发服务器；mock 请求集中在 adapter；管理员和普通操作员导航存在权限差异；后续切换真实 API 不需要修改业务页面调用方式。

## Implemented, Awaiting Review

### TASK-002 实现 PC 工单与辅料称重管理界面原型

- 状态：`implemented-unverified`
- 依赖：`TASK-001`

### TASK-003 实现 PC 主数据、标签、账号和设置界面原型

- 状态：`implemented-unverified`
- 依赖：`TASK-001`

详细任务契约见 [`task-list.yaml`](/home/tbl/Project/辅料称重防错系统/.project-log/tasks/task-list.yaml)。
