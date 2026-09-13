import json


def admin_headers(client):
    token = client.post(
        "/api/v1/auth/admin/login",
        json={"username": "admin", "password": "admin123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_operator(client, headers, *, username="audit_operator", employee_no="AUDIT001"):
    return client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": username,
            "display_name": "审计操作员",
            "password": "operator123",
            "employee_no": employee_no,
        },
    ).json()["user"]


def create_order_fixture(client, headers):
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "AUD-A1", "name_zh": "审计用蔗糖", "shelf_life_months": 24},
    ).json()
    label_id = client.post(
        "/api/v1/labels/print-batches",
        headers=headers,
        json={"material_id": material["material_id"], "quantity": 1},
    ).json()["labels"][0]
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={
            "name": "审计测试产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}],
        },
    ).json()
    order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()
    return material, label_id, product, order


def upload_image(client, headers, name, content=b"audit-image"):
    return client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": (name, content, "image/jpeg")},
    ).json()["file_id"]


def test_audit_log_permissions_filters_and_pagination(client):
    admin = admin_headers(client)
    admin_headers(client)
    operator = create_operator(client, admin)
    operator_token = client.post(
        "/api/v1/auth/login",
        json={"username": operator["username"], "password": "operator123"},
    ).json()["access_token"]

    forbidden = client.get(
        "/api/v1/operations/audit-logs",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert forbidden.status_code == 403

    response = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={
            "start_at": "2000-01-01T00:00:00Z",
            "end_at": "2100-01-01T00:00:00Z",
            "actor_id": operator["id"],
            "action": "auth.login",
            "result": "success",
            "page": 1,
            "page_size": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["actor_id"] == operator["id"]
    assert item["actor_username"] == operator["username"]
    assert item["action"] == "auth.login"
    assert item["result"] == "success"
    assert item["detail"]["portal"] == "app"

    paged = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={"action": "auth.admin_login", "page": 2, "page_size": 1},
    ).json()
    assert paged["page"] == 2
    assert paged["pages"] >= 2
    assert len(paged["items"]) == 1


def test_audit_redacts_sensitive_values(client):
    from app.services.audit import sanitize_audit_detail

    admin = admin_headers(client)
    operator = create_operator(client, admin, username="secret_operator", employee_no="AUDIT002")
    operator_token = client.post(
        "/api/v1/auth/login",
        json={"username": operator["username"], "password": "operator123"},
    ).json()["access_token"]
    response = client.post(
        "/api/v1/auth/me/change-password",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"current_password": "wrong-secret", "new_password": "new-secret-123"},
    )
    assert response.status_code == 422

    logs = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={"actor_id": operator["id"], "action": "account.password_changed"},
    ).json()["items"]
    assert logs
    serialized = json.dumps(logs, ensure_ascii=False)
    assert "wrong-secret" not in serialized
    assert "new-secret-123" not in serialized
    assert logs[0]["result"] == "failure"

    sanitized = sanitize_audit_detail(
        {
            "password": "plain",
            "nested": {
                "access_token": "token-value",
                "smtp_password": "mail-secret",
                "safe": "visible",
            },
        }
    )
    assert sanitized == {
        "password": "[REDACTED]",
        "nested": {
            "access_token": "[REDACTED]",
            "smtp_password": "[REDACTED]",
            "safe": "visible",
        },
    }


