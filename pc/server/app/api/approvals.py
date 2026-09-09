from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import TypeConfirmation, User, WorkOrderStep, WorkOrder
from app.db.session import get_db

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("")
def list_pending_approvals(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    # Returns pending photo approvals and any takeover/cancellation requests
    items = []
    # 1. Photo confirmations pending
    photo_query = (
        select(TypeConfirmation, WorkOrderStep, WorkOrder)
        .join(WorkOrderStep, TypeConfirmation.work_order_step_id == WorkOrderStep.id)
        .join(WorkOrder, WorkOrderStep.work_order_id == WorkOrder.id)
        .where(TypeConfirmation.status == "pending")
        .order_by(TypeConfirmation.id.desc())
    )
    for conf, step, order in db.execute(photo_query).all():
        items.append({
            "id": f"AP-PHOTO-{conf.id}",
            "confirmation_id": conf.id,
            "type": "photo",
            "title": f"拍照放行申请 · {step.material_name_snapshot}",
            "description": f"工单 {order.order_no} · 步骤 {step.step_no}（{step.material_code_snapshot}）- 理由: {conf.reason or '现场标签无法识别'}",
            "order_no": order.order_no,
            "step_no": step.step_no,
            "file_id": conf.evidence_file_id,
            "time": conf.created_at.strftime("%H:%M") if conf.created_at else "刚刚",
            "status": "pending",
        })
    return items


@router.post("/{confirmation_id}/reject")
def reject_photo_confirmation(confirmation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED", "message": "需要管理员权限"})
    confirmation = db.get(TypeConfirmation, confirmation_id)
    if confirmation is None:
        raise HTTPException(status_code=404, detail={"code": "CONFIRMATION_NOT_FOUND", "message": "申请不存在"})
    if confirmation.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "CONFIRMATION_STATE_CONFLICT", "message": "申请已处理"})
    confirmation.status = "rejected"
    confirmation.decided_by = user.id
    db.commit()
    return {"status": "rejected", "message": "已驳回放行申请"}
