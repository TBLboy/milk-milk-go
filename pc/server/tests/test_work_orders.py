def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_product(client, headers):
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 12.5}]}).json()
    return product["id"]


def test_work_order_keeps_recipe_snapshot_and_calculates_weight(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    response = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 2000})
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "approved"
    assert order["steps"][0]["required_weight_kg"] == 25
    assert order["steps"][0]["tolerance_kg"] == 0.25


def test_operator_order_requires_admin_approval(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    client.post("/api/v1/auth/register", json={"username": "operator01", "display_name": "李师傅", "password": "operator123"})
    token = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"}).json()["access_token"]
    response = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"product_id": product_id, "target_weight_kg": 1000})
    assert response.status_code == 201
    assert response.json()["status"] == "pending_approval"
    assert client.post(f"/api/v1/work-orders/{response.json()['order_no']}/start", headers={"Authorization": f"Bearer {token}"}).status_code == 409
