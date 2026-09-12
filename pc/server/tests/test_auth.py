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
