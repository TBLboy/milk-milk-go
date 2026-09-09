from io import BytesIO

from openpyxl import Workbook


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_list_created_users(client):
    headers = admin_headers(client)
    create = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"username": "operator99", "display_name": "测试操作员", "password": "password123"},
    )
    assert create.status_code == 201
    users = client.get("/api/v1/auth/users", headers=headers).json()
    assert any(item["username"] == "operator99" for item in users)


def test_settings_defaults_can_be_updated(client):
    headers = admin_headers(client)
    defaults = client.get("/api/v1/settings", headers=headers)
    assert defaults.status_code == 200
    assert defaults.json()["default_tolerance_percent"] == "1.0"
    updated = client.put("/api/v1/settings", headers=headers, json={"values": {"default_tolerance_percent": "1.5"}})
    assert updated.status_code == 200
    assert updated.json()["default_tolerance_percent"] == "1.5"


def test_excel_import_creates_materials(client):
    headers = admin_headers(client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "materials"
    sheet.append(["material_code", "name_zh", "name_en", "shelf_life_months"])
    sheet.append(["Z9", "测试辅料", "Test Material", 18])
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = client.post("/api/v1/labels/excel-import", headers=headers, files={"file": ("materials.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 200
    assert response.json()["imported_count"] == 1
    materials = client.get("/api/v1/master-data/materials", headers=headers).json()
    assert any(item["material_code"] == "Z9" for item in materials)
