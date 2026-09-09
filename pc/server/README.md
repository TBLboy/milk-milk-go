# PC 后端服务

```bash
conda activate milk
python -m pip install -r requirements.txt
python -m pytest
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

默认数据目录为 `pc/server/data/`，可通过 `MILK_DATA_DIR` 指定。当前仅提供工程骨架、SQLite 初始化和 `GET /api/v1/health`。
