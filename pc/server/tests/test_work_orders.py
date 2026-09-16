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
    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "operator01", "display_name": "李师傅", "password": "operator123", "employee_no": "MH1008"},
    ).json()["user"]
    assert created["status"] == "active"
    token = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"}).json()["access_token"]
    response = client.post("/api/v1/work-orders", headers={"Authorization": f"Bearer {token}"}, json={"product_id": product_id, "target_weight_kg": 1000})
    assert response.status_code == 201
    assert response.json()["status"] == "pending_approval"
    assert client.post(f"/api/v1/work-orders/{response.json()['order_no']}/start", headers={"Authorization": f"Bearer {token}"}).status_code == 409


def test_only_assigned_operator_can_start_and_complete_order(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    assigned = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "assigned_operator", "display_name": "执行人", "password": "operator123", "employee_no": "MH1010"},
    ).json()["user"]
    other = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "other_operator", "display_name": "其他操作员", "password": "operator123", "employee_no": "MH1011"},
    ).json()["user"]
    assigned_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'assigned_operator', 'password': 'operator123'}).json()['access_token']}"
    }
    other_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'other_operator', 'password': 'operator123'}).json()['access_token']}"
    }
    order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product_id, "target_weight_kg": 1000, "operator_id": assigned["id"]},
    ).json()

    denied_start = client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=other_headers)
    assert denied_start.status_code == 403
    assert denied_start.json()["detail"]["code"] == "WORK_ORDER_OPERATOR_REQUIRED"
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=assigned_headers).status_code == 200

    denied_complete = client.post(f"/api/v1/work-orders/{order['order_no']}/complete", headers=other_headers)
    assert denied_complete.status_code == 403
    assert denied_complete.json()["detail"]["code"] == "WORK_ORDER_OPERATOR_REQUIRED"


def test_work_order_creator_cannot_operate_after_takeover(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    creator = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "creator_operator", "display_name": "原创建人", "password": "operator123", "employee_no": "MH1014"},
    ).json()["user"]
    replacement = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "replacement_operator", "display_name": "接管执行人", "password": "operator123", "employee_no": "MH1015"},
    ).json()["user"]
    creator_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'creator_operator', 'password': 'operator123'}).json()['access_token']}"
    }
    replacement_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'replacement_operator', 'password': 'operator123'}).json()['access_token']}"
    }
    order = client.post(
        "/api/v1/work-orders",
        headers=creator_headers,
        json={"product_id": product_id, "target_weight_kg": 1000},
    ).json()
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/approve", headers=headers).status_code == 200

    takeover = client.post(
        f"/api/v1/work-orders/{order['order_no']}/requests",
        headers=replacement_headers,
        json={"request_type": "takeover", "reason": "现场接替执行"},
    ).json()
    assert client.post(f"/api/v1/work-orders/requests/{takeover['id']}/approve", headers=headers).status_code == 200

    denied = client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=creator_headers)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "WORK_ORDER_OPERATOR_REQUIRED"
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=replacement_headers).status_code == 200


def test_pending_work_order_appears_in_admin_approvals(client):
    headers = admin_headers(client)
    product_id = create_product(client, headers)
    operator = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "operator_approval", "display_name": "李师傅", "password": "operator123", "employee_no": "MH1009"},
    ).json()["user"]
    token = client.post("/api/v1/auth/login", json={"username": "operator_approval", "password": "operator123"}).json()["access_token"]
    order = client.post(
        "/api/v1/work-orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": product_id, "target_weight_kg": 1000},
    ).json()

    approvals = client.get("/api/v1/approvals", headers=headers).json()
    approval = next((item for item in approvals if item["order_no"] == order["order_no"] and item["type"] == "work_order"), None)
    assert approval is not None
    assert approval["id"] == f"AP-WO-{order['order_no']}"

    approved = client.post(f"/api/v1/work-orders/{order['order_no']}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    approvals_after = client.get("/api/v1/approvals", headers=headers).json()
    assert not any(item["order_no"] == order["order_no"] and item["type"] == "work_order" for item in approvals_after)


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
