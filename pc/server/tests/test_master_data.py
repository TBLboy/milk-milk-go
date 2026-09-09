def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_operator_cannot_read_master_data(client):
    client.post("/api/v1/auth/register", json={"username": "operator01", "display_name": "李师傅", "password": "operator123"})
    token = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"}).json()["access_token"]
    assert client.get("/api/v1/master-data/materials", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_admin_can_create_material_and_product_recipe(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "name_en": "Sucrose", "shelf_life_months": 24, "image_file_ids": ["file-a", "file-b"]})
    assert material.status_code == 201
    material_id = material.json()["material_id"]
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙纯牛奶 1L", "items": [{"material_id": material_id, "quantity_per_ton_kg": 12.5}]})
    assert product.status_code == 201
    assert product.json()["items"][0]["quantity_per_ton_kg"] == 12.5


def test_recipe_rejects_disabled_material(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    client.patch(f"/api/v1/master-data/materials/{material['material_id']}/disable", headers=headers)
    response = client.post("/api/v1/master-data/products", headers=headers, json={"name": "测试产品", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 1}]})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "MATERIAL_NOT_AVAILABLE"
