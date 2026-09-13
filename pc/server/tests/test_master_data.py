def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_operator_cannot_read_master_data(client):
    admin_headers(client)
    token_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin = token_resp.json()["access_token"]
    client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin}"},
        json={"username": "operator01", "display_name": "李师傅", "password": "operator123", "employee_no": "MH1004"},
    )
    token = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"}).json()["access_token"]
    assert client.get("/api/v1/master-data/materials", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_admin_can_create_material_and_product_recipe(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "name_en": "Sucrose", "shelf_life_months": 24, "image_file_ids": ["file-a", "file-b"]})
    assert material.status_code == 201
    assert "enabled" not in material.json()
    material_id = material.json()["material_id"]
    product = client.post("/api/v1/master-data/products", headers=headers, json={"name": "高钙纯牛奶 1L", "items": [{"material_id": material_id, "quantity_per_ton_kg": 12.5}]})
    assert product.status_code == 201
    assert product.json()["items"][0]["quantity_per_ton_kg"] == 12.5


def test_recipe_accepts_legacy_material_enabled_flag(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "A1", "name_zh": "蔗糖", "shelf_life_months": 24}).json()
    from app.db.models import Material
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        row = db.query(Material).filter(Material.material_id == material["material_id"]).one()
        row.enabled = False
        db.commit()

    response = client.post("/api/v1/master-data/products", headers=headers, json={"name": "测试产品", "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 1}]})
    assert response.status_code == 201
    assert response.json()["items"][0]["material_id"] == material["material_id"]


def test_product_can_store_optional_image(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "IMG01", "name_zh": "带图辅料", "shelf_life_months": 12}).json()
    product = client.post("/api/v1/master-data/products", headers=headers, json={
        "name": "带图产品",
        "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 2}],
        "image_file_id": "FILE-product-image",
    })
    assert product.status_code == 201
    assert product.json()["image_file_id"] == "FILE-product-image"
    listed = client.get("/api/v1/master-data/products", headers=headers).json()
    target = next(item for item in listed if item["name"] == "带图产品")
    assert target["image_file_id"] == "FILE-product-image"


def test_product_recipe_can_be_edited(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "EDIT01", "name_zh": "可编辑辅料", "shelf_life_months": 12}).json()
    other = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "EDIT02", "name_zh": "另一辅料", "shelf_life_months": 12}).json()
    created = client.post("/api/v1/master-data/products", headers=headers, json={
        "name": "原始配方",
        "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 5}],
    })
    assert created.status_code == 201
    product_id = created.json()["id"]
    updated = client.put(f"/api/v1/master-data/products/{product_id}", headers=headers, json={
        "name": "编辑后配方",
        "items": [
            {"material_id": material["material_id"], "quantity_per_ton_kg": 7.5},
            {"material_id": other["material_id"], "quantity_per_ton_kg": 3},
        ],
        "image_file_id": "FILE-edited-image",
    })
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "编辑后配方"
    assert body["image_file_id"] == "FILE-edited-image"
    assert body["recipe_version"] == 2
    quantities = {item["material_id"]: item["quantity_per_ton_kg"] for item in body["items"]}
    assert quantities[material["material_id"]] == 7.5
    assert quantities[other["material_id"]] == 3
    listed = client.get("/api/v1/master-data/products", headers=headers).json()
    target = next(item for item in listed if item["id"] == product_id)
    assert target["name"] == "编辑后配方"
    assert len(target["items"]) == 2


