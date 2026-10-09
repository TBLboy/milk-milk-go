"""授权运行时装配：数据库副本、审计钩子、进程内单例。

`milk_license` 保持零 app 依赖（便于编译交付），
所有需要数据库的能力（第三处冗余副本、审计日志）都在这里注入。
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.models import SystemSetting
from app.db.session import SessionLocal
from app.services.audit import write_audit
from milk_license.guard import install as install_guard
from milk_license.service import LicenseService
from milk_license.store import (
    STATE_FILENAME,
    FileBackend,
    LicenseStore,
    RegistryBackend,
    default_state_dir,
)

logger = logging.getLogger("milk_license.runtime")

SETTING_KEY = "license_state"


class DatabaseBackend:
    """数据库副本（第三处冗余，BL-LICENSE-001/009）。

    读取失败或缺失都不影响判定：LicenseStore 会忽略坏副本，
    并按「起点取最早 / 最大已见时间取最大」合并。
    """

    name = "database"

    def read(self) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            row = db.scalar(select(SystemSetting).where(SystemSetting.key == SETTING_KEY))
            if row is None or not row.value:
                return None
            data = json.loads(row.value)
            return data if isinstance(data, dict) else None
        except Exception:  # noqa: BLE001 - 副本损坏不应影响授权判定
            logger.warning("数据库授权副本读取失败，忽略该副本", exc_info=True)
            return None
        finally:
            db.close()

    def write(self, state: dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False, sort_keys=True)
        db = SessionLocal()
        try:
            row = db.scalar(select(SystemSetting).where(SystemSetting.key == SETTING_KEY))
            if row is None:
                db.add(SystemSetting(key=SETTING_KEY, value=payload))
            else:
                row.value = payload
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def _resolve_state_dir() -> Path:
    """状态目录：默认系统级固定路径；开发/测试可用 MILK_LICENSE_STATE_DIR 覆盖。

    安全说明：该覆盖位于 app 层（交付时仍是可读源码），属于「源码可改」这一残余风险；
    ``milk_license`` 编译模块本身不读取任何环境变量（ALIGN-015/F3）。
    """
    override = os.environ.get("MILK_LICENSE_STATE_DIR")
    return Path(override) if override else default_state_dir()


def build_store() -> LicenseStore:
    """生产默认：注册表（HKLM/HKCU）+ 系统级文件 + 数据库。

    ``MILK_LICENSE_DISABLE_REGISTRY=1`` 用于测试，避免污染真实注册表。
    """
    backends: list = []
    if os.name == "nt" and not os.environ.get("MILK_LICENSE_DISABLE_REGISTRY"):
        backends.append(RegistryBackend("HKLM"))
        backends.append(RegistryBackend("HKCU"))
    backends.append(FileBackend(_resolve_state_dir() / STATE_FILENAME))
    backends.append(DatabaseBackend())
    return LicenseStore(backends)


def audit_hook(action: str, detail: dict[str, Any]) -> None:
    """授权事件审计（BL-LICENSE-012）。失败不影响请求处理。"""
    db = SessionLocal()
    try:
        write_audit(db, action=action, resource_type="license", result="success", detail=detail)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("授权审计写入失败", exc_info=True)
    finally:
        db.close()


_service: LicenseService | None = None


def get_license_service() -> LicenseService:
    """进程内单例（守卫中间件与 /license 接口共用同一份缓存与状态）。"""
    global _service
    if _service is None:
        _service = LicenseService(store=build_store())
    return _service


def reset_license_service() -> None:
    """测试用：清空单例。"""
    global _service
    _service = None


def install_license_guard(app) -> LicenseService:
    return install_guard(app, service=get_license_service(), audit=audit_hook)
