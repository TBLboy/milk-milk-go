import socket
from types import SimpleNamespace

from app.core.network import build_network_snapshot


def _address(ipv4: str) -> SimpleNamespace:
    return SimpleNamespace(family=socket.AF_INET, address=ipv4)


def test_hotspot_address_is_recommended_before_physical_and_virtual_adapters():
    snapshot = build_network_snapshot(
        {
            "WLAN": [_address("10.39.32.185")],
            "Local Area Connection* 10": [_address("192.168.137.1")],
            "VMware Network Adapter VMnet1": [_address("192.168.108.1")],
        },
        {
            "WLAN": SimpleNamespace(isup=True),
            "Local Area Connection* 10": SimpleNamespace(isup=True),
            "VMware Network Adapter VMnet1": SimpleNamespace(isup=True),
        },
    )

    assert snapshot["recommended"]["ipv4"] == "192.168.137.1"
    assert snapshot["recommended"]["kind"] == "hotspot"
    assert snapshot["addresses"][-1]["name"] == "VMware Network Adapter VMnet1"


def test_virtual_adapter_is_not_recommended_when_no_physical_address_exists():
    snapshot = build_network_snapshot(
        {"VMware Network Adapter VMnet8": [_address("192.168.133.1")]},
        {"VMware Network Adapter VMnet8": SimpleNamespace(isup=True)},
    )

    assert snapshot["recommended"] is None
    assert snapshot["addresses"][0]["is_virtual"] is True


def test_network_address_endpoint_requires_admin(client):
    response = client.get("/api/v1/settings/network-addresses")
    assert response.status_code == 401


def test_network_address_endpoint_returns_detection_result(client, monkeypatch):
    from app.api import settings as settings_api

    expected = {
        "detected_at": "2026-09-13T00:00:00+00:00",
        "recommended": {"name": "WLAN", "ipv4": "192.168.137.1", "kind": "hotspot"},
        "addresses": [{"name": "WLAN", "ipv4": "192.168.137.1", "kind": "hotspot"}],
    }
    monkeypatch.setattr(settings_api, "detect_local_ipv4_addresses", lambda: expected)
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]

    response = client.get(
        "/api/v1/settings/network-addresses",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == expected
