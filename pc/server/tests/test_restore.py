import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest


SERVER_DIR = Path(__file__).resolve().parents[1]


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_source_backup(client) -> tuple[Path, str, str, str]:
    headers = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "R1", "name_zh": "恢复测试蔗糖", "shelf_life_months": 24},
    ).json()
    label = client.post(
        "/api/v1/labels/print-batches",
        headers=headers,
        json={"material_id": material["material_id"], "quantity": 1},
    ).json()["labels"][0]
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={"name": "恢复测试产品", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]},
    ).json()
    order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()

    qr_file = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("qr.jpg", b"restore-qr-evidence", "image/jpeg")},
    ).json()["file_id"]
    qr = client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
        headers=headers,
        json={"label_id": label, "material_id": material["material_id"], "evidence_file_id": qr_file},
    )
    assert qr.status_code == 200

    scale_file = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("scale.jpg", b"restore-scale-evidence", "image/jpeg")},
    ).json()["file_id"]
    weight = client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/weight",
        headers=headers,
        json={"weight_kg": 10, "scale_photo_file_id": scale_file},
    )
    assert weight.status_code == 200

    backup_response = client.post("/api/v1/operations/backups", headers=headers)
    assert backup_response.status_code == 200
    backup = client.get("/api/v1/operations/backups", headers=headers).json()[0]
    return Path(backup["file_path"]), order["order_no"], qr_file, scale_file


def create_current_target_state(data_dir: Path) -> None:
    data_dir.mkdir(parents=True)
    database = data_dir / "milk_weigh.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE system_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO system_settings VALUES ('marker', 'current-state')")
        connection.commit()


def target_marker(data_dir: Path) -> str:
    with sqlite3.connect(data_dir / "milk_weigh.sqlite3") as connection:
        return connection.execute("SELECT value FROM system_settings WHERE key = 'marker'").fetchone()[0]


