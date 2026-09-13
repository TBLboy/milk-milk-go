import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.config import get_settings
from app.db.models import AuditLog, BackupRecord, SystemSetting, User
from app.db.session import get_db
from app.services.audit import sanitize_audit_detail, write_audit
from app.services.backup import BackupError, create_complete_backup

router = APIRouter(prefix="/operations", tags=["operations"])


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _audit_detail(item: AuditLog) -> dict | list | str | None:
    if not item.detail_json:
        return None
    try:
        return sanitize_audit_detail(json.loads(item.detail_json))
    except json.JSONDecodeError:
        return item.detail_json


@router.get("/audit-logs")
def list_audit_logs(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    actor_id: int | None = Query(default=None, gt=0),
    work_order_no: str | None = Query(default=None, max_length=40),
    action: str | None = Query(default=None, max_length=100),
    result: str | None = Query(default=None, pattern="^(success|failure|rejected)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    filters = []
    normalized_start = _as_utc(start_at)
    normalized_end = _as_utc(end_at)
    if normalized_start is not None:
        filters.append(AuditLog.created_at >= normalized_start)
    if normalized_end is not None:
        filters.append(AuditLog.created_at <= normalized_end)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if work_order_no:
        filters.append(AuditLog.work_order_no == work_order_no.strip())
    if action:
        filters.append(AuditLog.action == action.strip())
    if result:
        filters.append(AuditLog.result == result)

    total = db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
    records = db.scalars(
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    actor_ids = {item.actor_id for item in records if item.actor_id is not None}
    actors = {
        item.id: item
        for item in db.scalars(select(User).where(User.id.in_(actor_ids))).all()
    } if actor_ids else {}

    return {
        "items": [
            {
                "id": item.id,
                "actor_id": item.actor_id,
                "actor_name": actors.get(item.actor_id).display_name if item.actor_id and actors.get(item.actor_id) else None,
                "actor_username": actors.get(item.actor_id).username if item.actor_id and actors.get(item.actor_id) else None,
                "action": item.action,
                "result": item.result,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "work_order_no": item.work_order_no,
                "detail": _audit_detail(item),
                "created_at": item.created_at.isoformat(),
            }
            for item in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("/backups")
def create_backup(admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    values = {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}
    try:
        result = create_complete_backup(settings, trigger="manual", system_settings=values)
        record = BackupRecord(
            file_path=str(result.file_path),
            status="success",
            size_bytes=result.size_bytes,
            trigger="manual",
            checksum_sha256=result.checksum_sha256,
            app_version=settings.app_version,
        )
        db.add(record)
        db.flush()
        write_audit(
            db,
            actor_id=admin.id,
            action="backup.created",
            resource_type="backup",
            resource_id=record.id,
            detail={"file_name": result.file_name, "size_bytes": result.size_bytes},
        )
        db.commit()
        return {
            "status": "success",
            "file_name": result.file_name,
            "size_bytes": result.size_bytes,
            "checksum_sha256": result.checksum_sha256,
            "trigger": result.trigger,
            "created_at": result.created_at.isoformat(),
        }
    except BackupError as exc:
        db.add(
            BackupRecord(
                file_path=str(settings.data_dir / "backups"),
                status="failed",
                trigger="manual",
                app_version=settings.app_version,
                error_message=str(exc)[:1000],
            )
        )
        write_audit(
            db,
            actor_id=admin.id,
            action="backup.failed",
            resource_type="backup",
            result="failure",
            detail={"error": str(exc)[:500]},
        )
        db.commit()
        raise HTTPException(status_code=503, detail={"code": "BACKUP_FAILED", "message": "完整备份失败"}) from exc


@router.get("/backups")
def list_backups(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "file_path": item.file_path,
            "status": item.status,
            "size_bytes": item.size_bytes,
            "trigger": item.trigger,
            "schedule_key": item.schedule_key,
            "checksum_sha256": item.checksum_sha256,
            "app_version": item.app_version,
            "created_at": item.created_at.isoformat(),
            "error_message": item.error_message,
        }
        for item in db.scalars(select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(100)).all()
    ]
