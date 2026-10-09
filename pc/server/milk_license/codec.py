"""授权串（解锁码）编解码。

格式：``base64url(canonical_json_payload) + "." + base64url(signature)``

- payload 为规范化 JSON（键排序、无多余空格），保证签名可复现。
- 私钥只用于开发方签发（``issue_license``），交付物只使用 ``decode_license`` 验签。
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from milk_license import ed25519

PAYLOAD_VERSION = 1
REQUIRED_FIELDS = ("v", "licensee", "issued_at", "expires_at", "level")


class LicenseError(ValueError):
    """授权串无效（格式错误、字段缺失或验签失败）。"""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise LicenseError(f"字段 {field} 必须是非空字符串")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise LicenseError(f"字段 {field} 不是合法时间：{value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def issue_license(payload: dict[str, Any], seed: bytes) -> str:
    """开发方签发：用私钥种子对规范化 payload 签名，返回解锁码字符串。"""
    body = _canonical(payload)
    public = ed25519.public_key(seed)
    signature = ed25519.sign(body, seed, public)
    return f"{_b64encode(body)}.{_b64encode(signature)}"


def decode_license(code: str, public: bytes) -> dict[str, Any]:
    """验签并解析授权串；任何问题都抛 LicenseError。"""
    if not isinstance(code, str):
        raise LicenseError("解锁码必须是字符串")
    parts = code.strip().split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise LicenseError("解锁码格式不正确")
    try:
        body = _b64decode(parts[0])
        signature = _b64decode(parts[1])
    except (ValueError, TypeError) as exc:
        raise LicenseError("解锁码不是合法的 Base64 编码") from exc
    if not ed25519.verify(signature, body, public):
        raise LicenseError("解锁码验签失败（内容被改动或来源不可信）")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseError("解锁码内容不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise LicenseError("解锁码内容必须是 JSON 对象")
    for field in REQUIRED_FIELDS:
        if field not in payload:
            raise LicenseError(f"解锁码缺少字段：{field}")
    if payload["v"] != PAYLOAD_VERSION:
        raise LicenseError(f"不支持的授权版本：{payload['v']}")
    _parse_time(payload["issued_at"], "issued_at")
    _parse_time(payload["expires_at"], "expires_at")
    return payload


def expires_at(payload: dict[str, Any]) -> datetime:
    return _parse_time(payload["expires_at"], "expires_at")


def issued_at(payload: dict[str, Any]) -> datetime:
    return _parse_time(payload["issued_at"], "issued_at")


def format_license(payload: dict[str, Any]) -> str:
    """面向人/日志的单行摘要。"""
    return (
        f"客户={payload.get('licensee')} "
        f"签发={payload.get('issued_at')} "
        f"到期={payload.get('expires_at')} "
        f"级别={payload.get('level')}"
    )
