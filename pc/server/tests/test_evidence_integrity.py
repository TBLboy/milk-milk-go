import hashlib
from pathlib import Path


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload_image(client, headers, filename, content):
    response = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": (filename, content, "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def test_upload_records_sha256_metadata_and_file_remains_readable(client):
    headers = admin_headers(client)
    content = b"production-evidence-content"
    uploaded = upload_image(client, headers, "evidence.jpg", content)

    assert uploaded["sha256"] == hashlib.sha256(content).hexdigest()
    assert uploaded["size_bytes"] == len(content)

    from app.db.models import EvidenceFile
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        evidence = db.query(EvidenceFile).filter(EvidenceFile.file_id == uploaded["file_id"]).one()
        assert evidence.sha256 == uploaded["sha256"]
        assert evidence.size_bytes == len(content)
        assert evidence.content_type == "image/jpeg"
        assert evidence.uploaded_by > 0
        assert evidence.created_at is not None

    fetched = client.get(f"/api/v1/evidence/files/{uploaded['file_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == content

    checked = client.get("/api/v1/evidence/files/integrity-check", headers=headers)
    assert checked.status_code == 200
    assert checked.json()["total"] == 1
    assert checked.json()["ok"] == 1
    assert checked.json()["issue_count"] == 0


def test_integrity_check_detects_tampered_and_missing_files(client):
    headers = admin_headers(client)
    untouched = upload_image(client, headers, "untouched.jpg", b"untouched")
    tampered = upload_image(client, headers, "tampered.jpg", b"original-a")
    missing = upload_image(client, headers, "missing.jpg", b"missing-file")

    from app.db.models import EvidenceFile
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        rows = {
            item.file_id: Path(item.stored_path)
            for item in db.query(EvidenceFile).filter(
                EvidenceFile.file_id.in_([untouched["file_id"], tampered["file_id"], missing["file_id"]])
            )
        }

    rows[tampered["file_id"]].write_bytes(b"tampered-a")
    rows[missing["file_id"]].unlink()

    response = client.get("/api/v1/evidence/files/integrity-check", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["ok"] == 1
    assert body["issue_count"] == 2
    statuses = {item["file_id"]: item["status"] for item in body["items"]}
    assert statuses[untouched["file_id"]] == "ok"
    assert statuses[tampered["file_id"]] == "hash_mismatch"
    assert statuses[missing["file_id"]] == "missing"
    issues = {item["file_id"]: item for item in body["issues"]}
    assert issues[tampered["file_id"]]["expected_sha256"] != issues[tampered["file_id"]]["actual_sha256"]


def test_existing_file_id_cannot_be_overwritten(client, monkeypatch):
    from app.api import evidence as evidence_api

    headers = admin_headers(client)
    monkeypatch.setattr(evidence_api.secrets, "token_hex", lambda _size: "a" * 24)

    first = upload_image(client, headers, "first.jpg", b"first-content")
    second = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("second.jpg", b"second-content", "image/jpeg")},
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "EVIDENCE_FILE_EXISTS"
    fetched = client.get(f"/api/v1/evidence/files/{first['file_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == b"first-content"


def test_integrity_check_requires_admin(client):
    headers = admin_headers(client)
    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "integrity_operator", "display_name": "普通操作员", "password": "operator123", "employee_no": "MH1002"},
    )
    assert created.status_code == 201
    token = client.post("/api/v1/auth/login", json={"username": "integrity_operator", "password": "operator123"}).json()["access_token"]
    response = client.get(
        "/api/v1/evidence/files/integrity-check",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_REQUIRED"
