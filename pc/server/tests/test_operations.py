def admin_headers(client):
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_backup_creates_record(client):
    headers = admin_headers(client)
    client.get("/api/v1/health")
    response = client.post("/api/v1/operations/backups", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert client.get("/api/v1/operations/backups", headers=headers).json()[0]["status"] == "success"
