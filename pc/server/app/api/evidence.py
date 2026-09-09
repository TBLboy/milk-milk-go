import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import get_settings
from app.db.models import EvidenceFile, TypeConfirmation, User, WeighingAttempt, WorkOrderStep
from app.db.session import get_db

router = APIRouter(prefix="/evidence", tags=["evidence"])
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


class QRConfirmation(BaseModel):
    material_id: str = Field(min_length=1, max_length=32)


class WeightSubmission(BaseModel):
    weight_kg: float = Field(ge=0, le=1_000_000)
    scale_photo_file_id: str = Field(min_length=1, max_length=64)


class PhotoRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    file_id: str = Field(min_length=1, max_length=64)


def get_step(db: Session, order_no: str, step_no: int) -> WorkOrderStep:
    step = db.scalar(select(WorkOrderStep).join(WorkOrderStep.work_order).where(WorkOrderStep.step_no == step_no, WorkOrderStep.work_order.has(order_no=order_no)))
    if step is None:
        raise HTTPException(status_code=404, detail={"code": "STEP_NOT_FOUND", "message": "工单步骤不存在"})
    return step


def authorize_step(step: WorkOrderStep, user: User) -> None:
    if user.role != "admin" and step.work_order.operator_id != user.id and step.work_order.created_by != user.id:
        raise HTTPException(status_code=404, detail={"code": "STEP_NOT_FOUND", "message": "工单步骤不存在"})


@router.post("/files", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_FILE_TYPE", "message": "仅支持 JPG、PNG 或 WebP 图片"})
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "FILE_TOO_LARGE", "message": "图片不能超过 10MB"})
    file_id = f"FILE-{secrets.token_hex(12)}"
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    directory = get_settings().data_dir / "uploads" / file_id[:8]
    directory.mkdir(parents=True, exist_ok=True)
    stored = directory / f"{file_id}{extension}"
    stored.write_bytes(content)
    db.add(EvidenceFile(file_id=file_id, original_name=Path(file.filename or "upload").name, stored_path=str(stored), content_type=file.content_type, size_bytes=len(content), uploaded_by=user.id))
    db.commit()
    return {"file_id": file_id, "content_type": file.content_type, "size_bytes": len(content)}


@router.get("/files/{file_id}")
def get_evidence_file(file_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> FileResponse:
    evidence = db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == file_id))
    if evidence is None:
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "文件不存在"})
    path = Path(evidence.stored_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"code": "FILE_MISSING", "message": "文件已丢失"})
    return FileResponse(path, media_type=evidence.content_type)


@router.post("/work-orders/{order_no}/steps/{step_no}/qr")
def confirm_qr(order_no: str, step_no: int, body: QRConfirmation, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    step = get_step(db, order_no, step_no)
    authorize_step(step, user)
    if step.status not in {"pending", "type_confirmation"}:
        raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤不允许类型确认"})
    matched = body.material_id == step.material_id_snapshot
    db.add(TypeConfirmation(work_order_step_id=step.id, method="qr", scanned_material_id=body.material_id, status="passed" if matched else "rejected", created_by=user.id))
    if matched:
        step.status = "weighing"
    db.commit()
    if not matched:
        raise HTTPException(status_code=422, detail={"code": "MATERIAL_MISMATCH", "message": "扫描到的辅料与当前步骤要求不一致"})
    return {"status": "passed", "next": "weighing", "material_id": body.material_id}


@router.post("/work-orders/{order_no}/steps/{step_no}/photo-request")
def request_photo_confirmation(order_no: str, step_no: int, body: PhotoRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    step = get_step(db, order_no, step_no)
    authorize_step(step, user)
    if db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == body.file_id)) is None:
        raise HTTPException(status_code=422, detail={"code": "EVIDENCE_NOT_FOUND", "message": "照片证据不存在"})
    confirmation = TypeConfirmation(work_order_step_id=step.id, method="photo", reason=body.reason, evidence_file_id=body.file_id, status="pending", created_by=user.id)
    db.add(confirmation)
    step.status = "type_confirmation"
    db.commit()
    db.commit()
    return {"confirmation_id": confirmation.id, "status": "pending", "message": "已提交拍照放行申请"}


@router.post("/confirmations/{confirmation_id}/approve")
def approve_photo_confirmation(confirmation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED", "message": "需要管理员权限"})
    confirmation = db.get(TypeConfirmation, confirmation_id)
    if confirmation is None:
        raise HTTPException(status_code=404, detail={"code": "CONFIRMATION_NOT_FOUND", "message": "申请不存在"})
    if confirmation.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "CONFIRMATION_STATE_CONFLICT", "message": "申请已处理"})
    step = db.get(WorkOrderStep, confirmation.work_order_step_id)
    confirmation.status = "passed"
    confirmation.decided_by = user.id
    step.status = "weighing"
    db.commit()
    return {"status": "passed", "next": "weighing"}


@router.post("/work-orders/{order_no}/steps/{step_no}/weight")
def submit_weight(order_no: str, step_no: int, body: WeightSubmission, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    step = get_step(db, order_no, step_no)
    authorize_step(step, user)
    if step.status != "weighing":
        raise HTTPException(status_code=409, detail={"code": "STEP_NOT_READY_FOR_WEIGHT", "message": "请先完成辅料类型确认"})
    evidence = db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == body.scale_photo_file_id, EvidenceFile.uploaded_by == user.id))
    if evidence is None:
        raise HTTPException(status_code=422, detail={"code": "SCALE_PHOTO_REQUIRED", "message": "请上传当前操作员拍摄的电子秤读数照片"})
    passed = abs(body.weight_kg - step.required_weight_kg) <= step.tolerance_kg
    db.add(WeighingAttempt(work_order_step_id=step.id, weight_kg=body.weight_kg, weight_source="manual", scale_photo_file_id=body.scale_photo_file_id, passed=passed, created_by=user.id))
    if passed:
        step.status = "completed"
    db.commit()
    return {"status": "passed" if passed else "out_of_tolerance", "required_weight_kg": step.required_weight_kg, "tolerance_kg": step.tolerance_kg, "weight_kg": body.weight_kg}
