"""TASK-129: 备份按年限过滤业务数据并保留数量清理。"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

from app.core.config import Settings
from app.services.backup import create_complete_backup, parse_keep_count, parse_retention_years


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_product(client, headers):
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 12.5}]}).json()
    return product["id"]


def _age_work_order(data_dir: Path, order_no: str, days: int) -> None:
    database = data_dir / "milk_weigh.sqlite3"
    stamp = (datetime.now().astimezone() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE work_orders SET created_at = ? WHERE order_no = ?", (stamp, order_no))
        connection.commit()


def _work_order_count(database_path: Path) -> int:
    with sqlite3.connect(database_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]


def test_retention_parsers():
    assert parse_retention_years(None) == 12
    assert parse_retention_years("12") == 12
    assert parse_retention_years("0") == 0
    assert parse_retention_years("120") == 120
    assert parse_retention_years("-1") is None
    assert parse_retention_years("abc") is None

    assert parse_keep_count(None) == 60
    assert parse_keep_count("10") == 10
    assert parse_keep_count("365") == 365
    assert parse_keep_count("9") is None
    assert parse_keep_count("366") is None
    assert parse_keep_count("abc") is None


def test_backup_filters_expired_work_orders_and_keeps_master_data(client, tmp_path):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    fresh = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 2000}).json()
    stale = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1000}).json()
    _age_work_order(tmp_path, stale["order_no"], days=400)

    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 200

    backup = client.get("/api/v1/operations/backups", headers=headers).json()[0]
    with ZipFile(Path(backup["file_path"])) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["retention"]["expired_work_orders"] == 1
        archive.extract("database/milk_weigh.sqlite3", tmp_path / "extracted")

    snapshot = tmp_path / "extracted" / "database" / "milk_weigh.sqlite3"
    with sqlite3.connect(snapshot) as connection:
        order_nos = {row[0] for row in connection.execute("SELECT order_no FROM work_orders").fetchall()}
        assert fresh["order_no"] in order_nos
        assert stale["order_no"] not in order_nos
        assert connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 1


def test_backup_permanent_retention_keeps_all_work_orders(client, tmp_path):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    stale = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1000}).json()
    _age_work_order(tmp_path, stale["order_no"], days=400)
    client.put("/api/v1/settings", headers=headers, json={"values": {"backup_retention_years": "0"}})

    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 200

    backup = client.get("/api/v1/operations/backups", headers=headers).json()[0]
    with ZipFile(Path(backup["file_path"])) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["retention"] is None
        archive.extract("database/milk_weigh.sqlite3", tmp_path / "extracted")

    snapshot = tmp_path / "extracted" / "database" / "milk_weigh.sqlite3"
    with sqlite3.connect(snapshot) as connection:
        order_nos = {row[0] for row in connection.execute("SELECT order_no FROM work_orders").fetchall()}
        assert stale["order_no"] in order_nos


def test_backup_prunes_oldest_archives_beyond_keep_count(client, tmp_path):
    headers = admin_headers(client)
    client.put("/api/v1/settings", headers=headers, json={"values": {"backup_keep_count": "10"}})

    for _ in range(12):
        assert client.post("/api/v1/operations/backups", headers=headers).status_code == 200

    backup_dir = tmp_path / "backups"
    archives = sorted(backup_dir.glob("milk-weigh-backup-*.zip"))
    assert len(archives) == 10
    sidecars = sorted(backup_dir.glob("milk-weigh-backup-*.zip.sha256"))
    assert len(sidecars) == 10


def test_settings_reject_invalid_retention_and_keep_count(client):
    headers = admin_headers(client)
    bad_retention = client.put("/api/v1/settings", headers=headers, json={"values": {"backup_retention_years": "121"}})
    assert bad_retention.status_code == 422
    bad_count = client.put("/api/v1/settings", headers=headers, json={"values": {"backup_keep_count": "5"}})
    assert bad_count.status_code == 422
    ok = client.put("/api/v1/settings", headers=headers, json={"values": {"backup_retention_years": "24", "backup_keep_count": "30"}})
    assert ok.status_code == 200
    assert ok.json()["backup_retention_years"] == "24"
    assert ok.json()["backup_keep_count"] == "30"


def test_pre_restore_backup_is_not_filtered(client, tmp_path):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    stale = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1000}).json()
    _age_work_order(tmp_path, stale["order_no"], days=400)

    result = create_complete_backup(
        Settings(data_dir=tmp_path, app_version="test-version"),
        trigger="pre_restore",
        system_settings={"backup_retention_years": "12"},
    )
    with ZipFile(result.file_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["retention"] is None
        archive.extract("database/milk_weigh.sqlite3", tmp_path / "extracted")

    snapshot = tmp_path / "extracted" / "database" / "milk_weigh.sqlite3"
    assert _work_order_count(snapshot) == 1


def _setup_order_with_evidence(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    label = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": material["material_id"], "quantity": 1}).json()["labels"][0]
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]}).json()
    order = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product["id"], "target_weight_kg": 1000}).json()
    order_no = order["order_no"]
    client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr/validate",
        headers=headers,
        json={"label_id": label, "material_id": material["material_id"]},
    )
    qr_file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("qr.jpg", b"qr-image", "image/jpeg")}).json()["file_id"]
    client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": label, "material_id": material["material_id"], "evidence_file_id": qr_file_id},
    )
    return headers, order_no, qr_file_id


def test_backup_prunes_expired_evidence_uploads(client, tmp_path):
    headers, order_no, qr_file_id = _setup_order_with_evidence(client)
    _age_work_order(tmp_path, order_no, days=400)

    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 200

    backup = client.get("/api/v1/operations/backups", headers=headers).json()[0]
    with ZipFile(Path(backup["file_path"])) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["retention"]["expired_work_orders"] == 1
        assert qr_file_id in manifest["retention"]["expired_file_ids"]
        upload_names = [name for name in archive.namelist() if name.startswith("uploads/")]
        assert all(qr_file_id not in name for name in upload_names)
        archive.extract("database/milk_weigh.sqlite3", tmp_path / "extracted")

    snapshot = tmp_path / "extracted" / "database" / "milk_weigh.sqlite3"
    with sqlite3.connect(snapshot) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence_files").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM type_confirmations").fetchone()[0] == 0


def test_backup_keeps_fresh_evidence_uploads(client, tmp_path):
    headers, order_no, qr_file_id = _setup_order_with_evidence(client)

    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 200

    backup = client.get("/api/v1/operations/backups", headers=headers).json()[0]
    with ZipFile(Path(backup["file_path"])) as archive:
        upload_names = [name for name in archive.namelist() if name.startswith("uploads/")]
        assert any(qr_file_id in name for name in upload_names)
        archive.extract("database/milk_weigh.sqlite3", tmp_path / "extracted")

    snapshot = tmp_path / "extracted" / "database" / "milk_weigh.sqlite3"
    with sqlite3.connect(snapshot) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence_files").fetchone()[0] == 1
