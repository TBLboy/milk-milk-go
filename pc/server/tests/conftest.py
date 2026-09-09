import pytest
from fastapi.testclient import TestClient
import sys


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MILK_DATA_DIR", str(tmp_path))
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
