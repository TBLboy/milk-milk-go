import ipaddress
import socket
from datetime import datetime, timezone
from typing import Any

import psutil


HOTSPOT_MARKERS = (
    "hosted",
    "hotspot",
    "wi-fi direct",
    "wifi direct",
    "移动热点",
    "本地连接*",
)
VIRTUAL_MARKERS = (
    "vmware",
    "virtualbox",
    "hyper-v",
    "vethernet",
    "loopback",
    "docker",
    "br-",
    "virbr",
    "veth",
    "wsl",
    "npcap",
    "tap-windows",
    "tailscale",
    "zerotier",
)
WIRELESS_MARKERS = (
    "wlan",
    "wi-fi",
    "wifi",
    "wireless",
    "无线局域网",
    "无线网络",
)
ETHERNET_MARKERS = (
    "ethernet",
    "local area connection",
    "以太网",
    "本地连接",
)


def _interface_kind(name: str, ipv4: str) -> str:
    normalized = name.casefold()
    if ipv4 == "192.168.137.1" or any(marker in normalized for marker in HOTSPOT_MARKERS):
        return "hotspot"
    if any(marker in normalized for marker in VIRTUAL_MARKERS):
        return "virtual"
    if normalized.startswith("wl") or any(marker in normalized for marker in WIRELESS_MARKERS):
        return "wireless"
    if normalized.startswith(("en", "eth")) or any(marker in normalized for marker in ETHERNET_MARKERS):
        return "ethernet"
    return "other"


def _address_score(name: str, ipv4: str, is_up: bool, kind: str) -> int:
    if not is_up:
        return -1
    if ipv4 == "192.168.137.1":
        return 1000
    if kind == "hotspot":
        return 950
    if kind == "wireless":
        return 800
    if kind == "ethernet":
        return 750
    if kind == "other":
        return 600
    if kind == "virtual":
        return 200
    return 0


def build_network_snapshot(
    interfaces: dict[str, list[Any]],
    interface_stats: dict[str, Any],
) -> dict[str, Any]:
    addresses: list[dict[str, Any]] = []

    for name, entries in interfaces.items():
        stats = interface_stats.get(name)
        is_up = bool(getattr(stats, "isup", False))
        for entry in entries:
            if getattr(entry, "family", None) != socket.AF_INET:
                continue

            raw_address = str(getattr(entry, "address", "")).split("%", 1)[0].strip()
            try:
                address = ipaddress.IPv4Address(raw_address)
            except ipaddress.AddressValueError:
                continue
            if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
                continue

            ipv4 = str(address)
            kind = _interface_kind(name, ipv4)
            score = _address_score(name, ipv4, is_up, kind)
            addresses.append(
                {
                    "name": name,
                    "ipv4": ipv4,
                    "kind": kind,
                    "is_up": is_up,
                    "is_virtual": kind == "virtual",
                    "is_hotspot": kind == "hotspot",
                    "score": score,
                }
            )

    addresses.sort(key=lambda item: (-item["score"], item["name"].casefold(), item["ipv4"]))
    recommended = next((item for item in addresses if item["score"] >= 600), None)

    for item in addresses:
        item.pop("score", None)
        item["is_recommended"] = bool(recommended and item["ipv4"] == recommended["ipv4"] and item["name"] == recommended["name"])

    public_recommended = None
    if recommended is not None:
        public_recommended = {
            key: value
            for key, value in recommended.items()
            if key != "score"
        }
        public_recommended["is_recommended"] = True

    return {
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "recommended": public_recommended,
        "addresses": addresses,
    }


def detect_local_ipv4_addresses() -> dict[str, Any]:
    try:
        return build_network_snapshot(psutil.net_if_addrs(), psutil.net_if_stats())
    except Exception as exc:
        raise RuntimeError("无法读取本机网络地址，请检查系统网络适配器状态") from exc
