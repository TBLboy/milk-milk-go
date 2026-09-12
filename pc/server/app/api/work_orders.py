from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import current_user, require_admin
from app.db.models import Product, Recipe, RecipeItem, SystemSetting, User, WorkOrder, WorkOrderStep
from app.db.session import get_db

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


class WorkOrderInput(BaseModel):
    product_id: int = Field(gt=0)
    target_weight_kg: float = Field(gt=0, le=1_000_000)
    operator_id: int | None = Field(default=None, gt=0)


def order_view(order: WorkOrder, users: dict[int, User] | None = None) -> dict:
    users = users or {}
    return {
        "order_no": order.order_no,
        "product_name": order.product_name_snapshot,
        "target_weight_kg": order.target_weight_kg,
        "status": order.status,
        "operator_id": order.operator_id,
        "operator_name": users.get(order.operator_id).display_name if order.operator_id and users.get(order.operator_id) else None,
        "created_by": order.created_by,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "steps": [{
            "step_no": step.step_no,
            "material_id": step.material_id_snapshot,
            "material_code": step.material_code_snapshot,
            "material_name": step.material_name_snapshot,
            "required_weight_kg": step.required_weight_kg,
            "tolerance_kg": step.tolerance_kg,
            "status": step.status,
            "confirmations": [{
                "id": item.id,
                "method": item.method,
                "status": item.status,
                "scanned_material_id": item.scanned_material_id,
                "reason": item.reason,
                "evidence_file_id": item.evidence_file_id,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            } for item in step.confirmations],
            "weighing_attempts": [{
                "id": item.id,
                "weight_kg": item.weight_kg,
                "weight_source": item.weight_source,
                "scale_photo_file_id": item.scale_photo_file_id,
                "passed": item.passed,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            } for item in step.weighing_attempts],
        } for step in order.steps],
        "requests": [{
            "id": request.id,
            "request_type": request.request_type,
            "reason": request.reason,
            "status": request.status,
            "requested_by": request.requested_by,
            "requester_name": users.get(request.requested_by).display_name if request.requested_by and users.get(request.requested_by) else None,
            "decided_by": request.decided_by,
            "created_at": request.created_at.isoformat() if request.created_at else None,
            "decided_at": request.decided_at.isoformat() if request.decided_at else None,
        } for request in order.requests],
    }


def _setting_float(db: Session, key: str, default: float) -> float:
    value = db.scalar(select(SystemSetting.value).where(SystemSetting.key == key))
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_step_evidence(query):
    return query.options(
        selectinload(WorkOrder.steps).selectinload(WorkOrderStep.confirmations),
        selectinload(WorkOrder.steps).selectinload(WorkOrderStep.weighing_attempts),
        selectinload(WorkOrder.requests),
    )


