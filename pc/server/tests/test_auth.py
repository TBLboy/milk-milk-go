def test_admin_is_seeded_and_can_login(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert response.json()["user"]["must_change_password"] is True


def test_operator_registration_and_admin_protection(client):
    registered = client.post("/api/v1/auth/register", json={"username": "operator01", "display_name": "李师傅", "password": "operator123"})
    assert registered.status_code == 201
    assert registered.json()["status"] == "pending"
    assert registered.json()["submitted"] is True
    login = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"})
    assert login.status_code == 403

    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    user_id = registered.json()["id"]
    assert client.post(f"/api/v1/auth/users/{user_id}/approve", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    login = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"})
    token = login.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_operator_cannot_login_to_admin_portal(client):
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "desktop_operator", "display_name": "普通操作员", "password": "operator123"},
    )

    assert client.post(
        "/api/v1/auth/login",
        json={"username": "desktop_operator", "password": "operator123"},
    ).status_code == 200
    response = client.post(
        "/api/v1/auth/admin/login",
        json={"username": "desktop_operator", "password": "operator123"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_PORTAL_REQUIRED"

    admin_response = client.post(
        "/api/v1/auth/admin/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["user"]["role"] == "admin"


def test_admin_recovery_resets_password_and_invalidates_old_session(client, monkeypatch):
    from app.core.config import get_settings
    from app.core.security import hash_password

    recovery_password = "recovery-test-password"
    monkeypatch.setenv("MILK_ADMIN_RECOVERY_SECRET_HASH", hash_password(recovery_password))
    get_settings.cache_clear()

    old_login = client.post("/api/v1/auth/admin/login", json={"username": "admin", "password": "admin123"})
    old_token = old_login.json()["access_token"]

    recovered = client.post(
        "/api/v1/auth/admin/recover",
        json={"recovery_password": recovery_password},
    )
    assert recovered.status_code == 200
    result = recovered.json()
    assert result["username"] == "admin"
    assert result["must_change_password"] is True
    assert len(result["temporary_password"]) == 10

    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/admin/login",
        json={"username": "admin", "password": "admin123"},
    ).status_code == 401

    new_login = client.post(
        "/api/v1/auth/admin/login",
        json={"username": "admin", "password": result["temporary_password"]},
    )
    assert new_login.status_code == 200
    new_token = new_login.json()["access_token"]
    logs = client.get(
        "/api/v1/operations/audit-logs",
        headers={"Authorization": f"Bearer {new_token}"},
    ).json()
    assert any(item["action"] == "admin_password.recovered" for item in logs)


def test_admin_recovery_is_rate_limited(client, monkeypatch):
    from app.core.config import get_settings
    from app.core.security import hash_password

    recovery_password = "recovery-test-password"
    monkeypatch.setenv("MILK_ADMIN_RECOVERY_SECRET_HASH", hash_password(recovery_password))
    get_settings.cache_clear()

    for _ in range(4):
        response = client.post(
            "/api/v1/auth/admin/recover",
            json={"recovery_password": "wrong-password"},
        )
        assert response.status_code == 401

    locked = client.post(
        "/api/v1/auth/admin/recover",
        json={"recovery_password": "wrong-password"},
    )
    assert locked.status_code == 429
    assert locked.json()["detail"]["code"] == "ADMIN_RECOVERY_LOCKED"

    assert client.post(
        "/api/v1/auth/admin/recover",
        json={"recovery_password": recovery_password},
    ).status_code == 429


def test_duplicate_registration_is_rejected(client):
    body = {"username": "operator01", "display_name": "李师傅", "password": "operator123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=body)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "USERNAME_EXISTS"


def test_admin_create_user_and_reset_password(client):
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "operator98", "display_name": "重置测试", "password": "password123", "phone": "13800000000"},
    )
    assert created.status_code == 201
    user = created.json()["user"]
    assert user["status"] == "active"
    assert user["phone"] == "13800000000"
    reset = client.post(f"/api/v1/auth/users/{user['id']}/reset-password", headers=headers)
    assert reset.status_code == 200
    reset_password = reset.json()["temporary_password"]
    assert len(reset_password) == 10
    assert reset.json()["must_change_password"] is True
    user_login = client.post("/api/v1/auth/login", json={"username": "operator98", "password": reset_password})
    assert user_login.status_code == 200
    assert user_login.json()["user"]["must_change_password"] is True


def test_user_profile_and_change_password(client):
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    created = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"username": "operator99", "display_name": "资料测试", "password": "password123", "id_card": "110101199001011234"},
    ).json()["user"]
    user_login = client.post("/api/v1/auth/login", json={"username": "operator99", "password": "password123"})
    token = user_login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    assert me["id_card"] == "110101199001011234"
    updated = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "资料测试二", "phone": "13900000000"},
    )
    assert updated.status_code == 200
    assert updated.json()["user"]["display_name"] == "资料测试二"
    changed = client.post(
        "/api/v1/auth/me/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "password123", "new_password": "newpassword123"},
    )
    assert changed.status_code == 200
    bad_old = client.post(
        "/api/v1/auth/me/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
    )
    assert bad_old.status_code == 422
    new_login = client.post("/api/v1/auth/login", json={"username": "operator99", "password": "newpassword123"})
    assert new_login.status_code == 200
    assert client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200
    assert created["id"] == me["id"]
