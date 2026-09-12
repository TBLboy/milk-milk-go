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


def test_work_order_uses_configured_tolerance(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    client.put("/api/v1/settings", headers=headers, json={
        "values": {"default_tolerance_percent": "2.0", "min_absolute_tolerance_grams": "100"}
    })
    order = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 2000}).json()
    assert order["steps"][0]["required_weight_kg"] == 25
    assert order["steps"][0]["tolerance_kg"] == 0.5


def test_operator_order_requires_admin_approval(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    client.post("/api/v1/auth/register", json={"username": "operator01", "display_name": "李师傅", "password": "operator123"})
    token = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"}).json()["access_token"]
    response = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"product_id": product_id, "target_weight_kg": 1000})
    assert response.status_code == 201
    assert response.json()["status"] == "pending_approval"
    assert client.post(f"/api/v1/work-orders/{response.json()['order_no']}/start", headers={"Authorization": f"Bearer {token}"}).status_code == 409


def test_admin_can_cancel_order_but_not_complete_incomplete_steps(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    order = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1000}).json()
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/complete", headers=headers).status_code == 409
    client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers)
    cancel = client.post(f"/api/v1/work-orders/{order['order_no']}/cancel", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers).status_code == 409


def test_cancelled_orders_are_sorted_last(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    active = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1000}).json()
    cancelled = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1500}).json()
    assert client.post(f"/api/v1/work-orders/{cancelled['order_no']}/cancel", headers=headers).status_code == 200

    listed = client.get("/api/v1/work-orders", headers=headers).json()
    statuses = [item["status"] for item in listed]
    assert statuses == ["approved", "cancelled"]
    assert listed[0]["order_no"] == active["order_no"]
