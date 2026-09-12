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
    assert body["printed_at"]
    assert body["status"] == "pending"


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