def _load_order(db: Session, order_no: str) -> WorkOrder | None:
    return db.scalar(_load_step_evidence(select(WorkOrder)).where(WorkOrder.order_no == order_no))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_work_order(body: WorkOrderInput, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    product = db.scalar(select(Product).options(selectinload(Product.recipe).selectinload(Recipe.items).selectinload(RecipeItem.material)).where(Product.id == body.product_id, Product.enabled.is_(True)))
    if product is None or product.recipe is None or not product.recipe.enabled:
        raise HTTPException(status_code=422, detail={"code": "PRODUCT_RECIPE_UNAVAILABLE", "message": "产品或启用配方不存在"})
    operator_id = body.operator_id if user.role == "admin" and body.operator_id else user.id
    if operator_id != user.id and db.scalar(select(User).where(User.id == operator_id, User.role == "operator", User.is_active.is_(True))) is None:
        raise HTTPException(status_code=422, detail={"code": "OPERATOR_NOT_FOUND", "message": "指定操作员不存在或不可用"})
    now = datetime.now(timezone.utc)
    order = WorkOrder(order_no=f"WO-{now.strftime('%Y%m%d%H%M%S')}-{now.microsecond // 1000:03d}", product_name_snapshot=product.name, target_weight_kg=body.target_weight_kg, status="approved" if user.role == "admin" else "pending_approval", operator_id=operator_id if user.role == "admin" else None, created_by=user.id)
    tons = body.target_weight_kg / 1000
    tolerance_percent = _setting_float(db, "default_tolerance_percent", 1.0)
    min_absolute_kg = _setting_float(db, "min_absolute_tolerance_grams", 5.0) / 1000
    order.steps = [WorkOrderStep(step_no=index + 1, material_id_snapshot=item.material.material_id, material_code_snapshot=item.material.material_code, material_name_snapshot=item.material.name_zh, required_weight_kg=round(item.quantity_per_ton_kg * tons, 6), tolerance_kg=max(round(item.quantity_per_ton_kg * tons * tolerance_percent / 100, 6), min_absolute_kg)) for index, item in enumerate(product.recipe.items)]
    db.add(order)
    db.commit()
    db.refresh(order)
    return order_view(order)


@router.get("")
def list_work_orders(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    closed_last = case((WorkOrder.status.in_(["cancelled", "deleted"]), 1), else_=0)
    query = _load_step_evidence(select(WorkOrder)).order_by(closed_last.asc(), WorkOrder.created_at.desc())
    if user.role != "admin":
        query = query.where(WorkOrder.status != "deleted")
    orders = db.scalars(query).all()
    user_ids: set[int] = set()
    for order in orders:
        user_ids.add(order.created_by)
        if order.operator_id:
            user_ids.add(order.operator_id)
        for request in order.requests:
            user_ids.add(request.requested_by)
            if request.decided_by:
                user_ids.add(request.decided_by)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    return [order_view(order, users) for order in orders]


@router.get("/{order_no}")
def get_work_order(order_no: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_no)
    if order is None or (user.role != "admin" and order.status == "deleted"):
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
    user_ids = {order.created_by}
    if order.operator_id:
        user_ids.add(order.operator_id)
    for request in order.requests:
        user_ids.add(request.requested_by)
        if request.decided_by:
            user_ids.add(request.decided_by)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    return order_view(order, users)


@router.post("/{order_no}/approve")
def approve_work_order(order_no: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_no)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
    if order.status != "pending_approval":
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单当前状态不可审批"})
    order.status = "approved"
    order.operator_id = order.operator_id or order.created_by
    db.commit()
    user_ids = {order.created_by}
    if order.operator_id:
        user_ids.add(order.operator_id)
    for request in order.requests:
        user_ids.add(request.requested_by)
        if request.decided_by:
            user_ids.add(request.decided_by)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    return order_view(order, users)


@router.post("/{order_no}/start")
def start_work_order(order_no: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_no)
    if order is None or (user.role != "admin" and order.operator_id != user.id and order.created_by != user.id):
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
    if order.status != "approved":
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单尚未获得执行许可"})
    order.status = "in_progress"
    db.commit()
    user_ids = {order.created_by}
    if order.operator_id:
        user_ids.add(order.operator_id)
    for request in order.requests:
        user_ids.add(request.requested_by)
        if request.decided_by:
            user_ids.add(request.decided_by)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    return order_view(order, users)


@router.post("/{order_no}/cancel")
def cancel_work_order(order_no: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_no)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
    if order.status not in {"pending_approval", "approved", "in_progress"}:
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "工单当前状态不可撤销"})
    order.status = "cancelled"
    db.commit()
    user_ids = {order.created_by}
    if order.operator_id:
        user_ids.add(order.operator_id)
    for request in order.requests:
        user_ids.add(request.requested_by)
        if request.decided_by:
            user_ids.add(request.decided_by)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    return order_view(order, users)


@router.post("/{order_no}/complete")
def complete_work_order(order_no: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    order = _load_order(db, order_no)
    if order is None or (user.role != "admin" and order.operator_id != user.id and order.created_by != user.id):
        raise HTTPException(status_code=404, detail={"code": "WORK_ORDER_NOT_FOUND", "message": "工单不存在"})
    if order.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STATE_CONFLICT", "message": "只有执行中的工单可以完成"})
    if any(step.status != "completed" for step in order.steps):
        raise HTTPException(status_code=409, detail={"code": "WORK_ORDER_STEPS_INCOMPLETE", "message": "所有辅料步骤完成前不能提交工单"})
    order.status = "completed"
    db.commit()
    user_ids = {order.created_by}
    if order.operator_id:
        user_ids.add(order.operator_id)
    for request in order.requests:
        user_ids.add(request.requested_by)
        if request.decided_by:
            user_ids.add(request.decided_by)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids))).all()}
    return order_view(order, users)
