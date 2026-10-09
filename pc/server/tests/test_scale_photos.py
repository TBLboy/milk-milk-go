"""称重多图（最多 3 张）后端回归测试。

覆盖 BL-WEIGH-PHOTO-001..008 与 DEC-056/057/058：
数量 1~3、上限 3、重复拒绝、归属校验、旧单值兼容、字段冲突、完成校验。
"""

import json
import sqlite3

from sqlalchemy import create_engine


def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def upload(client, headers, name="scale.jpg"):
    response = client.post("/api/v1/evidence/files", headers=headers, files={"file": (name, b"fake-image", "image/jpeg")})
    assert response.status_code == 201
    return response.json()["file_id"]


def setup_order(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    label = client.post("/api/v1/labels/print-batches", headers=headers, json={"material_id": material["material_id"], "quantity": 1}).json()["labels"][0]
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙奶", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}]}).json()
    order = client.post("/api/v1/work-orders", headers=headers, json={"product_id": product["id"], "target_weight_kg": 1000}).json()
    return headers, order["order_no"], material["material_id"], label


def confirm_type(client, headers, order_no, material_id, label_id):
    assert client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr/validate",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id},
    ).status_code == 200
    qr_file_id = upload(client, headers, "qr.jpg")
    assert client.post(
        f"/api/v1/evidence/work-orders/{order_no}/steps/1/qr",
        headers=headers,
        json={"label_id": label_id, "material_id": material_id, "evidence_file_id": qr_file_id},
    ).status_code == 200


def step_of(client, headers, order_no):
    detail = client.get(f"/api/v1/work-orders/{order_no}", headers=headers).json()
    return detail["steps"][0]


def submit_weight(client, headers, order_no, payload):
    return client.post(f"/api/v1/evidence/work-orders/{order_no}/steps/1/weight", headers=headers, json=payload)


