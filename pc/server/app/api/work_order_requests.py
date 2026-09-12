from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user, require_admin
from app.db.models import User, WorkOrder, WorkOrderRequest
from app.db.session import get_db

router = APIRouter(prefix="/work-orders", tags=["work-order-requests"])

ACTIVE_STATUSES = {"pending_approval", "approved", "in_progress"}


class WorkOrderRequestInput(BaseModel):
    request_type: Literal["takeover", "cancel"]
    reason: str = Field(min_length=1, max_length=500)


def request_view(request: WorkOrderRequest, order: WorkOrder | None = None, users: dict[int, User] | None = None) -> dict:
    users = users or {}
    requester = users.get(request.requested_by)
    return {
        "id": request.id,
        "order_no": order.order_no if order else None,
        "request_type": request.request_type,
        "reason": request.reason,
        "status": request.status,
        "requested_by": request.requested_by,
        "requester_name": requester.display_name if requester else None,
        "decided_by": request.decided_by,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "decided_at": request.decided_at.isoformat() if request.decided_at else None,
    }


def _order_with_request_or_404(db: Session, order_no: str) -> WorkOrder:
    order = db.scalar(select(WorkOrder).where(WorkOrder.order_no == order_no))
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
    return order


def _check_no_pending_request(db: Session, order: WorkOrder) -> None:
    pending = db.scalar(
        select(WorkOrderRequest.id).where(
            WorkOrderRequest.work_order_id == order.id,
            WorkOrderRequest.status == "pending",
        )
    )
    if pending is not None:
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_REQUEST_EXISTS", "message": "该工单已有待审批申请"})


@router.post("/{order_no}/requests", status_code=status.HTTP_201_CREATED)
def create_work_order_request(
    order_no: str,
    body: WorkOrderRequestInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    order = _order_with_request_or_404(db, order_no)
    if order.status == "deleted":
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_DELETED", "message": "工单已删除，不能继续申请操作"})
    _check_no_pending_request(db, order)

    if body.request_type == "takeover":
        if order.operator_id == user.id or order.created_by == user.id:
            raise HTTPException(status_code=409, detail={"code": "ALREADY_BOUND", "message": "当前账号已是该工单的执行人"})
        if order.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "当前工单状态不能申请接管"})
    else:
        if order.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "当前工单状态不能申请撤销"})

    request = WorkOrderRequest(
        work_order_id=order.id,
        request_type=body.request_type,
        reason=body.reason.strip(),
        status="pending",
        requested_by=user.id,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request_view(request, order, {user.id: user})


@router.get("/{order_no}/requests")
def list_work_order_requests(
    order_no: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    order = _order_with_request_or_404(db, order_no)
    requests = db.scalars(select(WorkOrderRequest).where(WorkOrderRequest.work_order_id == order.id).order_by(WorkOrderRequest.id.desc())).all()
    user_ids = {item.requested_by for item in requests} | {item.decided_by for item in requests if item.decided_by}
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    return [request_view(item, order, users) for item in requests]


@router.post("/requests/{request_id}/approve")
def approve_work_order_request(
    request_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    request = db.get(WorkOrderRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail={"code": "REQUEST_NOT_FOUND", "message": "申请不存在"})
    if request.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "REQUEST_STATE_CONFLICT", "message": "申请已处理"})
    order = db.get(WorkOrder, request.work_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})

    if request.request_type == "takeover":
        if order.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单当前状态不能接管"})
        order.operator_id = request.requested_by
    elif request.request_type == "cancel":
        if order.status not in ACTIVE_STATUSES:
            raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单当前状态不能撤销"})
        order.status = "cancelled"
    else:
        raise HTTPException(status_code=409, detail={"code": "REQUEST_TYPE_RETIRED", "message": "工单删除申请已停用，请驳回该历史申请"})

    request.status = "approved"
    request.decided_by = user.id
    request.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request_view(request, order, {user.id: user})


@router.post("/requests/{request_id}/reject")
def reject_work_order_request(
    request_id: int,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    request = db.get(WorkOrderRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail={"code": "REQUEST_NOT_FOUND", "message": "申请不存在"})
    if request.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "REQUEST_STATE_CONFLICT", "message": "申请已处理"})
    request.status = "rejected"
    request.decided_by = user.id
    request.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request_view(request, None, {user.id: user})
