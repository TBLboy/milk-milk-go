def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def operator_headers(client):
    headers = admin_headers(client)
    client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "operator01", "display_name": "李师傅", "password": "operator123"},
    )
    token = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_product(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]}).json()
    return product["id"]


def create_order(client, product_id):
    headers = admin_headers(client)
    return client.post("/api/v1/work-orders", headers=headers, json={"product_id": product_id, "target_weight_kg": 1000}).json()


def test_takeover_request_updates_operator_after_admin_approval(client):
    product_id = create_product(client)
    order = create_order(client, product_id)
    admin = admin_headers(client)
    operator = operator_headers(client)

    listed = client.get("/api/v1/work-orders", headers=operator).json()
    assert any(item["order_no"] == order["order_no"] for item in listed)
    assert client.get(f"/api/v1/work-orders/{order['order_no']}", headers=operator).status_code == 200
    assert client.get("/api/v1/master-data/products", headers=operator).status_code == 200

    request = client.post(
        f"/api/v1/work-orders/{order['order_no']}/requests",
        headers=operator,
        json={"request_type": "takeover", "reason": "原执行人不在现场"},
    )
    assert request.status_code == 201
    request_id = request.json()["id"]
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/requests", headers=operator, json={"request_type": "takeover", "reason": "重复申请"}).status_code == 409

    approvals = client.get("/api/v1/approvals", headers=admin).json()
    assert any(item["id"] == f"AP-REQ-{request_id}" for item in approvals)

    approved = client.post(f"/api/v1/work-orders/requests/{request_id}/approve", headers=admin)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    detail = client.get(f"/api/v1/work-orders/{order['order_no']}", headers=operator).json()
    assert detail["operator_name"] == "李师傅"


def test_cancel_and_delete_requests_keep_traceable_records(client):
    admin = admin_headers(client)
    operator = operator_headers(client)
    product_id = create_product(client)
    order_one = create_order(client, product_id)
    order_two = create_order(client, product_id)

    cancel = client.post(
        f"/api/v1/work-orders/{order_one['order_no']}/requests",
        headers=operator,
        json={"request_type": "cancel", "reason": "计划调整"},
    ).json()
    cancelled = client.post(f"/api/v1/work-orders/requests/{cancel['id']}/approve", headers=admin)
    assert cancelled.status_code == 200
    assert client.get(f"/api/v1/work-orders/{order_one['order_no']}", headers=admin).json()["status"] == "cancelled"

    delete = client.post(
        f"/api/v1/work-orders/{order_two['order_no']}/requests",
        headers=operator,
        json={"request_type": "delete", "reason": "误建工单"},
    ).json()
    deleted = client.post(f"/api/v1/work-orders/requests/{delete['id']}/approve", headers=admin)
    assert deleted.status_code == 200
    assert client.get(f"/api/v1/work-orders/{order_two['order_no']}", headers=admin).json()["status"] == "deleted"

    operator_orders = client.get("/api/v1/work-orders", headers=operator).json()
    assert all(item["order_no"] != order_two["order_no"] for item in operator_orders)
    admin_orders = client.get("/api/v1/work-orders", headers=admin).json()
    assert [item["order_no"] for item in admin_orders][-2:] == [order_two["order_no"], order_one["order_no"]]


def test_work_order_request_can_be_rejected(client):
    product_id = create_product(client)
    order = create_order(client, product_id)
    admin = admin_headers(client)
    operator = operator_headers(client)
    request = client.post(
        f"/api/v1/work-orders/{order['order_no']}/requests",
        headers=operator,
        json={"request_type": "takeover", "reason": "希望接管"},
    ).json()
    rejected = client.post(f"/api/v1/work-orders/requests/{request['id']}/reject", headers=admin)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get(f"/api/v1/work-orders/{order['order_no']}", headers=admin).json()["operator_name"] != "李师傅"
