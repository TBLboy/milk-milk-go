def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def setup_order(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    label = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": material["material_id"], "quantity": 1}).json()["labels"][0]
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]}).json()
    order = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product["id"], "target_weight_kg": 1000}).json()
    return headers, order["order_no"], material["material_id"], label


def test_qr_confirmation_and_weight_evidence(client):
    headers, order_no, material_id, label_id = setup_order(client)
    validation = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr/validate",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id},
    )
    assert validation.status_code == 200
    qr_file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("qr.jpg", b"qr-image", "image/jpeg")}).json()["file_id"]
    assert client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id, "evidence_file_id": qr_file_id},
    ).status_code == 200
    weight_validation = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight/validate",
        headers=headers,
        json={"weight_kg": 10},
    )
    assert weight_validation.status_code == 200
    file_response = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("scale.jpg", b"fake-image", "image/jpeg")})
    assert file_response.status_code == 201
    file_id = file_response.json()["file_id"]
    weight = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json={"weight_kg": 10, "scale_photo_file_id": file_id})
    assert weight.status_code == 200
    assert weight.json()["status"] == "passed"

    detail = client.get(f"/api/v1/work-orders/{order_no}", headers=headers).json()
    step = detail["steps"][0]
    assert step["confirmations"]
    assert step["confirmations"][0]["method"] == "qr"
    assert step["confirmations"][0]["status"] == "passed"
    assert step["confirmations"][0]["scanned_label_id"] == label_id
    assert step["confirmations"][0]["evidence_file_id"] == qr_file_id
    assert step["weighing_attempts"]
    assert step["weighing_attempts"][0]["scale_photo_file_id"] == file_id
    assert step["weighing_attempts"][0]["passed"] is True


def test_weight_validation_rejects_out_of_tolerance_without_evidence(client):
    headers, order_no, _, _ = setup_order(client)
    from app.db.models import WorkOrderStep
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        step = db.query(WorkOrderStep).filter(WorkOrderStep.work_order.has(order_no=order_no), WorkOrderStep.step_no == 1).one()
        step.status = "weighing"
        db.commit()

    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight/validate",
        headers=headers,
        json={"weight_kg": 8},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "WEIGHT_OUT_OF_TOLERANCE"
    assert client.get("/api/v1/evidence/files/integrity-check", headers=headers).json()["total"] == 0


def test_out_of_tolerance_weight_submission_creates_no_attempt_or_evidence(client):
    headers, order_no, _, _ = setup_order(client)
    from app.db.models import WorkOrderStep
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        step = db.query(WorkOrderStep).filter(WorkOrderStep.work_order.has(order_no=order_no), WorkOrderStep.step_no == 1).one()
        step.status = "weighing"
        db.commit()

    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight",
        headers=headers,
        json={"weight_kg": 8, "scale_photo_file_id": "FILE-NOT-UPLOADED"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "WEIGHT_OUT_OF_TOLERANCE"
    assert client.get("/api/v1/evidence/files/integrity-check", headers=headers).json()["total"] == 0
    detail = client.get(f"/api/v1/work-orders/{order_no}", headers=headers).json()
    assert detail["steps"][0]["weighing_attempts"] == []


def test_qr_validation_accepts_matching_label_without_evidence(client):
    headers, order_no, material_id, label_id = setup_order(client)

    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr/validate",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "valid"
    assert response.json()["label_id"] == label_id
    assert client.get("/api/v1/evidence/files/integrity-check", headers=headers).json()["total"] == 0


def test_qr_validation_rejects_mismatch_without_creating_evidence(client):
    headers, order_no, material_id, _ = setup_order(client)
    other = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "A2", "name_zh": "乳粉", "shelf_life_months": 24},
    ).json()
    other_label = client.post(
        "/api/v1/labels/print-batches",
        headers=headers,
        json={"material_id": other["material_id"], "quantity": 1},
    ).json()["labels"][0]

    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr/validate",
        headers=headers,
        json={"label_id": other_label, "material_id": material_id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LABEL_MATERIAL_MISMATCH"
    assert client.get("/api/v1/evidence/files/integrity-check", headers=headers).json()["total"] == 0


def test_qr_confirmation_requires_uploaded_evidence(client):
    headers, order_no, material_id, label_id = setup_order(client)
    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id},
    )
    assert response.status_code == 422


def test_unassigned_operator_cannot_confirm_work_order_step(client):
    headers = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "PERM-01", "name_zh": "权限测试辅料", "shelf_life_months": 24},
    ).json()
    label_id = client.post(
        "/api/v1/labels/print-batches",
        headers=headers,
        json={"material_id": material["material_id"], "quantity": 1},
    ).json()["labels"][0]
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={"name": "权限测试产品", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]},
    ).json()
    assigned = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "step_owner", "display_name": "步骤执行人", "password": "operator123", "employee_no": "MH1012"},
    ).json()["user"]
    other = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "step_other", "display_name": "步骤其他人", "password": "operator123", "employee_no": "MH1013"},
    ).json()["user"]
    order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000, "operator_id": assigned["id"]},
    ).json()
    assigned_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'step_owner', 'password': 'operator123'}).json()['access_token']}"
    }
    other_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'step_other', 'password': 'operator123'}).json()['access_token']}"
    }
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=assigned_headers).status_code == 200
    file_id = client.post(
        "/api/v1/evidence/files",
        headers=other_headers,
        files={"file": ("qr.jpg", b"qr-image", "image/jpeg")},
    ).json()["file_id"]

    response = client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
        headers=other_headers,
        json={"label_id": label_id, "material_id": material["material_id"], "evidence_file_id": file_id},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "WORK_ORDER_OPERATOR_REQUIRED"


