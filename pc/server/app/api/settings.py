from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.models import SystemSetting, User
from app.db.session import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsInput(BaseModel):
    values: dict[str, str] = Field(min_length=1, max_length=50)


def _settings_dict(db: Session) -> dict[str, str]:
    return {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}


@router.get("")
def get_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    return _settings_dict(db)


@router.put("")
def update_settings(body: SettingsInput, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, str]:
    for key, value in body.values.items():
        setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if setting is None:
            db.add(SystemSetting(key=key, value=value))
        else:
            setting.value = value
    db.commit()
    return _settings_dict(db)
