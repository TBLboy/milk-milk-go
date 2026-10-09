import pytest
from fastapi.testclient import TestClient
import sys


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MILK_DATA_DIR", str(tmp_path))
    # 授权状态隔离：不写真实注册表 / ProgramData，避免测试互相污染
    monkeypatch.setenv("MILK_LICENSE_STATE_DIR", str(tmp_path / "license-state"))
    monkeypatch.setenv("MILK_LICENSE_DISABLE_REGISTRY", "1")
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.db.session import engine

    engine.dispose()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
