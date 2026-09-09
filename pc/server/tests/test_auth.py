def test_admin_is_seeded_and_can_login(client):
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
    assert response.json()["user"]["must_change_password"] is True


def test_operator_registration_and_admin_protection(client):
    registered = client.post("/api/v1/auth/register", json={"username": "operator01", "display_name": "李师傅", "password": "operator123"})
    assert registered.status_code == 201
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
