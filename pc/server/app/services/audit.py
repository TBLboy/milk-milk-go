from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog


SENSITIVE_KEYWORDS = {
    "authorization",
    "credential",
    "password",
    "secret",
    "smtp_password",
    "token",
}
REDACTED = "[REDACTED]"


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def sanitize_audit_detail(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_key(key) else sanitize_audit_detail(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_audit_detail(item) for item in value]
    return value


def write_audit(
    db: Session,
    *,
    actor_id: int | None = None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    result: str = "success",
    work_order_no: str | None = None,
    detail: Mapping[str, Any] | list[Any] | None = None,
) -> AuditLog:
    if result not in {"success", "failure", "rejected"}:
        raise ValueError(f"unsupported audit result: {result}")
    detail_json = (
        json.dumps(
            sanitize_audit_detail(detail),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        if detail is not None
        else None
    )
    record = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        result=result,
        work_order_no=work_order_no,
        detail_json=detail_json,
    )
    db.add(record)
    return record
