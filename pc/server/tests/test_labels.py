from io import BytesIO

from openpyxl import Workbook


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def material(client, headers):
    return client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()


def test_print_batch_creates_unique_labels(client):
    headers = admin_headers(client)
    item = material(client, headers)
    response = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": item["material_id"], "quantity": 3})
    assert response.status_code == 201
    body = response.json()
    assert len(body["labels"]) == 3
    assert len(set(body["labels"])) == 3
    assert len(body["label_payloads"]) == 3
    assert [payload["labelId"] for payload in body["label_payloads"]] == body["labels"]
    assert all(payload["labelId"] != "PREVIEW" for payload in body["label_payloads"])
    assert all(payload["materialId"] == item["material_id"] for payload in body["label_payloads"])
    assert body["label_size"] == "60x40"
    assert all(payload["labelSize"] == "60x40" for payload in body["label_payloads"])
    assert body["printed_at"]
    assert body["status"] == "pending"

    from app.db.models import Label
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        persisted_ids = {
            label.label_id
            for label in db.query(Label).filter(Label.label_id.in_(body["labels"])).all()
        }
    assert {payload["labelId"] for payload in body["label_payloads"]} == persisted_ids

    batches = client.get("/api/v1/labels/print-batches", headers=headers).json()
    assert batches[0]["created_by_name"] == "系统管理员"


def test_print_batch_accepts_legacy_material_enabled_flag(client):
    headers = admin_headers(client)
    item = material(client, headers)
    from app.db.models import Material
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        row = db.query(Material).filter(Material.material_id == item["material_id"]).one()
        row.enabled = False
        db.commit()

    response = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": item["material_id"], "quantity": 1})
    assert response.status_code == 201


def test_print_batch_uses_configured_label_size(client):
    headers = admin_headers(client)
    item = material(client, headers)
    updated = client.put("/api/v1/settings", headers=headers, json={"values": {"label_size_mm": "70x50"}})
    assert updated.status_code == 200

    response = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": item["material_id"], "quantity": 1})
    assert response.status_code == 201
    body = response.json()
    assert body["label_size"] == "70x50"
    assert body["label_payloads"][0]["labelSize"] == "70x50"


def test_excel_validation_rejects_duplicate_code(client):
    headers = admin_headers(client)
    material(client, headers)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["material_code", "name_zh", "name_en", "shelf_life_months"])
    sheet.append(["A1", "蔗糖", "Sucrose", 24])
    sheet.append(["A2", "乳酸菌粉", "", 12])
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = client.post("/api/v1/labels/excel-validate", headers=headers, files={"file": ("materials.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 200
    assert response.json()["valid_count"] == 1
    assert response.json()["error_count"] == 1
