import json
import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.auth import current_user, require_admin
from app.core.config import get_settings
from app.db.models import EvidenceFile, Label, Material, TypeConfirmation, User, WeighingAttempt, WorkOrderStep
from app.db.session import get_db
from app.services.audit import write_audit
from app.services.idempotency import execute_idempotent

router = APIRouter(prefix="/evidence", tags=["evidence"])
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class QRConfirmation(BaseModel):
    label_id: str = Field(min_length=1, max_length=64)
    material_id: str = Field(min_length=1, max_length=32)
    evidence_file_id: str = Field(min_length=1, max_length=64)


class WeightSubmission(BaseModel):
    weight_kg: float = Field(ge=0, le=1_000_000)
    scale_photo_file_id: str = Field(min_length=1, max_length=64)


class PhotoRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    file_id: str = Field(min_length=1, max_length=64)


def _material_identity(db: Session, material_id: str, label: Label | None = None) -> dict[str, str]:
    material = db.scalar(select(Material).where(Material.material_id == material_id))
    if material is not None:
        return {
            "material_id": material.material_id,
            "material_code": material.material_code,
            "material_name": material.name_zh,
        }

    if label is not None and label.payload_json:
        try:
            payload = json.loads(label.payload_json)
        except (TypeError, ValueError):
            payload = {}
        return {
            "material_id": material_id,
            "material_code": str(payload.get("materialCode") or payload.get("material_code") or ""),
            "material_name": str(payload.get("name") or payload.get("materialName") or ""),
        }

    return {"material_id": material_id, "material_code": "", "material_name": ""}


def _material_identity_text(identity: dict[str, str]) -> str:
    code = identity.get("material_code", "").strip()
    name = identity.get("material_name", "").strip()
    label = " ".join(part for part in (code, name) if part) or "未登记辅料"
    return f"{label}（{identity['material_id']}）"


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
    content_sha256 = hashlib.sha256(content).hexdigest()
    file_id = f"FILE-{secrets.token_hex(12)}"
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    directory = get_settings().data_dir / "uploads" / file_id[:8]
    directory.mkdir(parents=True, exist_ok=True)
    stored = directory / f"{file_id}{extension}"
    try:
        with stored.open("xb") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail={"code": "EVIDENCE_FILE_EXISTS", "message": "证据文件编号已存在，拒绝覆盖"}) from exc
    try:
        db.add(EvidenceFile(file_id=file_id, original_name=Path(file.filename or "upload").name, stored_path=str(stored), content_type=file.content_type, size_bytes=len(content), sha256=content_sha256, uploaded_by=user.id))
        db.commit()
    except Exception:
        db.rollback()
        stored.unlink(missing_ok=True)
        raise
    return {"file_id": file_id, "content_type": file.content_type, "size_bytes": len(content), "sha256": content_sha256}


