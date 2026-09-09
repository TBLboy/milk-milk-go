import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.config import get_settings
from app.db.models import AuditLog, BackupRecord, User
from app.db.session import get_db

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/audit-logs")
def list_audit_logs(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": item.id, "actor_id": item.actor_id, "action": item.action, "resource_type": item.resource_type, "resource_id": item.resource_id, "created_at": item.created_at.isoformat()} for item in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)).all()]


@router.post("/backups")
def create_backup(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    source = settings.data_dir / settings.database_filename
    backup_dir = settings.data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"{source.stem}-{stamp}.sqlite3"
    try:
        if not source.exists():
            raise FileNotFoundError("database file does not exist")
        shutil.copy2(source, destination)
        record = BackupRecord(file_path=str(destination), status="success", size_bytes=destination.stat().st_size)
        db.add(record)
        db.add(AuditLog(action="backup.created", resource_type="backup", resource_id=str(record.id) if record.id else None, detail_json=None))
        db.commit()
        return {"status": "success", "file_name": destination.name, "size_bytes": record.size_bytes, "created_at": record.created_at.isoformat()}
    except OSError as exc:
        db.add(BackupRecord(file_path=str(destination), status="failed", error_message="backup failed"))
        db.commit()
        raise HTTPException(status_code=503, detail={"code": "BACKUP_FAILED", "message": "数据库备份失败"}) from exc


@router.get("/backups")
def list_backups(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    return [{"file_path": item.file_path, "status": item.status, "size_bytes": item.size_bytes, "created_at": item.created_at.isoformat(), "error_message": item.error_message} for item in db.scalars(select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(100)).all()]
