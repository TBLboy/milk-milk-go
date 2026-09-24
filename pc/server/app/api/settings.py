import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.core.network import detect_local_ipv4_addresses
from app.db.models import SystemSetting, User
from app.db.session import get_db
from app.services.audit import write_audit
from app.services.backup import parse_backup_time, parse_keep_count, parse_retention_years, validate_backup_path

router = APIRouter(prefix="/settings", tags=["settings"])
LABEL_SIZE_PATTERN = re.compile(r"^(\d{1,3})\s*[xX×]\s*(\d{1,3})$")


class SettingsInput(BaseModel):
    values: dict[str, str] = Field(min_length=1, max_length=50)


def _settings_dict(db: Session) -> dict[str, str]:
    return {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}


@router.get("")
def get_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    return _settings_dict(db)


def _normalize_label_size(value: str) -> str | None:
    match = LABEL_SIZE_PATTERN.fullmatch(value.strip())
    if match is None:
        return None
    width, height = (int(part) for part in match.groups())
    if not 10 <= width <= 300 or not 10 <= height <= 300:
        return None
    return f"{width}x{height}"


@router.get("/network-addresses")
def get_network_addresses(_: User = Depends(require_admin)) -> dict:
    try:
        return detect_local_ipv4_addresses()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.put("")
def update_settings(body: SettingsInput, user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    changes = {}
    for key, value in body.values.items():
        if key == "backup_time" and parse_backup_time(value.strip()) is None:
            raise HTTPException(status_code=422, detail={"code": "BACKUP_TIME_INVALID", "message": "自动备份时间必须使用 HH:MM 格式"})
        if key == "backup_enabled" and value.strip().lower() not in {"true", "false"}:
            raise HTTPException(status_code=422, detail={"code": "BACKUP_ENABLED_INVALID", "message": "自动备份开关必须为 true 或 false"})
        if key == "backup_retention_years":
            months = parse_retention_years(value)
            if months is None or months > 120:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "BACKUP_RETENTION_INVALID",
                        "message": "备份保留年限必须为 0（永久）或 1-120 个月",
                    },
                )
            value = str(months)
        if key == "backup_keep_count":
            count = parse_keep_count(value)
            if count is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "BACKUP_KEEP_COUNT_INVALID",
                        "message": "备份保留数量必须为 10-365 之间的整数",
                    },
                )
            value = str(count)
        if key == "backup_path":
            path_error = validate_backup_path(value)
            if path_error is not None:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "BACKUP_PATH_INVALID", "message": path_error},
                )
            value = value.strip()
        if key == "label_size_mm":
            normalized_label_size = _normalize_label_size(value)
            if normalized_label_size is None:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "LABEL_SIZE_INVALID",
                        "message": "标签尺寸必须使用宽x高格式，宽高范围为 10-300 毫米",
                    },
                )
            value = normalized_label_size
        value = value.strip()
        setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        before = setting.value if setting is not None else None
        changes[key] = {"before": before, "after": value}
        if setting is None:
            db.add(SystemSetting(key=key, value=value))
        else:
            setting.value = value
    write_audit(
        db,
        actor_id=user.id,
        action="settings.updated",
        resource_type="system_setting",
        detail={"changes": changes},
    )
    db.commit()
    if "backup_path" in changes:
        _write_backup_path_conf(changes["backup_path"]["after"])
    return _settings_dict(db)


def _write_backup_path_conf(value: str) -> None:
    """Mirror the backup path into a config file so restores keep the setting."""
    from app.core.config import get_settings

    settings = get_settings()
    conf_path = settings.data_dir / "backup_path.conf"
    try:
        conf_path.write_text(value.strip() + "\n", encoding="utf-8")
    except OSError:
        pass
