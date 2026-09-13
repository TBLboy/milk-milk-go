import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.exc import OperationalError


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_material(client, headers, code="A1", name="蔗糖"):
    response = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": code, "name_zh": name, "shelf_life_months": 24},
    )
    assert response.status_code == 201
    return response.json()


def create_label(client, headers, material_id, key=None):
    request_headers = dict(headers)
    if key:
        request_headers["Idempotency-Key"] = key
    response = client.post(
        "/api/v1/labels/print-batches",
        headers=request_headers,
        json={"material_id": material_id, "quantity": 1},
    )
    assert response.status_code == 201
    return response


def create_order(client, headers, product_name="并发测试产品"):
    material = create_material(client, headers)
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={"name": product_name, "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]},
    ).json()
    order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()
    return material, order


def upload_evidence(client, headers, filename="evidence.jpg", content=b"image"):
    response = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": (filename, content, "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()["file_id"]


def qr_payload(client, headers, order_no, label_id, material_id, key, evidence_file_id=None):
    evidence_file_id = evidence_file_id or upload_evidence(client, headers, "qr.jpg", b"qr-image")
    request_headers = {**headers, "Idempotency-Key": key}
    return client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=request_headers,
        json={"label_id": label_id, "material_id": material_id, "evidence_file_id": evidence_file_id},
    )


def test_same_key_replays_qr_and_does_not_duplicate_confirmation(client):
    headers = admin_headers(client)
    material, order = create_order(client, headers)
    label = create_label(client, headers, material["material_id"]).json()["labels"][0]
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers).status_code == 200
    evidence_file_id = upload_evidence(client, headers, "qr.jpg", b"qr-image")

    first = qr_payload(client, headers, order["order_no"], label, material["material_id"], "qr-replay-1", evidence_file_id)
    second = qr_payload(client, headers, order["order_no"], label, material["material_id"], "qr-replay-1", evidence_file_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    detail = client.get(f"/api/v1/work-orders/{order['order_no']}", headers=headers).json()
    assert detail["steps"][0]["status"] == "weighing"
    assert len(detail["steps"][0]["confirmations"]) == 1


def test_concurrent_recipe_edits_never_duplicate_version_numbers(client):
    headers = admin_headers(client)
    material = create_material(client, headers, code="VERCON", name="并发版本辅料")
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={
            "name": "并发版本产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 5}],
        },
    ).json()
    barrier = threading.Barrier(2)

    def update_recipe(quantity):
        barrier.wait()
        return client.put(
            f"/api/v1/master-data/products/{product['id']}",
            headers=headers,
            json={
                "name": "并发版本产品",
                "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": quantity}],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(update_recipe, [7.5, 9.0]))

    assert any(response.status_code == 200 for response in responses)
    assert all(response.status_code in {200, 409, 503} for response in responses)
    history = client.get(
        f"/api/v1/master-data/products/{product['id']}/recipe-versions",
        headers=headers,
    ).json()
    versions = [item["version"] for item in history]
    assert versions == sorted(set(versions), reverse=True)
    assert versions[-1] == 1
    assert versions[0] == len(versions)
    assert sum(item["is_current"] for item in history) == 1


