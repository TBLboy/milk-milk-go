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
    assert registered.json()["employee_no"] == ""
    login = client.post("/api/v1/auth/login", json={"username": "operator01", "password": "operator123"})
    assert login.status_code == 403

    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    user_id = registered.json()["id"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    missing_employee_no = client.post(f"/api/v1/auth/users/{user_id}/approve", headers=admin_headers)
    assert missing_employee_no.status_code == 422
    assert missing_employee_no.json()["detail"]["code"] == "EMPLOYEE_NO_REQUIRED"
    profile = client.patch(
        f"/api/v1/auth/users/{user_id}/profile",
        headers=admin_headers,
        json={"employee_no": "MH0001"},
    )
    assert profile.status_code == 200
    assert profile.json()["user"]["employee_no"] == "MH0001"
    assert client.post(f"/api/v1/auth/users/{user_id}/approve", headers=admin_headers).status_code == 200
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
        json={"username": "desktop_operator", "display_name": "普通操作员", "password": "operator123", "employee_no": "MH0002"},
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
    assert any(item["action"] == "admin_password.recovered" for item in logs["items"])


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


def test_operator_registration_accepts_optional_employee_no(client):
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "username": "employee_registration",
            "display_name": "自主注册员工",
            "employee_no": " MH0300 ",
            "password": "operator123",
        },
    )
    assert registered.status_code == 201
    assert registered.json()["employee_no"] == "MH0300"

    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "username": "employee_registration_2",
            "display_name": "重复工号员工",
            "employee_no": "MH0300",
            "password": "operator123",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "EMPLOYEE_NO_EXISTS"


def test_admin_create_user_and_reset_password(client):
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    created = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "operator98", "display_name": "重置测试", "password": "password123", "phone": "13800000000", "employee_no": "MH0003"},
    )
    assert created.status_code == 201
    user = created.json()["user"]
    assert user["status"] == "active"
    assert user["phone"] == "13800000000"
    assert user["employee_no"] == "MH0003"
    assert "id_card" not in user
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
        json={"username": "operator99", "display_name": "资料测试", "password": "password123", "employee_no": "MH0004"},
    ).json()["user"]
    user_login = client.post("/api/v1/auth/login", json={"username": "operator99", "password": "password123"})
    token = user_login.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]
    assert me["employee_no"] == "MH0004"
    assert "id_card" not in me
    updated = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "资料测试二", "phone": "13900000000"},
    )
    assert updated.status_code == 200
    assert updated.json()["user"]["display_name"] == "资料测试二"
    assert updated.json()["user"]["employee_no"] == "MH0004"
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


def test_employee_no_is_required_and_unique(client):
    admin = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {admin}"}
    missing = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "no_employee", "display_name": "无工号", "password": "password123"},
    )
    assert missing.status_code == 422
    first = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "employee_one", "display_name": "员工一", "password": "password123", "employee_no": "MH0100"},
    )
    assert first.status_code == 201
    duplicate = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "employee_two", "display_name": "员工二", "password": "password123", "employee_no": "MH0100"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "EMPLOYEE_NO_EXISTS"


def test_operator_cannot_change_own_employee_no(client):
    admin = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    created = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin}"},
        json={"username": "readonly_employee", "display_name": "只读工号", "password": "password123", "employee_no": "MH0200"},
    ).json()["user"]
    token = client.post("/api/v1/auth/login", json={"username": "readonly_employee", "password": "password123"}).json()["access_token"]
    response = client.patch(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "只读工号二", "employee_no": "MH9999"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["employee_no"] == "MH0200"


def test_user_schema_migration_drops_id_card_and_adds_unique_employee_no(tmp_path):
    import sqlite3

    from sqlalchemy import create_engine

    from app.db.models import _migrate_user_account_columns

    database = tmp_path / "legacy-users.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, id_card VARCHAR(64))")
        connection.execute("INSERT INTO users (id, id_card) VALUES (1, '110101199001011234')")
        connection.commit()

    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        _migrate_user_account_columns(engine)
        with engine.connect() as connection:
            columns = {row[1] for row in connection.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
            indexes = connection.exec_driver_sql("PRAGMA index_list(users)").fetchall()
    finally:
        engine.dispose()

    assert "employee_no" in columns
    assert "id_card" not in columns
    assert any(row[1] == "ix_users_employee_no" and row[2] == 1 for row in indexes)
