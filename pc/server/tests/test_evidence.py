def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_order(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]}).json()
    order = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product["id"], "target_weight_kg": 1000}).json()
    return headers, order["order_no"], material["material_id"]


def test_qr_confirmation_and_weight_evidence(client):
    headers, order_no, material_id = setup_order(client)
    assert client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr", headers=headers, json={"material_id": material_id}).status_code == 200
    file_response = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("scale.jpg", b"fake-image", "image/jpeg")})
    assert file_response.status_code == 201
    file_id = file_response.json()["file_id"]
    weight = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json={"weight_kg": 10, "scale_photo_file_id": file_id})
    assert weight.status_code == 200
    assert weight.json()["status"] == "passed"


def test_photo_approval_is_required_before_weight(client):
    headers, order_no, _ = setup_order(client)
    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("material.jpg", b"fake-image", "image/jpeg")}).json()["file_id"]
    request = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/photo-request", headers=headers, json={"reason": "自制标签尚未粘贴", "file_id": file_id})
    assert request.status_code == 200
    assert client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json={"weight_kg": 10, "scale_photo_file_id": file_id}).status_code == 409
    confirmation_id = request.json()["confirmation_id"]
    assert client.post(f"/api/v1/evidence/confirmations/{confirmation_id}/approve", headers=headers).status_code == 200
    weight = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json={"weight_kg": 10, "scale_photo_file_id": file_id})
    assert weight.status_code == 200
    assert weight.json()["status"] == "passed"