def test_critical_workflow_writes_traceable_audit_events(client):
    admin = admin_headers(client)
    operator = create_operator(client, admin, username="workflow_operator", employee_no="AUDIT003")
    operator_token = client.post(
        "/api/v1/auth/login",
        json={"username": operator["username"], "password": "operator123"},
    ).json()["access_token"]
    operator_headers = {"Authorization": f"Bearer {operator_token}"}

    material, label_id, product, pending_order = create_order_fixture(client, admin)
    order = client.post(
        "/api/v1/work-orders",
        headers=operator_headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()
    assert order["status"] == "pending_approval"
    assert client.post(
        f"/api/v1/work-orders/{order['order_no']}/approve",
        headers=admin,
    ).status_code == 200
    assert client.post(
        f"/api/v1/work-orders/{order['order_no']}/start",
        headers=operator_headers,
    ).status_code == 200

    qr_file_id = upload_image(client, operator_headers, "qr.jpg")
    assert client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
        headers=operator_headers,
        json={
            "label_id": label_id,
            "material_id": material["material_id"],
            "evidence_file_id": qr_file_id,
        },
    ).status_code == 200
    scale_file_id = upload_image(client, operator_headers, "scale.jpg")
    assert client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/weight",
        headers=operator_headers,
        json={"weight_kg": 10, "scale_photo_file_id": scale_file_id},
    ).json()["status"] == "passed"
    assert client.post(
        f"/api/v1/work-orders/{order['order_no']}/complete",
        headers=operator_headers,
    ).status_code == 200

    takeover_order = client.post(
        "/api/v1/work-orders",
        headers=admin,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()
    takeover = client.post(
        f"/api/v1/work-orders/{takeover_order['order_no']}/requests",
        headers=operator_headers,
        json={"request_type": "takeover", "reason": "原执行人不在现场"},
    )
    assert takeover.status_code == 201
    assert client.post(
        f"/api/v1/work-orders/requests/{takeover.json()['id']}/approve",
        headers=admin,
    ).status_code == 200

    first_order_logs = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={"work_order_no": order["order_no"], "page_size": 100},
    ).json()
    actions = {item["action"] for item in first_order_logs["items"]}
    assert first_order_logs["total"] >= 5
    assert {
        "work_order.created",
        "work_order.approved",
        "work_order.started",
        "type_confirmation.passed",
        "weighing.passed",
        "work_order.completed",
    } <= actions

    request_logs = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={"work_order_no": takeover_order["order_no"], "page_size": 100},
    ).json()["items"]
    request_actions = {item["action"] for item in request_logs}
    assert {"work_order.created", "work_order.request_created", "work_order.request_approved"} <= request_actions

    master_actions = {
        item["action"]
        for action in ("material.created", "product.created", "label.batch_created")
        for item in client.get(
            "/api/v1/operations/audit-logs",
            headers=admin,
            params={"action": action},
        ).json()["items"]
    }
    assert master_actions == {"material.created", "product.created", "label.batch_created"}


def test_rejected_photo_and_weight_attempts_are_audited(client):
    admin = admin_headers(client)
    material, label_id, _, order = create_order_fixture(client, admin)
    assert client.post(
        f"/api/v1/work-orders/{order['order_no']}/start",
        headers=admin,
    ).status_code == 200
    photo_file_id = upload_image(client, admin, "material.jpg")
    photo_request = client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/photo-request",
        headers=admin,
        json={"reason": "标签模糊", "file_id": photo_file_id},
    ).json()
    confirmation_id = photo_request["confirmation_id"]
    assert client.post(
        f"/api/v1/approvals/{confirmation_id}/reject",
        headers=admin,
    ).status_code == 200

    assert client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
        headers=admin,
        json={
            "label_id": label_id,
            "material_id": material["material_id"],
            "evidence_file_id": photo_file_id,
        },
    ).status_code == 200
    scale_file_id = upload_image(client, admin, "scale.jpg")
    rejected_weight = client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/weight",
        headers=admin,
        json={"weight_kg": 8, "scale_photo_file_id": scale_file_id},
    )
    assert rejected_weight.status_code == 200
    assert rejected_weight.json()["status"] == "out_of_tolerance"

    events = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={"work_order_no": order["order_no"], "page_size": 100},
    ).json()["items"]
    rejected = {(item["action"], item["result"]) for item in events}
    assert ("type_confirmation.photo_requested", "success") in rejected
    assert ("type_confirmation.rejected", "rejected") in rejected
    assert ("type_confirmation.passed", "success") in rejected
    assert ("weighing.rejected", "rejected") in rejected


def test_idempotent_replay_does_not_duplicate_audit_event(client):
    admin = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=admin,
        json={"material_code": "AUD-IDEM", "name_zh": "幂等审计辅料", "shelf_life_months": 12},
    ).json()
    headers = {**admin, "X-Request-ID": "audit-idempotency-replay"}
    payload = {"material_id": material["material_id"], "quantity": 2}

    first = client.post("/api/v1/labels/print-batches", headers=headers, json=payload)
    second = client.post("/api/v1/labels/print-batches", headers=headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["batch_id"] == second.json()["batch_id"]

    logs = client.get(
        "/api/v1/operations/audit-logs",
        headers=admin,
        params={"action": "label.batch_created"},
    ).json()
    assert logs["total"] == 1