@router.get("/files/integrity-check")
def check_evidence_integrity(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    items = []
    summary = {"ok": 0, "missing": 0, "hash_mismatch": 0, "size_mismatch": 0, "unhashed": 0}
    for evidence in db.scalars(select(EvidenceFile).order_by(EvidenceFile.created_at.desc())).all():
        path = Path(evidence.stored_path)
        item = {
            "file_id": evidence.file_id,
            "expected_sha256": evidence.sha256,
            "expected_size_bytes": evidence.size_bytes,
            "actual_sha256": None,
            "actual_size_bytes": None,
            "status": "ok",
        }
        if not path.is_file():
            item["status"] = "missing"
        else:
            actual_size = path.stat().st_size
            item["actual_size_bytes"] = actual_size
            if actual_size != evidence.size_bytes:
                item["status"] = "size_mismatch"
            elif not evidence.sha256:
                item["status"] = "unhashed"
            else:
                actual_sha256 = _sha256_file(path)
                item["actual_sha256"] = actual_sha256
                if actual_sha256 != evidence.sha256:
                    item["status"] = "hash_mismatch"
        summary[item["status"]] += 1
        items.append(item)

    issue_count = sum(count for status, count in summary.items() if status != "ok")
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total": len(items),
        "ok": summary["ok"],
        "issue_count": issue_count,
        "issues": [item for item in items if item["status"] != "ok"],
        "items": items,
    }


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
def confirm_qr(
    order_no: str,
    step_no: int,
    body: QRConfirmation,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    def operation() -> dict:
        step = get_step(db, order_no, step_no)
        authorize_step(step, user)
        if step.status not in {"pending", "type_confirmation"}:
            raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤不允许类型确认"})
        evidence = db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == body.evidence_file_id, EvidenceFile.uploaded_by == user.id))
        if evidence is None:
            raise HTTPException(status_code=422, detail={"code": "EVIDENCE_NOT_FOUND", "message": "类型确认照片证据不存在"})
        label = db.scalar(select(Label).where(Label.label_id == body.label_id))
        confirmation = TypeConfirmation(
            work_order_step_id=step.id,
            method="qr",
            scanned_material_id=body.material_id,
            scanned_label_id=body.label_id,
            evidence_file_id=body.evidence_file_id,
            created_by=user.id,
            status="rejected",
        )

        label_identity = _material_identity(db, label.material_id, label) if label is not None else None
        scanned_identity = _material_identity(
            db,
            body.material_id,
            label if label is not None and label.material_id == body.material_id else None,
        )
        required_identity = {
            "material_id": step.material_id_snapshot,
            "material_code": step.material_code_snapshot,
            "material_name": step.material_name_snapshot,
        }

        rejection: dict | None = None
        if label is None:
            rejection = {"code": "LABEL_NOT_FOUND", "message": "二维码标签不存在"}
        elif label.status != "active":
            rejection = {"code": "LABEL_NOT_ACTIVE", "message": "二维码标签已失效"}
        elif label.material_id != body.material_id:
            rejection = {
                "code": "LABEL_MATERIAL_MISMATCH",
                "message": (
                    "二维码标签与扫描结果不一致："
                    f"标签为 {_material_identity_text(label_identity)}，"
                    f"扫描结果为 {_material_identity_text(scanned_identity)}"
                ),
            }
        elif body.material_id != step.material_id_snapshot:
            rejection = {
                "code": "MATERIAL_MISMATCH",
                "message": (
                    "扫描到的辅料与当前步骤要求不一致："
                    f"当前步骤要求 {_material_identity_text(required_identity)}，"
                    f"扫描标签为 {_material_identity_text(scanned_identity)}。"
                    "请确认当前工单是否使用了最新配方。"
                ),
            }

        if rejection is not None:
            db.add(confirmation)
            db.flush()
            write_audit(
                db,
                actor_id=user.id,
                action="type_confirmation.rejected",
                resource_type="type_confirmation",
                resource_id=confirmation.id,
                work_order_no=order_no,
                result="rejected",
                detail={
                    "method": "qr",
                    "step_no": step_no,
                    "required_material_id": step.material_id_snapshot,
                    "scanned_material_id": body.material_id,
                    "label_material_id": label.material_id if label is not None else None,
                    "scanned_label_id": body.label_id,
                    "reason": rejection["code"],
                },
            )
            db.commit()
            raise HTTPException(status_code=422, detail=rejection)

        confirmation.status = "passed"
        db.add(confirmation)
        step_update = db.execute(
            update(WorkOrderStep)
            .where(
                WorkOrderStep.id == step.id,
                WorkOrderStep.status.in_(("pending", "type_confirmation")),
            )
            .values(status="weighing")
        )
        if step_update.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤已被其他设备推进"})
        db.flush()
        write_audit(
            db,
            actor_id=user.id,
            action="type_confirmation.passed",
            resource_type="type_confirmation",
            resource_id=confirmation.id,
            work_order_no=order_no,
            detail={
                "method": "qr",
                "step_no": step_no,
                "material_id": body.material_id,
                "label_id": body.label_id,
            },
        )
        return {"status": "passed", "next": "weighing", "material_id": body.material_id, "label_id": body.label_id}

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /evidence/work-orders/{order_no}/steps/{step_no}/qr",
        payload={
            "order_no": order_no,
            "step_no": step_no,
            "label_id": body.label_id,
            "material_id": body.material_id,
            "evidence_file_id": body.evidence_file_id,
        },
        operation=operation,
    )


@router.post("/work-orders/{order_no}/steps/{step_no}/photo-request")
def request_photo_confirmation(
    order_no: str,
    step_no: int,
    body: PhotoRequest,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    def operation() -> dict:
        step = get_step(db, order_no, step_no)
        authorize_step(step, user)
        if step.status != "pending":
            raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤不允许提交拍照放行申请"})
        if db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == body.file_id, EvidenceFile.uploaded_by == user.id)) is None:
            raise HTTPException(status_code=422, detail={"code": "EVIDENCE_NOT_FOUND", "message": "照片证据不存在"})
        step_update = db.execute(
            update(WorkOrderStep)
            .where(WorkOrderStep.id == step.id, WorkOrderStep.status == "pending")
            .values(status="type_confirmation")
        )
        if step_update.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤已被其他设备推进"})
        confirmation = TypeConfirmation(work_order_step_id=step.id, method="photo", reason=body.reason, evidence_file_id=body.file_id, status="pending", created_by=user.id)
        db.add(confirmation)
        db.flush()
        write_audit(
            db,
            actor_id=user.id,
            action="type_confirmation.photo_requested",
            resource_type="type_confirmation",
            resource_id=confirmation.id,
            work_order_no=order_no,
            detail={"step_no": step_no, "reason": confirmation.reason},
        )
        return {"confirmation_id": confirmation.id, "status": "pending", "message": "已提交拍照放行申请"}

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /evidence/work-orders/{order_no}/steps/{step_no}/photo-request",
        payload={
            "order_no": order_no,
            "step_no": step_no,
            "reason": body.reason,
            "file_id": body.file_id,
        },
        operation=operation,
    )


