import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from app.core.config import Settings
from app.services.backup import create_complete_backup


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_complete_backup_contains_database_evidence_config_and_checksums(client):
    headers = admin_headers(client)
    client.get("/api/v1/health")
    upload = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("evidence.jpg", b"production-evidence", "image/jpeg")},
    )
    assert upload.status_code == 201

    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["trigger"] == "manual"
    assert len(response.json()["checksum_sha256"]) == 64

    backup = client.get("/api/v1/operations/backups", headers=headers).json()[0]
    assert backup["status"] == "success"
    assert backup["trigger"] == "manual"
    archive_path = Path(backup["file_path"])
    assert archive_path.is_file()
    assert archive_path.suffix == ".zip"

    checksum_path = archive_path.with_suffix(".zip.sha256")
    checksum, checksum_name = checksum_path.read_text(encoding="ascii").strip().split("  ", 1)
    assert checksum == backup["checksum_sha256"]
    assert checksum_name == archive_path.name
    assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == checksum

    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert "database/milk_weigh.sqlite3" in names
        assert "config/runtime.json" in names
        assert "manifest.json" in names
        upload_names = [name for name in names if name.startswith("uploads/")]
        assert len(upload_names) == 1
        assert archive.read(upload_names[0]) == b"production-evidence"

        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["format_version"] == 1
        assert manifest["trigger"] == "manual"
        assert manifest["app_version"] == "0.1.0"
        for component in manifest["components"]:
            payload = archive.read(component["path"])
            assert len(payload) == component["size_bytes"]
            assert hashlib.sha256(payload).hexdigest() == component["sha256"]


def test_backup_failure_is_recorded(client, monkeypatch):
    from app.api import operations as operations_api
    from app.services.backup import BackupError

    headers = admin_headers(client)
    monkeypatch.setattr(
        operations_api,
        "create_complete_backup",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(BackupError("simulated failure")),
    )

    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 503
    records = client.get("/api/v1/operations/backups", headers=headers).json()
    assert records[0]["status"] == "failed"
    assert records[0]["trigger"] == "manual"
    assert "simulated failure" in records[0]["error_message"]


def test_scheduled_backup_due_rules():
    from app.services.backup import is_backup_due

    scheduled = datetime(2026, 9, 13, 2, 0)
    assert is_backup_due(
        enabled=True,
        backup_time="02:00",
        now=scheduled,
        schedule_key=None,
    )
    assert not is_backup_due(
        enabled=True,
        backup_time="02:00",
        now=scheduled,
        schedule_key="2026-09-13",
    )
    assert not is_backup_due(
        enabled=True,
        backup_time="03:00",
        now=scheduled,
        schedule_key=None,
    )
    assert not is_backup_due(
        enabled=False,
        backup_time="02:00",
        now=scheduled,
        schedule_key=None,
    )
    assert not is_backup_due(
        enabled=True,
        backup_time="invalid",
        now=scheduled,
        schedule_key=None,
    )


def test_scheduler_runs_once_for_due_schedule(client, monkeypatch):
    from app.services import backup as backup_service

    headers = admin_headers(client)
    expected = backup_service.BackupResult(
        file_path=Path("scheduled-backup.zip"),
        file_name="scheduled-backup.zip",
        size_bytes=123,
        checksum_sha256="a" * 64,
        created_at=datetime(2026, 9, 13, 2, 0),
        trigger="scheduled",
    )
    monkeypatch.setattr(
        backup_service,
        "create_complete_backup",
        lambda *_args, **_kwargs: expected,
    )

    assert backup_service.backup_scheduler.run_once(now=datetime(2026, 9, 13, 2, 0)) is True
    assert backup_service.backup_scheduler.run_once(now=datetime(2026, 9, 13, 2, 1)) is False

    records = client.get("/api/v1/operations/backups", headers=headers).json()
    assert records[0]["trigger"] == "scheduled"
    assert records[0]["schedule_key"] == "2026-09-13"
    assert records[0]["checksum_sha256"] == "a" * 64


def test_complete_backup_supports_service_style_data_path(tmp_path):
    data_dir = tmp_path / "Milk Weigh Service Data"
    data_dir.mkdir()
    database = data_dir / "milk_weigh.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO marker VALUES ('ok')")
        connection.commit()
    upload_dir = data_dir / "uploads" / "FILE-12345678"
    upload_dir.mkdir(parents=True)
    (upload_dir / "evidence.jpg").write_bytes(b"service-path-evidence")

    result = create_complete_backup(
        Settings(data_dir=data_dir, app_version="test-version"),
        trigger="scheduled",
        system_settings={"backup_time": "02:00"},
    )

    assert result.file_path.is_file()
    with ZipFile(result.file_path) as archive:
        assert archive.read("database/milk_weigh.sqlite3").startswith(b"SQLite format 3")
        assert archive.read("uploads/FILE-12345678/evidence.jpg") == b"service-path-evidence"
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["app_version"] == "test-version"
        assert manifest["trigger"] == "scheduled"