def test_restore_into_clean_environment_and_open_history(client, tmp_path):
    archive, order_no, qr_file, scale_file = create_source_backup(client)
    target_data = tmp_path / "Clean Restore Data"
    create_current_target_state(target_data)

    restore_environment = os.environ.copy()
    restore_environment["MILK_DATA_DIR"] = str(target_data)
    restore_environment["PYTHONPATH"] = str(SERVER_DIR)
    restored = subprocess.run(
        [sys.executable, str(SERVER_DIR / "restore_backup.py"), "--backup", str(archive), "--yes"],
        cwd=SERVER_DIR,
        env=restore_environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert restored.returncode == 0, restored.stderr
    result = json.loads(restored.stdout)

    pre_restore_backup = Path(result["pre_restore_backup"])
    assert pre_restore_backup.is_file()
    with ZipFile(pre_restore_backup) as pre_restore:
        manifest = json.loads(pre_restore.read("manifest.json"))
        assert manifest["trigger"] == "pre_restore"

    target_db = target_data / "milk_weigh.sqlite3"
    with sqlite3.connect(target_db) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute(
            "SELECT COUNT(*) FROM work_orders WHERE order_no = ?", (order_no,)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM type_confirmations WHERE evidence_file_id = ?", (qr_file,)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM weighing_attempts WHERE scale_photo_file_id = ?", (scale_file,)
        ).fetchone()[0] == 1
        restored_audit = connection.execute(
            "SELECT action, result FROM audit_logs WHERE action = 'system.restored' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert restored_audit == ("system.restored", "success")
        stored_paths = [
            row[0]
            for row in connection.execute(
                "SELECT stored_path FROM evidence_files WHERE file_id IN (?, ?)", (qr_file, scale_file)
            )
        ]
    assert len(stored_paths) == 2
    assert all(Path(path).is_file() for path in stored_paths)
    assert all(Path(path).is_relative_to(target_data / "uploads") for path in stored_paths)

    script = """
import sys
from fastapi.testclient import TestClient
from app.main import app

order_no, qr_file, scale_file = sys.argv[1:4]
with TestClient(app) as client:
    login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    order = client.get("/api/v1/work-orders/" + order_no, headers=headers)
    assert order.status_code == 200, order.text
    body = order.json()
    assert body["steps"][0]["confirmations"][0]["evidence_file_id"] == qr_file
    assert body["steps"][0]["weighing_attempts"][0]["scale_photo_file_id"] == scale_file
    assert client.get("/api/v1/evidence/files/" + qr_file, headers=headers).content == b"restore-qr-evidence"
    assert client.get("/api/v1/evidence/files/" + scale_file, headers=headers).content == b"restore-scale-evidence"
print("RESTORE_APP_OK")
"""
    environment = restore_environment
    completed = subprocess.run(
        [sys.executable, "-c", script, order_no, qr_file, scale_file],
        cwd=SERVER_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "RESTORE_APP_OK" in completed.stdout


def test_restore_rejects_corrupted_archive(client, tmp_path):
    from app.core.config import Settings
    from app.services.restore import RestoreError, restore_complete_backup

    archive, _, _, _ = create_source_backup(client)
    corrupt_dir = tmp_path / "corrupt"
    corrupt_dir.mkdir()
    corrupt_archive = corrupt_dir / archive.name
    shutil.copy2(archive, corrupt_archive)
    shutil.copy2(archive.with_suffix(".zip.sha256"), corrupt_archive.with_suffix(".zip.sha256"))
    with corrupt_archive.open("ab") as stream:
        stream.write(b"corruption")

    target_data = tmp_path / "target"
    create_current_target_state(target_data)
    with pytest.raises(RestoreError, match="SHA-256"):
        restore_complete_backup(corrupt_archive, Settings(data_dir=target_data))
    assert target_marker(target_data) == "current-state"


def test_restore_rejects_evidence_hash_mismatch(client, tmp_path):
    from app.core.config import Settings
    from app.services.restore import RestoreError, restore_complete_backup

    archive, _, _, _ = create_source_backup(client)
    tampered_dir = tmp_path / "tampered-evidence"
    tampered_dir.mkdir()
    tampered_archive = tampered_dir / archive.name
    with ZipFile(archive) as source, ZipFile(tampered_archive, "w") as target:
        manifest = json.loads(source.read("manifest.json"))
        tampered_once = False
        entries = {}
        for info in source.infolist():
            payload = source.read(info)
            if not tampered_once and info.filename.startswith("uploads/"):
                payload = b"X" + payload[1:]
                component = next(item for item in manifest["components"] if item["path"] == info.filename)
                component["size_bytes"] = len(payload)
                component["sha256"] = hashlib.sha256(payload).hexdigest()
                tampered_once = True
            entries[info] = payload
        for info, payload in entries.items():
            if info.filename == "manifest.json":
                payload = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            target.writestr(info, payload)
    checksum = hashlib.sha256(tampered_archive.read_bytes()).hexdigest()
    tampered_archive.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {tampered_archive.name}\n",
        encoding="ascii",
    )

    target_data = tmp_path / "hash-mismatch-target"
    create_current_target_state(target_data)
    with pytest.raises(RestoreError, match="哈希不一致"):
        restore_complete_backup(tampered_archive, Settings(data_dir=target_data))
    assert target_marker(target_data) == "current-state"


def test_restore_rejects_incomplete_archive(client, tmp_path):
    from app.core.config import Settings
    from app.services.restore import RestoreError, restore_complete_backup

    archive, _, _, _ = create_source_backup(client)
    incomplete_dir = tmp_path / "incomplete"
    incomplete_dir.mkdir()
    incomplete_archive = incomplete_dir / archive.name
    with ZipFile(archive) as source, ZipFile(incomplete_archive, "w") as target:
        for info in source.infolist():
            if info.filename.startswith("uploads/"):
                continue
            target.writestr(info, source.read(info))
    checksum = hashlib.sha256(incomplete_archive.read_bytes()).hexdigest()
    incomplete_archive.with_suffix(".zip.sha256").write_text(
        f"{checksum}  {incomplete_archive.name}\n",
        encoding="ascii",
    )

    target_data = tmp_path / "incomplete-target"
    create_current_target_state(target_data)
    with pytest.raises(RestoreError, match="文件清单不一致"):
        restore_complete_backup(incomplete_archive, Settings(data_dir=target_data))
    assert target_marker(target_data) == "current-state"


def test_restore_failure_rolls_back_current_state(client, tmp_path, monkeypatch):
    from app.core.config import Settings
    from app.services import restore as restore_service

    archive, _, _, _ = create_source_backup(client)
    target_data = tmp_path / "rollback-target"
    create_current_target_state(target_data)
    real_validate = restore_service._validate_database
    calls = 0

    def fail_after_install(database_path, uploads_dir, target_data_dir):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise restore_service.RestoreError("simulated post-restore validation failure")
        return real_validate(database_path, uploads_dir, target_data_dir)

    monkeypatch.setattr(restore_service, "_validate_database", fail_after_install)
    with pytest.raises(restore_service.RestoreError, match="post-restore"):
        restore_service.restore_complete_backup(archive, Settings(data_dir=target_data))

    assert target_marker(target_data) == "current-state"
    assert not (target_data / ".restore-journal.json").exists()


def test_interrupted_restore_journal_restores_original_on_startup(tmp_path):
    from app.services.restore import JOURNAL_NAME, recover_interrupted_restore

    data_dir = tmp_path / "journal-data"
    create_current_target_state(data_dir)
    rollback_dir = data_dir / ".restore-rollback-test"
    rollback_dir.mkdir()
    rollback_database = rollback_dir / "database"
    with sqlite3.connect(rollback_database) as connection:
        connection.execute("CREATE TABLE system_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO system_settings VALUES ('marker', 'original-state')")
        connection.commit()
    (data_dir / JOURNAL_NAME).write_text(
        json.dumps(
            {
                "rollback_dir": rollback_dir.name,
                "targets": {
                    "database": "milk_weigh.sqlite3",
                    "uploads": "uploads",
                    "token_secret": "token_secret",
                },
                "managed": {
                    "database": True,
                    "uploads": False,
                    "token_secret": False,
                },
                "had_original": {
                    "database": True,
                    "uploads": False,
                    "token_secret": False,
                },
            }
        ),
        encoding="utf-8",
    )

    assert recover_interrupted_restore(data_dir) is True
    assert target_marker(data_dir) == "original-state"
    assert not (data_dir / JOURNAL_NAME).exists()
