# PC 后端服务

开发环境搭建与复现步骤见仓库内 [`docs/dev-environment.md`](../../docs/dev-environment.md)。

```powershell
# 在仓库根目录创建环境（uv，无需 conda）
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -r pc\server\requirements.lock

# 初始化演示数据
cd pc\server
..\..\.venv\Scripts\python.exe seed.py

# 运行（端口固定 8011，与前端代理/Android/安装包一致）
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload

# 测试
..\..\.venv\Scripts\python.exe -m pytest
```

默认数据目录为 `pc/data/`（由 `app/core/config.py` 的 `PROJECT_ROOT` 决定），可通过环境变量 `MILK_DATA_DIR` 覆盖。

## 数据库连接池

同步端点在 anyio 线程池（默认 40 线程）中执行。SQLAlchemy 对 SQLite 的默认连接池为
`pool_size=5` + `max_overflow=10`（共 15 个连接），并发超过该值时请求会在连接池排队，
持续过载会在 `pool_timeout`（30s）后抛 `sqlalchemy.exc.TimeoutError` 并返回 500。

默认已调整为与线程池匹配的容量，可用环境变量覆盖：

```env
MILK_DB_POOL_SIZE=20
MILK_DB_MAX_OVERFLOW=20
MILK_DB_POOL_TIMEOUT=30
```

## BUG 反馈邮件

BUG 反馈固定发送到 `1218740205@qq.com`。发件账号需要在 `pc/server/.env` 中配置，授权码不会提交到 Git：

```env
MILK_SMTP_USERNAME=你的发件QQ邮箱
MILK_SMTP_PASSWORD=QQ邮箱SMTP授权码
```

QQ 邮箱请使用“设置 -> 账号 -> POP3/SMTP服务”生成的 SMTP 授权码，不要填写邮箱登录密码。