def test_weight_accepts_one_to_three_photos(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    files = [upload(client, headers, f"scale{i}.jpg") for i in range(3)]

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": files})

    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    attempt = step_of(client, headers, order_no)["weighing_attempts"][0]
    assert attempt["scale_photo_file_ids"] == files
    # 兼容字段等于第一张照片
    assert attempt["scale_photo_file_id"] == files[0]


def test_weight_accepts_two_photos(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    files = [upload(client, headers, f"s{i}.jpg") for i in range(2)]

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": files})

    assert response.status_code == 200
    attempt = step_of(client, headers, order_no)["weighing_attempts"][0]
    assert attempt["scale_photo_file_ids"] == files


def test_weight_legacy_single_field_still_accepted(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    file_id = upload(client, headers)

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_id": file_id})

    assert response.status_code == 200
    attempt = step_of(client, headers, order_no)["weighing_attempts"][0]
    assert attempt["scale_photo_file_id"] == file_id
    assert attempt["scale_photo_file_ids"] == [file_id]


def test_weight_accepts_consistent_both_fields(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    file_id = upload(client, headers)

    response = submit_weight(
        client, headers, order_no,
        {"weight_kg": 10, "scale_photo_file_id": file_id, "scale_photo_file_ids": [file_id]},
    )

    assert response.status_code == 200
    assert step_of(client, headers, order_no)["weighing_attempts"][0]["scale_photo_file_ids"] == [file_id]


def test_weight_rejects_four_photos_without_partial_write(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    files = [upload(client, headers, f"p{i}.jpg") for i in range(4)]

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": files})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCALE_PHOTO_LIMIT_EXCEEDED"
    # 不部分落库
    assert step_of(client, headers, order_no)["weighing_attempts"] == []


def test_weight_rejects_duplicate_photos(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    file_id = upload(client, headers)

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": [file_id, file_id]})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCALE_PHOTO_DUPLICATED"
    assert step_of(client, headers, order_no)["weighing_attempts"] == []


def test_weight_rejects_empty_photo_list(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": []})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCALE_PHOTO_REQUIRED"


def test_weight_rejects_conflicting_photo_fields(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    first = upload(client, headers, "a.jpg")
    second = upload(client, headers, "b.jpg")

    response = submit_weight(
        client, headers, order_no,
        {"weight_kg": 10, "scale_photo_file_id": first, "scale_photo_file_ids": [second]},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SCALE_PHOTO_FIELDS_CONFLICT"
    assert step_of(client, headers, order_no)["weighing_attempts"] == []


def test_weight_rejects_photo_uploaded_by_another_operator(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    own = upload(client, headers, "own.jpg")
    client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "photo_other", "display_name": "其他操作员", "password": "operator123", "employee_no": "MH1099"},
    )
    other_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'username': 'photo_other', 'password': 'operator123'}).json()['access_token']}"
    }
    foreign = upload(client, other_headers, "foreign.jpg")

    response = submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": [own, foreign]})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SCALE_PHOTO_REQUIRED"
    assert step_of(client, headers, order_no)["weighing_attempts"] == []


def test_out_of_tolerance_with_multiple_photos_leaves_no_record(client):
    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    files = [upload(client, headers, f"t{i}.jpg") for i in range(3)]

    response = submit_weight(client, headers, order_no, {"weight_kg": 8, "scale_photo_file_ids": files})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "WEIGHT_OUT_OF_TOLERANCE"
    assert step_of(client, headers, order_no)["weighing_attempts"] == []


def test_complete_work_order_requires_evidence_photos(client):
    from app.db.models import WeighingAttempt
    from app.db.session import SessionLocal

    headers, order_no, material_id, label_id = setup_order(client)
    confirm_type(client, headers, order_no, material_id, label_id)
    file_id = upload(client, headers)
    assert submit_weight(client, headers, order_no, {"weight_kg": 10, "scale_photo_file_ids": [file_id]}).status_code == 200
    assert client.post(f"/api/v1/work-orders/{order_no}/start", headers=headers).status_code == 200

    # 构造历史异常数据：已完成的称重步骤丢失全部照片
    with SessionLocal() as db:
        attempt = db.query(WeighingAttempt).one()
        attempt.scale_photo_file_ids_json = "[]"
        attempt.scale_photo_file_id = ""
        db.commit()

    blocked = client.post(f"/api/v1/work-orders/{order_no}/complete", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "WORK_ORDER_EVIDENCE_INCOMPLETE"

    # 恢复照片后同一请求应通过，证明只有证据检查在阻塞
    with SessionLocal() as db:
        attempt = db.query(WeighingAttempt).one()
        attempt.scale_photo_file_ids_json = json.dumps([file_id])
        attempt.scale_photo_file_id = file_id
        db.commit()

    assert client.post(f"/api/v1/work-orders/{order_no}/complete", headers=headers).status_code == 200


def test_scale_photo_ids_helper_handles_legacy_and_broken_data(client):
    from app.db.models import WeighingAttempt

    legacy = WeighingAttempt(scale_photo_file_id="F1", scale_photo_file_ids_json="[]")
    assert legacy.scale_photo_ids() == ["F1"]

    multi = WeighingAttempt(scale_photo_file_id="F1", scale_photo_file_ids_json='["F1","F2","F3"]')
    assert multi.scale_photo_ids() == ["F1", "F2", "F3"]

    broken = WeighingAttempt(scale_photo_file_id="F1", scale_photo_file_ids_json="not-json")
    assert broken.scale_photo_ids() == ["F1"]

    nulled = WeighingAttempt(scale_photo_file_id="", scale_photo_file_ids_json="[]")
    assert nulled.scale_photo_ids() == []


def test_migration_backfills_existing_single_photo(tmp_path):
    from app.db.models import _migrate_weighing_attempt_columns

    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE weighing_attempts (id INTEGER PRIMARY KEY, scale_photo_file_id VARCHAR(64) NOT NULL)"
    )
    connection.execute("INSERT INTO weighing_attempts (id, scale_photo_file_id) VALUES (1, 'FILE-A')")
    connection.execute("INSERT INTO weighing_attempts (id, scale_photo_file_id) VALUES (2, 'FILE-B')")
    connection.commit()
    connection.close()

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    _migrate_weighing_attempt_columns(engine)
    # 幂等：重复执行不改变结果
    _migrate_weighing_attempt_columns(engine)
    with engine.connect() as conn:
        rows = dict(
            conn.exec_driver_sql("SELECT id, scale_photo_file_ids_json FROM weighing_attempts").fetchall()
        )
    engine.dispose()

    assert rows[1] == '["FILE-A"]'
    assert rows[2] == '["FILE-B"]'