@router.post("/confirmations/{confirmation_id}/approve")
def approve_photo_confirmation(
    confirmation_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail={"code": "ADMIN_REQUIRED", "message": "需要管理员权限"})

    def operation() -> dict:
        confirmation_update = db.execute(
            update(TypeConfirmation)
            .where(TypeConfirmation.id == confirmation_id, TypeConfirmation.status == "pending")
            .values(status="passed", decided_by=user.id)
        )
        if confirmation_update.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "CONFIRMATION_STATE_CONFLICT", "message": "申请已处理"})
        confirmation = db.get(TypeConfirmation, confirmation_id)
        step_update = db.execute(
            update(WorkOrderStep)
            .where(
                WorkOrderStep.id == confirmation.work_order_step_id,
                WorkOrderStep.status == "type_confirmation",
            )
            .values(status="weighing")
        )
        if step_update.rowcount != 1:
            raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤已被其他设备推进"})
        db.flush()
        write_audit(
            db,
            actor_id=user.id,
            action="type_confirmation.approved",
            resource_type="type_confirmation",
            resource_id=confirmation.id,
            work_order_no=confirmation.step.work_order.order_no,
            detail={"method": confirmation.method, "step_no": confirmation.step.step_no},
        )
        return {"status": "passed", "next": "weighing"}

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /evidence/confirmations/{confirmation_id}/approve",
        payload={"confirmation_id": confirmation_id},
        operation=operation,
    )


@router.post("/work-orders/{order_no}/steps/{step_no}/weight")
def submit_weight(
    order_no: str,
    step_no: int,
    body: WeightSubmission,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    def operation() -> dict:
        step = get_step(db, order_no, step_no)
        authorize_step(step, user)
        if step.status != "weighing":
            raise HTTPException(status_code=409, detail={"code": "STEP_NOT_READY_FOR_WEIGHT", "message": "请先完成辅料类型确认"})
        evidence = db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == body.scale_photo_file_id, EvidenceFile.uploaded_by == user.id))
        if evidence is None:
            raise HTTPException(status_code=422, detail={"code": "SCALE_PHOTO_REQUIRED", "message": "请上传当前操作员拍摄的电子秤读数照片"})
        passed = abs(body.weight_kg - step.required_weight_kg) <= step.tolerance_kg
        attempt = WeighingAttempt(work_order_step_id=step.id, weight_kg=body.weight_kg, weight_source="manual", scale_photo_file_id=body.scale_photo_file_id, passed=passed, created_by=user.id)
        db.add(attempt)
        db.flush()
        if passed:
            step_update = db.execute(
                update(WorkOrderStep)
                .where(WorkOrderStep.id == step.id, WorkOrderStep.status == "weighing")
                .values(status="completed")
            )
            if step_update.rowcount != 1:
                raise HTTPException(status_code=409, detail={"code": "STEP_STATE_CONFLICT", "message": "当前步骤已被其他设备完成"})
        write_audit(
            db,
            actor_id=user.id,
            action="weighing.passed" if passed else "weighing.rejected",
            resource_type="weighing_attempt",
            resource_id=attempt.id,
            work_order_no=order_no,
            result="success" if passed else "rejected",
            detail={
                "step_no": step_no,
                "material_id": step.material_id_snapshot,
                "required_weight_kg": step.required_weight_kg,
                "tolerance_kg": step.tolerance_kg,
                "submitted_weight_kg": body.weight_kg,
                "reason": None if passed else "OUT_OF_TOLERANCE",
            },
        )
        return {
            "status": "passed" if passed else "out_of_tolerance",
            "required_weight_kg": step.required_weight_kg,
            "tolerance_kg": step.tolerance_kg,
            "weight_kg": body.weight_kg,
        }

    return execute_idempotent(
        db,
        request,
        user_id=user.id,
        endpoint="POST /evidence/work-orders/{order_no}/steps/{step_no}/weight",
        payload={
            "order_no": order_no,
            "step_no": step_no,
            "weight_kg": body.weight_kg,
            "scale_photo_file_id": body.scale_photo_file_id,
        },
        operation=operation,
    )
