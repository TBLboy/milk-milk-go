# PC 后端服务

```bash
conda activate milk
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

默认数据目录为 `pc/server/data/`，可通过 `MILK_DATA_DIR` 指定。当前仅提供工程骨架、SQLite 初始化和 `GET /api/v1/health`。

## BUG 反馈邮件

BUG 反馈固定发送到 `1218740205@qq.com`。发件账号需要在 `pc/server/.env` 中配置，授权码不会提交到 Git：

```env
MILK_SMTP_USERNAME=你的发件QQ邮箱
MILK_SMTP_PASSWORD=QQ邮箱SMTP授权码
```

QQ 邮箱请使用“设置 -> 账号 -> POP3/SMTP服务”生成的 SMTP 授权码，不要填写邮箱登录密码。