def test_recipe_history_only_versions_ingredient_changes(client):
    headers = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "VER01", "name_zh": "版本辅料", "shelf_life_months": 12},
    ).json()
    created = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={
            "name": "版本测试产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 5}],
        },
    ).json()

    initial = client.get(
        f"/api/v1/master-data/products/{created['id']}/recipe-versions",
        headers=headers,
    )
    assert initial.status_code == 200
    assert len(initial.json()) == 1
    assert initial.json()[0]["version"] == 1
    assert initial.json()[0]["is_current"] is True
    assert initial.json()[0]["items"][0]["quantity_per_ton_kg"] == 5
    assert initial.json()[0]["created_by"]["username"] == "admin"

    renamed = client.put(
        f"/api/v1/master-data/products/{created['id']}",
        headers=headers,
        json={
            "name": "改名但配方不变",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 5}],
            "image_file_id": "FILE-version-image",
        },
    )
    assert renamed.status_code == 200
    assert renamed.json()["recipe_version"] == 1
    assert len(client.get(
        f"/api/v1/master-data/products/{created['id']}/recipe-versions",
        headers=headers,
    ).json()) == 1

    changed = client.put(
        f"/api/v1/master-data/products/{created['id']}",
        headers=headers,
        json={
            "name": "改名但配方不变",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 7.5}],
            "image_file_id": "FILE-version-image",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["recipe_version"] == 2

    history = client.get(
        f"/api/v1/master-data/products/{created['id']}/recipe-versions",
        headers=headers,
    ).json()
    assert [item["version"] for item in history] == [2, 1]
    assert history[0]["is_current"] is True
    assert history[0]["items"][0]["quantity_per_ton_kg"] == 7.5
    assert history[1]["is_current"] is False
    assert history[1]["items"][0]["quantity_per_ton_kg"] == 5


