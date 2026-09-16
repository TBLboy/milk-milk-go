from pathlib import Path


def test_health_reports_service_and_database(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "milk-weigh-api", "database": "ok", "version": "1.0.5"}


def test_health_initializes_sqlite_database(client, tmp_path):
    assert client.get("/api/v1/health").status_code == 200
    assert (Path(tmp_path) / "milk_weigh.sqlite3").exists()
