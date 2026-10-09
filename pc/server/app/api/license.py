"""授权状态与解锁接口（BL-LICENSE-002/005/007/011/012）。

- ``GET /license/status``：App 与 PC 共用；任何已登录用户可读（操作员也要看到倒计时）。
- ``POST /license/unlock``：仅管理员；验签通过立即恢复，失败不改状态且写审计。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import current_user, require_admin
from app.db.models import User
from app.db.session import get_db
from app.license_runtime import get_license_service
from app.services.audit import write_audit
from milk_license import codec, state

router = APIRouter(prefix="/license", tags=["license"])


class UnlockInput(BaseModel):
    code: str = Field(min_length=1, max_length=8192)


def _status_payload(service) -> dict:
    result = service.status(force=True)
    return {
        "mode": result.mode,
        "source": result.source,
        "licensee": result.licensee,
        "issued_at": result.issued_at,
        "expires_at": result.expires_at,
        "deadline": result.deadline,
        "days_remaining": result.days_remaining,
        "grace_days_remaining": result.grace_days_remaining,
        "warn": result.warn,
        "warn_node": result.warn_node,
        "warn_days": state.WARN_DAYS,
        "warn_nodes": list(state.WARN_NODES),
        "grace_days": state.GRACE_DAYS,
        "trial_months": state.TRIAL_MONTHS,
        "clock_rollback_detected": result.clock_rollback_detected,
        "clock_anomaly_detected": result.clock_anomaly_detected,
        "max_forward_jump_days": state.MAX_FORWARD_JUMP_DAYS,
    }


@router.get("/status")
def read_license_status(_: User = Depends(current_user)) -> dict:
    return _status_payload(get_license_service())


@router.post("/unlock")
def unlock_license(
    body: UnlockInput,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    service = get_license_service()
    try:
        service.unlock(body.code)
    except codec.LicenseError as exc:
        write_audit(
            db,
            actor_id=user.id,
            action="license.unlock",
            resource_type="license",
            result="rejected",
            detail={"reason": str(exc)},
        )
        db.commit()
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "LICENSE_CODE_INVALID", "message": str(exc)},
        ) from exc

    payload = _status_payload(service)
    write_audit(
        db,
        actor_id=user.id,
        action="license.unlock",
        resource_type="license",
        result="success",
        detail={"licensee": payload["licensee"], "expires_at": payload["expires_at"]},
    )
    db.commit()
    return payload