def test_work_order_keeps_recipe_snapshot_after_new_version(client):
    headers = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "VERWO", "name_zh": "快照辅料", "shelf_life_months": 12},
    ).json()
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={
            "name": "快照版本产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 10}],
        },
    ).json()
    old_order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()

    updated = client.put(
        f"/api/v1/master-data/products/{product['id']}",
        headers=headers,
        json={
            "name": "快照版本产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 20}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["recipe_version"] == 2

    old_detail = client.get(
        f"/api/v1/work-orders/{old_order['order_no']}",
        headers=headers,
    ).json()
    assert old_detail["steps"][0]["required_weight_kg"] == 10
    new_order = client.post(
        "/api/v1/work-orders",
        headers=headers,
        json={"product_id": product["id"], "target_weight_kg": 1000},
    ).json()
    assert new_order["steps"][0]["required_weight_kg"] == 20


def test_operator_cannot_read_recipe_versions(client):
    headers = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "VERPERM", "name_zh": "权限辅料", "shelf_life_months": 12},
    ).json()
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={
            "name": "权限版本产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 1}],
        },
    ).json()
    client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "username": "version_operator",
            "display_name": "版本操作员",
            "password": "operator123",
            "employee_no": "MH-VERSION",
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "version_operator", "password": "operator123"},
    ).json()["access_token"]
    response = client.get(
        f"/api/v1/master-data/products/{product['id']}/recipe-versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_recipe_version_backfill_for_existing_current_recipe(client):
    headers = admin_headers(client)
    material = client.post(
        "/api/v1/master-data/materials",
        headers=headers,
        json={"material_code": "VERMIG", "name_zh": "迁移辅料", "shelf_life_months": 12},
    ).json()
    product = client.post(
        "/api/v1/master-data/products",
        headers=headers,
        json={
            "name": "迁移版本产品",
            "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 3}],
        },
    ).json()

    from app.db.models import RecipeVersion, initialize_database
    from app.db.session import SessionLocal

    with SessionLocal.begin() as db:
        for version in db.query(RecipeVersion).all():
            db.delete(version)
    initialize_database()

    history = client.get(
        f"/api/v1/master-data/products/{product['id']}/recipe-versions",
        headers=headers,
    ).json()
    assert len(history) == 1
    assert history[0]["version"] == 1
    assert history[0]["created_by"] is None
    assert history[0]["items"][0]["material_id"] == material["material_id"]


def test_product_recipe_can_be_enabled_and_disabled(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "ACTIVE01", "name_zh": "启停辅料", "shelf_life_months": 12}).json()
    created = client.post("/api/v1/master-data/products", headers=headers, json={
        "name": "启停配方",
        "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 2}],
    }).json()
    assert created["enabled"] is True
    assert created["recipe_enabled"] is True
    disabled = client.patch(f"/api/v1/master-data/products/{created['id']}/active", headers=headers, json={"is_active": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["recipe_enabled"] is False
    enabled = client.patch(f"/api/v1/master-data/products/{created['id']}/active", headers=headers, json={"is_active": True})
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["recipe_enabled"] is True


def test_product_recipe_can_be_deleted(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "DELETE01", "name_zh": "删除辅料", "shelf_life_months": 12}).json()
    created = client.post("/api/v1/master-data/products", headers=headers, json={
        "name": "待删除配方",
        "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 3}],
    }).json()
    deleted = client.delete(f"/api/v1/master-data/products/{created['id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    listed = client.get("/api/v1/master-data/products", headers=headers).json()
    assert all(item["id"] != created["id"] for item in listed)
    missing = client.delete(f"/api/v1/master-data/products/{created['id']}", headers=headers)
    assert missing.status_code == 404


def test_material_can_be_edited_and_images_replaced(client):
    headers = admin_headers(client)
    created = client.post("/api/v1/master-data/materials", headers=headers, json={
        "material_code": "EDIT_MAT",
        "name_zh": "旧名称",
        "name_en": "Old Name",
        "shelf_life_months": 24,
        "image_file_ids": ["old-one", "old-two"],
    }).json()
    updated = client.put(f"/api/v1/master-data/materials/{created['material_id']}", headers=headers, json={
        "material_code": "EDIT_MAT2",
        "name_zh": "新名称",
        "name_en": "New Name",
        "shelf_life_months": 36,
        "image_file_ids": ["new-one"],
    })
    assert updated.status_code == 200
    body = updated.json()
    assert body["material_code"] == "EDIT_MAT2"
    assert body["name_zh"] == "新名称"
    assert body["name_en"] == "New Name"
    assert body["shelf_life_months"] == 36
    assert [item["file_id"] for item in body["images"]] == ["new-one"]

    same_code = client.put(f"/api/v1/master-data/materials/{created['material_id']}", headers=headers, json={
        "material_code": "EDIT_MAT2",
        "name_zh": "重名",
        "shelf_life_months": 12,
    })
    assert same_code.status_code == 200
    assert same_code.json()["material_code"] == "EDIT_MAT2"

    other = client.post("/api/v1/master-data/materials", headers=headers, json={
        "material_code": "EDIT_MAT_OTHER",
        "name_zh": "其他辅料",
        "shelf_life_months": 12,
    }).json()
    duplicate = client.put(f"/api/v1/master-data/materials/{other['material_id']}", headers=headers, json={
        "material_code": "EDIT_MAT2",
        "name_zh": "冲突辅料",
        "shelf_life_months": 12,
    })
    assert duplicate.status_code == 409


def test_unreferenced_material_can_be_deleted(client):
    headers = admin_headers(client)
    created = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "DELETE_MAT", "name_zh": "待删除", "shelf_life_months": 12}).json()
    deleted = client.delete(f"/api/v1/master-data/materials/{created['material_id']}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    listed = client.get("/api/v1/master-data/materials", headers=headers).json()
    assert all(item["material_id"] != created["material_id"] for item in listed)
    assert client.delete(f"/api/v1/master-data/materials/{created['material_id']}", headers=headers).status_code == 404


def test_material_in_recipe_cannot_be_deleted(client):
    headers = admin_headers(client)
    material = client.post("/api/v1/master-data/materials", headers=headers, json={"material_code": "INUSE_MAT", "name_zh": "配方引用", "shelf_life_months": 12}).json()
    client.post("/api/v1/master-data/products", headers=headers, json={
        "name": "引用辅料配方",
        "items": [{"material_id": material["material_id"], "quantity_per_ton_kg": 2}],
    })
    deleted = client.delete(f"/api/v1/master-data/materials/{material['material_id']}", headers=headers)
    assert deleted.status_code == 409
    assert deleted.json()["detail"]["code"] == "MATERIAL_IN_USE"
