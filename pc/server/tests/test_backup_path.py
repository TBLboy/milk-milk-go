"""TASK-128: 备份路径可配置。"""
import json
from pathlib import Path
from zipfile import ZipFile

from app.core.config import Settings
from app.services.backup import resolve_backup_dir, validate_backup_path


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_validate_backup_path_rejects_network_paths():
    assert validate_backup_path("") is None
    assert validate_backup_path("/data/backups") is None
    assert validate_backup_path("D:\\Backups") is None
    assert validate_backup_path("\\\\server\\share") is not None
    assert validate_backup_path("//server/share") is not None


def test_resolve_backup_dir_prefers_config_file(tmp_path):
    settings = Settings(data_dir=tmp_path, app_version="test")
    custom = tmp_path / "custom-backups"
    custom.mkdir()
    (tmp_path / "backup_path.conf").write_text(str(custom) + "\n", encoding="utf-8")

    resolved = resolve_backup_dir(settings, {"backup_path": str(tmp_path / "other")})
    assert resolved == custom


def test_resolve_backup_dir_falls_back_to_data_dir(tmp_path):
    settings = Settings(data_dir=tmp_path, app_version="test")
    assert resolve_backup_dir(settings, {}) == tmp_path / "backups"
    assert resolve_backup_dir(settings, None) == tmp_path / "backups"


def test_settings_reject_network_backup_path(client):
    headers = admin_headers(client)
    response = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"values": {"backup_path": "\\\\server\\share"}},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "BACKUP_PATH_INVALID"


def test_backup_writes_to_configured_path(client, tmp_path):
    headers = admin_headers(client)
    custom = tmp_path / "custom-backups"
    custom.mkdir()
    response = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"values": {"backup_path": str(custom)}},
    )
    assert response.status_code == 200

    assert client.post("/api/v1/operations/backups", headers=headers).status_code == 200
    archives = list(custom.glob("milk-weigh-backup-*.zip"))
    assert len(archives) == 1
    assert (tmp_path / "backup_path.conf").read_text(encoding="utf-8").strip() == str(custom)

    with ZipFile(archives[0]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["trigger"] == "manual"
