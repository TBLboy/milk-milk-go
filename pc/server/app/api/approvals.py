from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.db.models import TypeConfirmation, User, WorkOrder, WorkOrderRequest, WorkOrderStep
from app.db.session import get_db
from app.services.audit import write_audit

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("")
def list_pending_approvals(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    # Returns pending work orders, photo approvals, user registrations and order requests.
    items = []
    user_query = select(User).where(User.status == "pending").order_by(User.id.desc())
    for pending_user in db.scalars(user_query).all():
        items.append({
            "id": f"AP-USER-{pending_user.id}",
            "user_id": pending_user.id,
            "type": "register",
            "title": f"新账号注册申请 · {pending_user.display_name}",
            "description": f"账号 {pending_user.username} · 等待管理员审批",
            "order_no": None,
            "step_no": None,
            "file_id": None,
            "time": pending_user.created_at.strftime("%H:%M") if pending_user.created_at else "刚刚",
            "status": "pending",
        })
    pending_order_query = (
        select(WorkOrder, User)
        .join(User, WorkOrder.created_by == User.id)
        .where(WorkOrder.status == "pending_approval")
        .order_by(WorkOrder.created_at.desc())
    )
    for order, creator in db.execute(pending_order_query).all():
        items.append({
            "id": f"AP-WO-{order.order_no}",
            "order_id": order.id,
            "type": "work_order",
            "title": f"工单审批 · {order.product_name_snapshot}",
            "description": f"工单 {order.order_no} · 申请人 {creator.display_name} · 目标 {order.target_weight_kg:g}kg",
            "order_no": order.order_no,
            "step_no": None,
            "file_id": None,
            "time": order.created_at.strftime("%H:%M") if order.created_at else "刚刚",
            "status": "pending",
        })
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
    request_query = (
        select(WorkOrderRequest, WorkOrder, User)
        .join(WorkOrder, WorkOrderRequest.work_order_id == WorkOrder.id)
        .join(User, WorkOrderRequest.requested_by == User.id)
        .where(WorkOrderRequest.status == "pending")
        .order_by(WorkOrderRequest.id.desc())
    )
    type_titles = {
        "takeover": "工单接管申请",
        "cancel": "工单撤销申请",
        "delete": "历史工单删除申请",
    }
    for request, order, requester in db.execute(request_query).all():
        items.append({
            "id": f"AP-REQ-{request.id}",
            "request_id": request.id,
            "type": request.request_type,
            "title": f"{type_titles.get(request.request_type, '工单申请')} · {order.product_name_snapshot}",
            "description": f"工单 {order.order_no} · 申请人 {requester.display_name} - 理由: {request.reason}",
            "order_no": order.order_no,
            "step_no": None,
            "file_id": None,
            "time": request.created_at.strftime("%H:%M") if request.created_at else "刚刚",
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
    step = db.get(WorkOrderStep, confirmation.work_order_step_id)
    order = db.get(WorkOrder, step.work_order_id) if step else None
    confirmation.status = "rejected"
    confirmation.decided_by = user.id
    write_audit(
        db,
        actor_id=user.id,
        action="type_confirmation.rejected",
        resource_type="type_confirmation",
        resource_id=confirmation.id,
        work_order_no=order.order_no if order else None,
        result="rejected",
        detail={
            "method": confirmation.method,
            "step_no": step.step_no if step else None,
            "reason": "ADMIN_REJECTED",
        },
    )
    db.commit()
    return {"status": "rejected", "message": "已驳回放行申请"}
