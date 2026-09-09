# TASK-004 后端工程骨架规格

## Scope

在 `pc/server` 建立第一版 FastAPI 服务基础，不实现认证、主数据和工单业务。

## Runtime

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.x + SQLite
- pytest + FastAPI TestClient
- 应用数据目录通过环境变量 `MILK_DATA_DIR` 配置；未配置时使用项目运行目录下的 `data/`，但代码不得依赖当前工作目录解析包资源。

## Layout

```text
pc/server/
  app/
    main.py
    core/config.py
    db/session.py
    db/models.py
    api/health.py
  tests/test_health.py
  requirements.txt
```

## API

`GET /api/v1/health` 返回：

```json
{
  "status": "ok",
  "service": "milk-weigh-api",
  "database": "ok",
  "version": "0.1.0"
}
```

数据库不可用时 HTTP 503，返回稳定错误结构，不泄露本机路径。

## Persistence

启动时创建数据目录和 SQLite 文件，开启 SQLite 外键约束；先建立 `schema_meta` 表保存 schema 版本。后续迁移不得覆盖业务数据。

## Verification

- `python -m pytest` 必须通过。
- `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` 能启动。
- TestClient 验证健康接口和数据库文件初始化。