def test_qr_confirmation_requires_label_id(client):
    headers, order_no, material_id, _ = setup_order(client)
    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("qr.jpg", b"qr-image", "image/jpeg")}).json()["file_id"]
    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"material_id": material_id, "evidence_file_id": file_id},
    )
    assert response.status_code == 422


def test_qr_confirmation_rejects_unknown_label(client):
    headers, order_no, material_id, _ = setup_order(client)
    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("qr.jpg", b"qr-image", "image/jpeg")}).json()["file_id"]
    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": "LBL-NOT-FOUND", "material_id": material_id, "evidence_file_id": file_id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LABEL_NOT_FOUND"


def test_qr_confirmation_rejects_void_label(client):
    headers, order_no, material_id, label_id = setup_order(client)
    from app.db.models import Label
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        label = db.query(Label).filter(Label.label_id == label_id).one()
        label.status = "void"
        db.commit()

    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("qr.jpg", b"qr-image", "image/jpeg")}).json()["file_id"]
    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id, "evidence_file_id": file_id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LABEL_NOT_ACTIVE"


def test_qr_confirmation_rejects_label_material_mismatch(client):
    headers, order_no, material_id, _ = setup_order(client)
    other = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A2", "name_zh": "乳粉", "shelf_life_months": 24}).json()
    other_label = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": other["material_id"], "quantity": 1}).json()["labels"][0]
    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("qr.jpg", b"qr-image", "image/jpeg")}).json()["file_id"]
    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": other_label, "material_id": material_id, "evidence_file_id": file_id},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LABEL_MATERIAL_MISMATCH"


def test_qr_confirmation_explains_same_name_different_material_id(client):
    headers, order_no, _, _ = setup_order(client)
    current = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "SWEET-01", "name_zh": "蔗糖", "shelf_life_months": 24},
    ).json()
    current_label = client.post(
        "/api/v1/labels/print-batches",
        headers=headers,
        json={"material_id": current["material_id"], "quantity": 1},
    ).json()["labels"][0]
    file_id = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("qr.jpg", b"qr-image", "image/jpeg")},
    ).json()["file_id"]

    response = client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={
            "label_id": current_label,
            "material_id": current["material_id"],
            "evidence_file_id": file_id,
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "MATERIAL_MISMATCH"
    assert "A1 蔗糖" in detail["message"]
    assert "SWEET-01 蔗糖" in detail["message"]
    assert "MAT-" in detail["message"]


def test_photo_approval_is_required_before_weight(client):
    headers, order_no, _, _ = setup_order(client)
    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("material.jpg", b"fake-image", "image/jpeg")}).json()["file_id"]
    request = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/photo-request", headers=headers, json={"reason": "自制标签尚未粘贴", "file_id": file_id})
    assert request.status_code == 200
    assert client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json={"weight_kg": 10, "scale_photo_file_id": file_id}).status_code == 409
    confirmation_id = request.json()["confirmation_id"]
    assert client.post(f"/api/v1/evidence/confirmations/{confirmation_id}/approve", headers=headers).status_code == 200
    weight = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json={"weight_kg": 10, "scale_photo_file_id": file_id})
    assert weight.status_code == 200
    assert weight.json()["status"] == "passed"


def test_uploaded_evidence_file_can_be_fetched(client):
    headers = admin_headers(client)
    uploaded = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("label.png", b"fake-image-bytes", "image/png")})
    assert uploaded.status_code == 201
    file_id = uploaded.json()["file_id"]
    fetched = client.get(f"/api/v1/evidence/files/{file_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == b"fake-image-bytes"

def test_approvals_api_lists_and_rejects(client):
    headers, order_no, _, _ = setup_order(client)
    file_id = client.post("/api/v1/evidence/files", headers=headers, files={"file": ("material.jpg", b"fake-image", "image/jpeg")}).json()["file_id"]
    request = client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/photo-request", headers=headers, json={"reason": "模糊无法扫码", "file_id": file_id})
    conf_id = request.json()["confirmation_id"]
    
    approvals = client.get("/api/v1/approvals", headers=headers).json()
    assert len(approvals) >= 1
    assert any(a["confirmation_id"] == conf_id for a in approvals)
    
    reject_res = client.post(f"/api/v1/approvals/{conf_id}/reject", headers=headers)
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"
    
    # After rejection, it should no longer be in pending
    approvals_after = client.get("/api/v1/approvals", headers=headers).json()
    assert not any(a["confirmation_id"] == conf_id for a in approvals_after)
