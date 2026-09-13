from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Mapping

from sqlalchemy import select

from app.core.config import Settings, get_settings


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupResult:
    file_path: Path
    file_name: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime
    trigger: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_sqlite_snapshot(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(str(destination))
    try:
        source_connection.backup(destination_connection)
        destination_connection.commit()
    finally:
        destination_connection.close()
        source_connection.close()


def _copy_uploads(uploads_dir: Path, staging_dir: Path) -> None:
    if not uploads_dir.is_dir():
        return
    destination = staging_dir / "uploads"
    for source in sorted(path for path in uploads_dir.rglob("*") if path.is_file()):
        relative = source.relative_to(uploads_dir)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _runtime_config(settings: Settings, system_settings: Mapping[str, str]) -> dict:
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "api_prefix": settings.api_prefix,
        "database_filename": settings.database_filename,
        "smtp": {
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "use_ssl": settings.smtp_use_ssl,
            "recipient": settings.bug_report_recipient,
            "username_configured": bool(settings.smtp_username),
            "password_configured": bool(settings.smtp_password),
        },
        "system_settings": dict(sorted(system_settings.items())),
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _component(path: Path, archive_path: str, kind: str) -> dict:
    return {
        "path": archive_path,
        "kind": kind,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def create_complete_backup(
    settings: Settings,
    *,
    trigger: str,
    system_settings: Mapping[str, str] | None = None,
) -> BackupResult:
    if trigger not in {"manual", "scheduled", "pre_restore"}:
        raise ValueError(f"unsupported backup trigger: {trigger}")

    source = settings.data_dir / settings.database_filename
    if not source.is_file():
        raise BackupError("数据库文件不存在")

    backup_dir = settings.data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now().astimezone()
    stamp = created_at.strftime("%Y%m%dT%H%M%S%f%z")
    archive_name = f"milk-weigh-backup-{stamp}.zip"
    archive_path = backup_dir / archive_name
    checksum_path = archive_path.with_suffix(".zip.sha256")

    try:
        with tempfile.TemporaryDirectory(prefix=".backup-", dir=backup_dir) as temporary:
            staging_dir = Path(temporary)
            database_path = staging_dir / "database" / settings.database_filename
            _copy_sqlite_snapshot(source, database_path)
            _copy_uploads(settings.data_dir / "uploads", staging_dir)

            token_secret = settings.data_dir / "token_secret"
            if token_secret.is_file():
                secret_target = staging_dir / "config" / "token_secret"
                secret_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(token_secret, secret_target)

            config_path = staging_dir / "config" / "runtime.json"
            _write_json(config_path, _runtime_config(settings, system_settings or {}))

            components = []
            for path in sorted(item for item in staging_dir.rglob("*") if item.is_file()):
                relative = path.relative_to(staging_dir).as_posix()
                if relative.startswith("database/"):
                    kind = "database"
                elif relative.startswith("uploads/"):
                    kind = "evidence"
                else:
                    kind = "config"
                components.append(_component(path, relative, kind))

            manifest_path = staging_dir / "manifest.json"
            _write_json(
                manifest_path,
                {
                    "format_version": 1,
                    "trigger": trigger,
                    "created_at": created_at.isoformat(),
                    "app_version": settings.app_version,
                    "archive_name": archive_name,
                    "components": components,
                },
            )

            temporary_archive = backup_dir / f".{archive_name}.tmp"
            try:
                with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for path in sorted(item for item in staging_dir.rglob("*") if item.is_file()):
                        archive.write(path, path.relative_to(staging_dir).as_posix())
                archive_path.unlink(missing_ok=True)
                temporary_archive.replace(archive_path)
            finally:
                temporary_archive.unlink(missing_ok=True)

        checksum = _sha256_file(archive_path)
        checksum_path.write_text(f"{checksum}  {archive_name}\n", encoding="ascii")
        return BackupResult(
            file_path=archive_path,
            file_name=archive_name,
            size_bytes=archive_path.stat().st_size,
            checksum_sha256=checksum,
            created_at=created_at,
            trigger=trigger,
        )
    except (OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
        archive_path.unlink(missing_ok=True)
        checksum_path.unlink(missing_ok=True)
        raise BackupError(str(exc)) from exc


def parse_backup_time(value: str) -> time | None:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def is_backup_due(
    *,
    enabled: bool,
    backup_time: str,
    now: datetime,
    schedule_key: str | None,
) -> bool:
    scheduled_time = parse_backup_time(backup_time)
    if not enabled or scheduled_time is None:
        return False
    today_key = now.strftime("%Y-%m-%d")
    return now.time() >= scheduled_time and schedule_key != today_key


class BackupScheduler:
    def __init__(self, check_interval_seconds: int = 30) -> None:
        self.check_interval_seconds = max(5, check_interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="milk-backup-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.wait(self.check_interval_seconds):
            self.run_once()

    def run_once(self, now: datetime | None = None) -> bool:
        from app.db.models import BackupRecord, SystemSetting
        from app.db.session import SessionLocal
        from app.services.audit import write_audit

        current = now or datetime.now().astimezone()
        schedule_key = current.strftime("%Y-%m-%d")
        settings = get_settings()
        with SessionLocal() as db:
            values = {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}
            latest = db.scalar(
                select(BackupRecord)
                .where(BackupRecord.trigger == "scheduled", BackupRecord.schedule_key == schedule_key)
                .order_by(BackupRecord.created_at.desc())
            )
            if not is_backup_due(
                enabled=values.get("backup_enabled", "true").lower() == "true",
                backup_time=values.get("backup_time", "02:00"),
                now=current,
                schedule_key=latest.schedule_key if latest else None,
            ):
                return False

            try:
                result = create_complete_backup(settings, trigger="scheduled", system_settings=values)
                record = BackupRecord(
                    file_path=str(result.file_path),
                    status="success",
                    size_bytes=result.size_bytes,
                    trigger="scheduled",
                    schedule_key=schedule_key,
                    checksum_sha256=result.checksum_sha256,
                    app_version=settings.app_version,
                )
                db.add(record)
                db.flush()
                write_audit(
                    db,
                    actor_id=None,
                    action="backup.scheduled.created",
                    resource_type="backup",
                    resource_id=record.id,
                    detail={"schedule_key": schedule_key},
                )
                db.commit()
            except Exception as exc:
                db.add(
                    BackupRecord(
                        file_path=str(settings.data_dir / "backups"),
                        status="failed",
                        trigger="scheduled",
                        schedule_key=schedule_key,
                        app_version=settings.app_version,
                        error_message=str(exc)[:1000],
                    )
                )
                write_audit(
                    db,
                    actor_id=None,
                    action="backup.scheduled.failed",
                    resource_type="backup",
                    result="failure",
                    detail={"schedule_key": schedule_key, "error": str(exc)[:500]},
                )
                db.commit()
            return True


backup_scheduler = BackupScheduler()
