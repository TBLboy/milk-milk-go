from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth import current_user, require_admin
from app.db.models import User, WorkOrder, WorkOrderRequest
from app.db.session import get_db
from app.services.audit import write_audit
from app.services.idempotency import execute_idempotent

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
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    def operation() -> dict:
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

        request_item = WorkOrderRequest(
            work_order_id=order.id,
            request_type=body.request_type,
            reason=body.reason.strip(),
            status="pending",
            requested_by=user.id,
        )
        db.add(request_item)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_REQUEST_EXISTS", "message": "该工单已有待审批申请"}) from exc
        write_audit(
            db,
            actor_id=user.id,
            action="work_order.request_created",
            resource_type="work_order_request",
            resource_id=request_item.id,
            work_order_no=order.order_no,
            detail={"request_type": body.request_type, "reason": request_item.reason},
        )
        return request_view(request_item, order, {user.id: user})

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /work-orders/{order_no}/requests",
        payload={"order_no": order_no, "request_type": body.request_type, "reason": body.reason.strip()},
        operation=operation,
        status_code=201,
    )


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
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    def operation() -> dict:
        request_item = db.get(WorkOrderRequest, request_id)
        if request_item is None:
            raise HTTPException(status_code=404, detail={"code": "REQUEST_NOT_FOUND", "message": "申请不存在"})
        order = db.get(WorkOrder, request_item.work_order_id)
        if order is None:
            raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
        request_update = db.execute(
            update(WorkOrderRequest)
            .where(WorkOrderRequest.id == request_id, WorkOrderRequest.status == "pending")
            .values(status="approved", decided_by=user.id, decided_at=datetime.now(timezone.utc))
        )
        if request_update.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "REQUEST_STATE_CONFLICT", "message": "申请已处理"})

        if request_item.request_type == "takeover":
            order_update = db.execute(
                update(WorkOrder)
                .where(WorkOrder.id == order.id, WorkOrder.status.in_(ACTIVE_STATUSES))
                .values(operator_id=request_item.requested_by)
            )
            if order_update.rowcount != 1:
                raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单当前状态不能接管"})
        elif request_item.request_type == "cancel":
            order_update = db.execute(
                update(WorkOrder)
                .where(WorkOrder.id == order.id, WorkOrder.status.in_(ACTIVE_STATUSES))
                .values(status="cancelled")
            )
            if order_update.rowcount != 1:
                raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单当前状态不能撤销"})
        else:
            raise HTTPException(status_code=409, detail={"code": "REQUEST_TYPE_RETIRED", "message": "工单删除申请已停用，请驳回该历史申请"})

        db.flush()
        db.refresh(request_item)
        db.refresh(order)
        write_audit(
            db,
            actor_id=user.id,
            action="work_order.request_approved",
            resource_type="work_order_request",
            resource_id=request_item.id,
            work_order_no=order.order_no,
            detail={
                "request_type": request_item.request_type,
                "requested_by": request_item.requested_by,
                "new_work_order_status": order.status,
                "new_operator_id": order.operator_id,
            },
        )
        return request_view(request_item, order, {user.id: user})

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /work-orders/requests/{request_id}/approve",
        payload={"request_id": request_id},
        operation=operation,
    )


@router.post("/requests/{request_id}/reject")
def reject_work_order_request(
    request_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    def operation() -> dict:
        request_item = db.get(WorkOrderRequest, request_id)
        if request_item is None:
            raise HTTPException(status_code=404, detail={"code": "REQUEST_NOT_FOUND", "message": "申请不存在"})
        result = db.execute(
            update(WorkOrderRequest)
            .where(WorkOrderRequest.id == request_id, WorkOrderRequest.status == "pending")
            .values(status="rejected", decided_by=user.id, decided_at=datetime.now(timezone.utc))
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "REQUEST_STATE_CONFLICT", "message": "申请已处理"})
        db.flush()
        db.refresh(request_item)
        order = db.get(WorkOrder, request_item.work_order_id)
        write_audit(
            db,
            actor_id=user.id,
            action="work_order.request_rejected",
            resource_type="work_order_request",
            resource_id=request_item.id,
            work_order_no=order.order_no if order else None,
            result="rejected",
            detail={
                "request_type": request_item.request_type,
                "requested_by": request_item.requested_by,
            },
        )
        return request_view(request_item, order, {user.id: user})

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /work-orders/requests/{request_id}/reject",
        payload={"request_id": request_id},
        operation=operation,
    )
