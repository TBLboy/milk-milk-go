from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, time, timezone
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


def parse_retention_years(value: str | None) -> int | None:
    """Return retention in months, or None for permanent retention.

    ``0`` means permanent. Otherwise the value is a positive month count.
    """
    if value is None:
        return 12
    text = value.strip()
    if text == "":
        return 12
    try:
        months = int(text)
    except (TypeError, ValueError):
        return None
    if months < 0:
        return None
    return months


def parse_keep_count(value: str | None) -> int | None:
    if value is None:
        return 60
    text = value.strip()
    if text == "":
        return 60
    try:
        count = int(text)
    except (TypeError, ValueError):
        return None
    if not 10 <= count <= 365:
        return None
    return count


def validate_backup_path(value: str) -> str | None:
    """Return an error message when the configured backup path is unusable."""
    text = value.strip()
    if text == "":
        return None
    if text.startswith("\\\\") or text.startswith("//"):
        return "备份路径不能是网络路径"
    return None


def resolve_backup_dir(settings: Settings, system_settings: Mapping[str, str] | None) -> Path:
    """Return the configured backup directory, falling back to the data directory.

    The config file wins over the database value so a restore cannot silently
    redirect backups to a stale path.
    """
    conf_path = settings.data_dir / "backup_path.conf"
    if conf_path.is_file():
        try:
            configured = conf_path.read_text(encoding="utf-8").strip()
        except OSError:
            configured = ""
        if configured:
            return Path(configured).expanduser()
    configured = (system_settings or {}).get("backup_path", "").strip()
    if configured:
        return Path(configured).expanduser()
    return settings.data_dir / "backups"


def _retention_cutoff(months: int, now: datetime) -> datetime:
    """Compute the cutoff timestamp for a month-based retention window."""
    total_months = now.year * 12 + (now.month - 1) - months
    year, month_index = divmod(total_months, 12)
    month = month_index + 1
    day = min(now.day, 28)
    return now.replace(year=year, month=month, day=day)


def _filter_business_data(database_path: Path, retention_months: int, now: datetime) -> dict:
    """Delete work-order business data older than the retention window.

    Master data (materials, products, recipes, users) is preserved. Cascading
    evidence, weighing, approval and audit rows tied to expired work orders are
    removed, and the returned ``kept_file_ids`` lists evidence files still
    referenced so the caller can prune orphaned uploads.
    """
    cutoff = _retention_cutoff(retention_months, now)
    cutoff_text = cutoff.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    connection = sqlite3.connect(str(database_path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "work_orders" not in tables:
            return {
                "expired_work_orders": 0,
                "expired_file_ids": set(),
                "expired_stored_paths": set(),
                "cutoff": cutoff.isoformat(),
            }
        expired = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM work_orders WHERE created_at < ?", (cutoff_text,)
            ).fetchall()
        ]
        if expired:
            placeholders = ",".join("?" for _ in expired)
            step_ids = [
                row[0]
                for row in connection.execute(
                    f"SELECT id FROM work_order_steps WHERE work_order_id IN ({placeholders})",
                    expired,
                ).fetchall()
            ]
            expired_file_ids: set[str] = set()
            if step_ids:
                step_placeholders = ",".join("?" for _ in step_ids)
                expired_file_ids |= {
                    row[0]
                    for row in connection.execute(
                        f"SELECT evidence_file_id FROM type_confirmations WHERE work_order_step_id IN ({step_placeholders}) AND evidence_file_id IS NOT NULL",
                        step_ids,
                    ).fetchall()
                }
                expired_file_ids |= {
                    row[0]
                    for row in connection.execute(
                        f"SELECT scale_photo_file_id FROM weighing_attempts WHERE work_order_step_id IN ({step_placeholders}) AND scale_photo_file_id IS NOT NULL",
                        step_ids,
                    ).fetchall()
                }
                connection.execute(
                    f"DELETE FROM type_confirmations WHERE work_order_step_id IN ({step_placeholders})",
                    step_ids,
                )
                connection.execute(
                    f"DELETE FROM weighing_attempts WHERE work_order_step_id IN ({step_placeholders})",
                    step_ids,
                )
            connection.execute(
                f"DELETE FROM work_order_steps WHERE work_order_id IN ({placeholders})",
                expired,
            )
            connection.execute(
                f"DELETE FROM work_order_requests WHERE work_order_id IN ({placeholders})",
                expired,
            )
            order_nos = [
                row[0]
                for row in connection.execute(
                    f"SELECT order_no FROM work_orders WHERE id IN ({placeholders})",
                    expired,
                ).fetchall()
            ]
            connection.execute(
                f"DELETE FROM work_orders WHERE id IN ({placeholders})", expired
            )
            if order_nos:
                order_placeholders = ",".join("?" for _ in order_nos)
                connection.execute(
                    f"DELETE FROM audit_logs WHERE work_order_no IN ({order_placeholders})",
                    order_nos,
                )
            if expired_file_ids:
                file_placeholders = ",".join("?" for _ in expired_file_ids)
                expired_stored_paths = {
                    row[0]
                    for row in connection.execute(
                        f"SELECT stored_path FROM evidence_files WHERE file_id IN ({file_placeholders})",
                        list(expired_file_ids),
                    ).fetchall()
                }
                connection.execute(
                    f"DELETE FROM evidence_files WHERE file_id IN ({file_placeholders})",
                    list(expired_file_ids),
                )
            else:
                expired_stored_paths = set()
        else:
            expired_file_ids = set()
            expired_stored_paths = set()
        connection.commit()
        return {
            "expired_work_orders": len(expired),
            "expired_file_ids": expired_file_ids,
            "expired_stored_paths": expired_stored_paths,
            "cutoff": cutoff.isoformat(),
        }
    finally:
        connection.close()

