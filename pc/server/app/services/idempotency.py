from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import IdempotencyRecord


def request_id_from_headers(request: Request) -> str | None:
    value = request.headers.get("Idempotency-Key") or request.headers.get("X-Request-ID")
    if value is None:
        return None
    value = value.strip()
    if not value or len(value) > 128 or any(ord(char) < 32 for char in value):
        raise HTTPException(
            status_code=422,
            detail={"code": "IDEMPOTENCY_KEY_INVALID", "message": "请求幂等标识无效"},
        )
    return value


def _payload_hash(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _replay(record: IdempotencyRecord) -> JSONResponse:
    try:
        payload = json.loads(record.response_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "IDEMPOTENCY_RESPONSE_CORRUPT", "message": "幂等请求历史结果损坏"},
        ) from exc
    return JSONResponse(status_code=record.status_code, content=payload)


def execute_idempotent(
    db: Session,
    request: Request,
    *,
    user_id: int,
    endpoint: str,
    payload: Any,
    operation: Callable[[], dict],
    status_code: int = 200,
) -> dict | JSONResponse:
    request_id = request_id_from_headers(request)
    if request_id is None:
        result = operation()
        db.commit()
        return result

    digest = _payload_hash(payload)
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.request_id == request_id,
        )
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": "请求幂等标识已用于其他参数"},
            )
        return _replay(existing)

    try:
        result = operation()
        db.add(
            IdempotencyRecord(
                user_id=user_id,
                endpoint=endpoint,
                request_id=request_id,
                request_hash=digest,
                status_code=status_code,
                response_json=json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
            )
        )
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.endpoint == endpoint,
                IdempotencyRecord.request_id == request_id,
            )
        )
        if existing is None:
            raise
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409,
                detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": "请求幂等标识已用于其他参数"},
            )
        return _replay(existing)
    except Exception:
        db.rollback()
        raise
