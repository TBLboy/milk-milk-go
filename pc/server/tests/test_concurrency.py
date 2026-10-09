"""并发正确性回归测试。

覆盖「一台 PC 后端 + 多操作员 / 多手机 / 多账号同时作业」场景下的关键不变量：

- 同一步骤被多路并发推进时，只能推进一次（CAS 乐观锁）；
- 并发提交不产生重复的确认 / 称重记录；
- 并发上传证据文件互不冲突。

并发建单唯一性的回归测试位于 ``test_work_orders.py``。
"""

import threading
from concurrent.futures import ThreadPoolExecutor


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_order(client, headers, code, name):
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": code, "name_zh": "并发回归蔗糖", "shelf_life_months": 24},
    ).json()
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={"name": name, "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]},
    ).json()
    order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()
    return material, order


def create_label(client, headers, material_id):
    response = client.post(
        "/api/v1/labels/print-batches",
        headers=headers,
        json={"material_id": material_id, "quantity": 1},
    )
    assert response.status_code == 201
    return response.json()["labels"][0]


def upload_evidence(client, headers, content=b"image"):
    response = client.post(
        "/api/v1/evidence/files",
        headers=headers,
        files={"file": ("evidence.jpg", content, "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()["file_id"]


def _run_concurrently(worker, count):
    barrier = threading.Barrier(count)

    def wrapped(index):
        barrier.wait()
        return worker(index)

    with ThreadPoolExecutor(max_workers=count) as executor:
        return list(executor.map(wrapped, range(count)))


def test_many_concurrent_qr_submissions_advance_step_once(client):
    """8 路并发提交同一步骤的二维码确认：仅 1 次推进，其余冲突，且只有 1 条确认记录。"""
    headers = admin_headers(client)
    material, order = create_order(client, headers, "CONCQR", "并发二维码产品")
    label_id = create_label(client, headers, material["material_id"])
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers).status_code == 200
    evidence_file_id = upload_evidence(client, headers, b"qr-image")
    payload = {"label_id": label_id, "material_id": material["material_id"], "evidence_file_id": evidence_file_id}

    def submit(index):
        return client.post(
            f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
            headers={**headers, "Idempotency-Key": f"qr-many-{index}"},
            json=payload,
        )

    responses = _run_concurrently(submit, 8)

    assert sum(response.status_code == 200 for response in responses) == 1
    assert all(response.status_code in {200, 409, 503} for response in responses)
    detail = client.get(f"/api/v1/work-orders/{order['order_no']}", headers=headers).json()
    step = detail["steps"][0]
    assert step["status"] == "weighing"
    assert len(step["confirmations"]) == 1
    assert step["confirmations"][0]["status"] == "passed"


def test_many_concurrent_weight_submissions_create_one_attempt(client):
    """8 路并发提交同一步骤称重：仅 1 条称重记录，步骤只完成一次。"""
    headers = admin_headers(client)
    material, order = create_order(client, headers, "CONCWT", "并发称重产品")
    label_id = create_label(client, headers, material["material_id"])
    assert client.post(f"/api/v1/work-orders/{order['order_no']}/start", headers=headers).status_code == 200
    assert client.post(
        f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/qr",
        headers={**headers, "Idempotency-Key": "weight-qr"},
        json={
            "label_id": label_id,
            "material_id": material["material_id"],
            "evidence_file_id": upload_evidence(client, headers, b"qr-image"),
        },
    ).status_code == 200
    scale_photo_file_id = upload_evidence(client, headers, b"scale-image")

    def submit(index):
        return client.post(
            f"/api/v1/evidence/work-orders/{order['order_no']}/steps/1/weight",
            headers={**headers, "Idempotency-Key": f"weight-many-{index}"},
            json={"weight_kg": 10, "scale_photo_file_id": scale_photo_file_id},
        )

    responses = _run_concurrently(submit, 8)

    assert sum(response.status_code == 200 for response in responses) == 1
    assert all(response.status_code in {200, 409, 503} for response in responses)
    detail = client.get(f"/api/v1/work-orders/{order['order_no']}", headers=headers).json()
    step = detail["steps"][0]
    assert step["status"] == "completed"
    assert len(step["weighing_attempts"]) == 1


def test_concurrent_evidence_uploads_store_distinct_files(client):
    """12 路并发上传证据文件：全部成功且 file_id 互不相同。"""
    headers = admin_headers(client)

    def upload(index):
        return client.post(
            "/api/v1/evidence/files",
            headers=headers,
            files={"file": ("evidence.jpg", f"payload-{index}".encode(), "image/jpeg")},
        )

    responses = _run_concurrently(upload, 12)

    failures = [(response.status_code, response.text[:200]) for response in responses if response.status_code != 201]
    assert not failures, f"并发上传出现失败：{failures}"
    file_ids = [response.json()["file_id"] for response in responses]
    assert len(set(file_ids)) == len(file_ids)