def _prune_uploads(uploads_dir: Path, expired_stored_paths: set[str]) -> int:
    """Remove upload files whose evidence record was filtered out.

    ``stored_path`` values point at the live data directory, so only the file
    name is used to locate the copy inside the staging uploads directory.
    """
    if not uploads_dir.is_dir() or not expired_stored_paths:
        return 0
    expired_names = {Path(value).name for value in expired_stored_paths}
    removed = 0
    for source in sorted(path for path in uploads_dir.rglob("*") if path.is_file()):
        if source.name in expired_names:
            source.unlink(missing_ok=True)
            removed += 1
    return removed


def _prune_backups(backup_dir: Path, keep_count: int) -> list[str]:
    """Delete the oldest backup archives beyond ``keep_count``."""
    archives = sorted(
        (path for path in backup_dir.glob("milk-weigh-backup-*.zip") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
    )
    removed: list[str] = []
    for archive in archives[:-keep_count] if keep_count > 0 else []:
        archive.unlink(missing_ok=True)
        archive.with_suffix(".zip.sha256").unlink(missing_ok=True)
        removed.append(archive.name)
    return removed


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

    backup_dir = resolve_backup_dir(settings, system_settings)
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

            filter_summary = None
            if trigger != "pre_restore":
                retention_months = parse_retention_years(
                    (system_settings or {}).get("backup_retention_years")
                )
                if retention_months is None:
                    raise BackupError("备份保留年限配置无效")
                if retention_months > 0:
                    filter_summary = _filter_business_data(
                        database_path, retention_months, created_at
                    )
                    _prune_uploads(
                        staging_dir / "uploads", filter_summary["expired_stored_paths"]
                    )

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
                    "retention": (
                        {
                            "expired_work_orders": filter_summary["expired_work_orders"],
                            "expired_file_ids": sorted(filter_summary["expired_file_ids"]),
                            "cutoff": filter_summary["cutoff"],
                        }
                        if filter_summary is not None
                        else None
                    ),                },
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
        if trigger != "pre_restore":
            keep_count = parse_keep_count(
                (system_settings or {}).get("backup_keep_count")
            )
            if keep_count is not None:
                _prune_backups(backup_dir, keep_count)
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


def parse_backup_times(value: str | None) -> list[time] | None:
    """Parse a comma-separated list of HH:MM times; None when any entry is invalid."""
    if value is None:
        return []
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not entries:
        return []
    parsed: list[time] = []
    for entry in entries:
        moment = parse_backup_time(entry)
        if moment is None:
            return None
        parsed.append(moment)
    return sorted(set(parsed))


def is_backup_due(
    *,
    enabled: bool,
    backup_time: str,
    now: datetime,
    schedule_key: str | None,
) -> bool:
    scheduled_times = parse_backup_times(backup_time)
    if not enabled or not scheduled_times:
        return False
    today_key = now.strftime("%Y-%m-%d")
    if schedule_key == today_key:
        return False
    return any(now.time() >= moment for moment in scheduled_times)


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
        settings = get_settings()
        with SessionLocal() as db:
            values = {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}
            if values.get("backup_enabled", "true").lower() != "true":
                return False
            scheduled_times = parse_backup_times(values.get("backup_time", "12:00,20:00"))
            if not scheduled_times:
                return False
            today_key = current.strftime("%Y-%m-%d")
            due_slots = [
                moment
                for moment in scheduled_times
                if current.time() >= moment
            ]
            if not due_slots:
                return False
            executed_keys = {
                row.schedule_key
                for row in db.scalars(
                    select(BackupRecord).where(
                        BackupRecord.trigger == "scheduled",
                        BackupRecord.schedule_key.like(f"{today_key}#%"),
                    )
                ).all()
            }
            pending_slots = [
                moment
                for moment in due_slots
                if f"{today_key}#{moment.strftime('%H:%M')}" not in executed_keys
            ]
            if not pending_slots:
                return False
            slot = pending_slots[0]
            schedule_key = f"{today_key}#{slot.strftime('%H:%M')}"

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