def test_same_key_replays_label_batch_and_rejects_different_payload(client):
    headers = admin_headers(client)
    material = create_material(client, headers)
    request_headers = {**headers, "Idempotency-Key": "label-replay-1"}
    payload = {"material_id": material["material_id"], "quantity": 2}

    first = client.post("/api/v1/labels/print-batches", headers=request_headers, json=payload)
    second = client.post("/api/v1/labels/print-batches", headers=request_headers, json=payload)
    reused = client.post(
        "/api/v1/labels/print-batches",
        headers=request_headers,
        json={"material_id": material["material_id"], "quantity": 1},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert len(client.get("/api/v1/labels/print-batches", headers=headers).json()) == 1
    assert reused.status_code == 409
    assert reused.json()["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_same_key_weight_submission_creates_one_attempt(client):
    headers = admin_headers(client)
    material, order = create_order(client, headers)
    label = create_label(client, headers, material["material_id"]).json()["labels"][0]
    client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers)
    assert qr_payload(client, headers, order["order_no"], label, material["material_id"], "weight-qr-1").status_code == 200

    scale_file_id = upload_evidence(client, headers, "scale.jpg", b"scale-image")
    request_headers = {**headers, "Idempotency-Key": "weight-submit-1"}
    payload = {"weight_kg": 10, "scale_photo_file_id": scale_file_id}
    first = client.post(f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/weight", headers=request_headers, json=payload)
    second = client.post(f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/weight", headers=request_headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    detail = client.get(f"/api/v1/work-orders/{order['order_no']}", headers=headers).json()
    assert len(detail["steps"][0]["weighing_attempts"]) == 1


def test_different_keys_only_advance_qr_step_once(client):
    headers = admin_headers(client)
    material, order = create_order(client, headers)
    label = create_label(client, headers, material["material_id"]).json()["labels"][0]
    client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers)
    evidence_file_id = upload_evidence(client, headers, "qr.jpg", b"qr-image")
    barrier = threading.Barrier(2)

    def submit(key):
        barrier.wait()
        return client.post(
            f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
            headers={**headers, "Idempotency-Key": key},
            json={"label_id": label, "material_id": material["material_id"], "evidence_file_id": evidence_file_id},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, ["qr-concurrent-a", "qr-concurrent-b"]))

    assert sum(response.status_code == 200 for response in responses) == 1
    loser = next(response for response in responses if response.status_code != 200)
    assert loser.status_code in {409, 503}
    assert loser.json()["detail"]["code"] in {"STEP_STATE_CONFLICT", "DATABASE_BUSY"}
    detail = client.get(f"/api/v1/work-orders/{order['order_no']}", headers=headers).json()
    assert len(detail["steps"][0]["confirmations"]) == 1


def test_concurrent_work_order_requests_keep_only_one_pending(client):
    headers = admin_headers(client)
    _, order = create_order(client, headers, "申请并发产品")
    operator = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "concurrent_operator", "display_name": "并发操作员", "password": "operator123", "employee_no": "MH1003"},
    ).json()["user"]
    token = client.post("/api/v1/auth/login", json={"username": "concurrent_operator", "password": "operator123"}).json()["access_token"]
    operator_headers = {"Authorization": f"Bearer {token}"}
    barrier = threading.Barrier(2)

    def submit(index):
        barrier.wait()
        return client.post(
            f"/api/v1/work-orders/{order['order_no']}/requests",
            headers={**operator_headers, "X-Request-ID": f"request-{index}"},
            json={"request_type": "takeover", "reason": f"设备{index}申请"},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(submit, [1, 2]))

    assert sum(response.status_code == 201 for response in responses) == 1
    loser = next(response for response in responses if response.status_code != 201)
    assert loser.status_code in {409, 503}
    assert loser.json()["detail"]["code"] in {"WORK_ORDER_REQUEST_EXISTS", "DATABASE_BUSY"}
    requests = client.get(f"/api/v1/work-orders/{order['order_no']}/requests", headers=headers).json()
    assert len([item for item in requests if item["status"] == "pending"]) == 1
    assert operator["id"] > 0


def test_database_lock_returns_stable_busy_error(client, monkeypatch):
    from app.api import evidence as evidence_api

    headers = admin_headers(client)

    def raise_locked(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, sqlite3.OperationalError("database is locked"))

    monkeypatch.setattr(evidence_api, "get_step", raise_locked)
    response = client.post(
        "/api/v1/evidence/work-orders/WO-NOT-CHECKED/steps/1/qr",
        headers=headers,
        json={"label_id": "LBL-1", "material_id": "MAT-1", "evidence_file_id": "FILE-1"},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATABASE_BUSY"
