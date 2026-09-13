from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.services.backup import BackupResult, create_complete_backup


class RestoreError(RuntimeError):
    pass


REQUIRED_TABLES = {
    "users",
    "evidence_files",
    "work_orders",
    "work_order_steps",
    "type_confirmations",
    "weighing_attempts",
    "system_settings",
}
MAX_ARCHIVE_ENTRIES = 100_000
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024 * 1024
JOURNAL_NAME = ".restore-journal.json"


@dataclass(frozen=True)
class BackupPackage:
    archive_path: Path
    manifest: dict
    database_member: str
    token_secret_member: str | None
    upload_members: tuple[str, ...]


@dataclass(frozen=True)
class RestoreResult:
    archive_path: Path
    pre_restore_backup: Path | None
    users: int
    work_orders: int
    evidence_files: int
    restored_at: datetime


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in path.parts[0]
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise RestoreError(f"备份包包含不安全路径：{name}")


def _validate_sidecar(archive_path: Path, expected_checksum: str | None) -> str:
    checksum_path = archive_path.with_suffix(".zip.sha256")
    if not checksum_path.is_file():
        raise RestoreError("缺少备份 SHA-256 校验文件，拒绝恢复")
    parts = checksum_path.read_text(encoding="ascii").strip().split()
    if len(parts) != 2 or parts[1].lstrip("*") != archive_path.name:
        raise RestoreError("备份 SHA-256 校验文件格式无效")
    actual = _sha256_file(archive_path)
    if parts[0].lower() != actual:
        raise RestoreError("备份包 SHA-256 校验失败")
    if expected_checksum and expected_checksum.lower() != actual:
        raise RestoreError("备份包与预期 SHA-256 不一致")
    return actual


def inspect_backup_archive(archive_path: Path, expected_checksum: str | None = None) -> BackupPackage:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise RestoreError("备份包不存在")
    _validate_sidecar(archive_path, expected_checksum)

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                raise RestoreError("备份包文件数量异常")
            if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise RestoreError("备份包解压后大小超过限制")

            normalized_names: set[str] = set()
            files: dict[str, zipfile.ZipInfo] = {}
            for info in infos:
                _validate_member_name(info.filename)
                key = info.filename.casefold()
                if key in normalized_names:
                    raise RestoreError(f"备份包包含重复路径：{info.filename}")
                normalized_names.add(key)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise RestoreError(f"备份包包含不允许的符号链接：{info.filename}")
                if not info.is_dir():
                    files[info.filename] = info

            manifest_info = files.get("manifest.json")
            if manifest_info is None or manifest_info.file_size > 1024 * 1024:
                raise RestoreError("缺少有效 manifest.json")
            try:
                manifest = json.loads(archive.read(manifest_info))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RestoreError("manifest.json 无法解析") from exc
            if manifest.get("format_version") != 1:
                raise RestoreError("不支持的备份格式版本")
            components = manifest.get("components")
            if not isinstance(components, list):
                raise RestoreError("manifest.json 缺少文件校验清单")

            component_map: dict[str, dict] = {}
            for component in components:
                if not isinstance(component, dict):
                    raise RestoreError("manifest.json 文件校验项无效")
                name = component.get("path")
                if not isinstance(name, str):
                    raise RestoreError("manifest.json 文件路径无效")
                _validate_member_name(name)
                if name == "manifest.json" or name in component_map:
                    raise RestoreError(f"manifest.json 文件清单重复或无效：{name}")
                component_map[name] = component

            file_names = set(files) - {"manifest.json"}
            if file_names != set(component_map):
                raise RestoreError("备份包内容与 manifest.json 文件清单不一致")

            for name, component in component_map.items():
                info = files[name]
                expected_size = component.get("size_bytes")
                expected_hash = component.get("sha256")
                if not isinstance(expected_size, int) or info.file_size != expected_size:
                    raise RestoreError(f"备份文件大小不一致：{name}")
                if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                    raise RestoreError(f"备份文件哈希无效：{name}")
                digest = hashlib.sha256()
                with archive.open(info) as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest() != expected_hash.lower():
                    raise RestoreError(f"备份文件哈希校验失败：{name}")

            database_members = [name for name in files if name.startswith("database/")]
            if len(database_members) != 1:
                raise RestoreError("备份包必须且只能包含一个 SQLite 数据库")
            if "config/runtime.json" not in files:
                raise RestoreError("备份包缺少运行配置")
            token_secret_member = "config/token_secret" if "config/token_secret" in files else None
            upload_members = tuple(sorted(name for name in files if name.startswith("uploads/")))
            return BackupPackage(
                archive_path=archive_path,
                manifest=manifest,
                database_member=database_members[0],
                token_secret_member=token_secret_member,
                upload_members=upload_members,
            )
    except zipfile.BadZipFile as exc:
        raise RestoreError("备份包不是有效的 ZIP 文件") from exc


def _extract_archive(package: BackupPackage, destination: Path) -> None:
    try:
        with zipfile.ZipFile(package.archive_path, "r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                target = destination / PurePosixPath(info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RestoreError(f"备份包解压失败：{exc}") from exc


def _relative_upload_path(stored_path: str) -> PurePosixPath:
    normalized = stored_path.replace("\\", "/")
    marker = "/uploads/"
    if marker in normalized:
        relative = normalized.split(marker, 1)[1]
    elif normalized.startswith("uploads/"):
        relative = normalized[len("uploads/") :]
    else:
        raise RestoreError(f"证据文件路径不在 uploads 目录：{stored_path}")
    path = PurePosixPath(relative)
    _validate_member_name(path.as_posix())
    if path.name in {"", ".", ".."}:
        raise RestoreError(f"证据文件相对路径无效：{stored_path}")
    return path


def _read_system_settings(database_path: Path) -> dict[str, str]:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute("SELECT key, value FROM system_settings").fetchall()
    return {str(key): str(value) for key, value in rows}


def _validate_database(database_path: Path, uploads_dir: Path, target_data_dir: Path) -> tuple[int, int, int]:
    try:
        with closing(sqlite3.connect(database_path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RestoreError("SQLite 完整性检查失败")
            table_rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            tables = {row[0] for row in table_rows}
            missing = REQUIRED_TABLES - tables
            if missing:
                raise RestoreError(f"备份数据库缺少必要数据表：{', '.join(sorted(missing))}")

            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            work_order_count = connection.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0]
            evidence_rows = connection.execute(
                "SELECT id, file_id, stored_path, size_bytes, sha256 FROM evidence_files ORDER BY id"
            ).fetchall()
            evidence_ids = {row[1] for row in evidence_rows}
            for evidence_id, file_id, stored_path, expected_size, expected_hash in evidence_rows:
                relative = _relative_upload_path(str(stored_path))
                source = uploads_dir / relative
                if not source.is_file():
                    raise RestoreError(f"证据文件缺失：{file_id}")
                if source.stat().st_size != int(expected_size):
                    raise RestoreError(f"证据文件大小不一致：{file_id}")
                if expected_hash and _sha256_file(source) != expected_hash:
                    raise RestoreError(f"证据文件哈希不一致：{file_id}")

            reference_queries = [
                ("users", "avatar_file_id"),
                ("material_images", "file_id"),
                ("product_images", "file_id"),
                ("type_confirmations", "evidence_file_id"),
                ("weighing_attempts", "scale_photo_file_id"),
                ("bug_reports", "image_file_ids_json"),
            ]
            for table, column in reference_queries:
                if table not in tables:
                    continue
                for (value,) in connection.execute(f'SELECT {column} FROM {table} WHERE {column} IS NOT NULL'):
                    if table == "bug_reports":
                        try:
                            refs = json.loads(value)
                        except (TypeError, json.JSONDecodeError) as exc:
                            raise RestoreError("BUG 反馈图片引用格式无效") from exc
                    else:
                        refs = [value]
                    for file_id in refs:
                        if file_id and file_id not in evidence_ids:
                            raise RestoreError(f"业务记录引用了不存在的证据文件：{file_id}")

            updates = []
            for _, file_id, stored_path, _, _ in evidence_rows:
                relative = _relative_upload_path(str(stored_path))
                updates.append((str(target_data_dir / "uploads" / relative), file_id))
            connection.executemany("UPDATE evidence_files SET stored_path = ? WHERE file_id = ?", updates)
            connection.commit()
            return int(user_count), int(work_order_count), len(evidence_rows)
    except sqlite3.Error as exc:
        raise RestoreError(f"备份数据库校验失败：{exc}") from exc


def _write_restore_audit(
    database_path: Path,
    package: BackupPackage,
    *,
    result: str,
    detail: dict,
) -> None:
    if not database_path.is_file():
        return
    with closing(sqlite3.connect(database_path)) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(audit_logs)").fetchall()
        }
        if not columns:
            return
        values = {
            "actor_id": None,
            "action": "system.restored" if result == "success" else "system.restore_failed",
            "result": result,
            "resource_type": "backup",
            "resource_id": package.archive_path.name,
            "work_order_no": None,
            "detail_json": json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        selected = [key for key in values if key in columns]
        placeholders = ", ".join("?" for _ in selected)
        connection.execute(
            f"INSERT INTO audit_logs ({', '.join(selected)}) VALUES ({placeholders})",
            [values[key] for key in selected],
        )
        connection.commit()


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _move_path(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir() and not source.is_symlink():
        shutil.move(str(source), str(destination))
    else:
        os.replace(source, destination)


def _database_sidecars(database_path: Path) -> tuple[Path, Path]:
    return (
        database_path.with_name(f"{database_path.name}-wal"),
        database_path.with_name(f"{database_path.name}-shm"),
    )


def _remove_database_files(database_path: Path) -> None:
    _remove_path(database_path)
    for sidecar in _database_sidecars(database_path):
        _remove_path(sidecar)


def _restore_database_files(
    *,
    target: Path,
    rollback_dir: Path,
    had_original: bool,
) -> None:
    rollback_database = rollback_dir / "database"
    if had_original:
        if not rollback_database.exists():
            if target.exists():
                raise RestoreError("恢复中断且回滚数据库缺失：database")
            return
        _remove_database_files(target)
        _move_path(rollback_database, target)
        for suffix in ("-wal", "-shm"):
            rollback_sidecar = rollback_dir / f"database{suffix}"
            if rollback_sidecar.exists():
                _move_path(rollback_sidecar, target.with_name(f"{target.name}{suffix}"))
        return
    _remove_database_files(target)


def recover_interrupted_restore(data_dir: Path) -> bool:
    journal_path = data_dir / JOURNAL_NAME
    if not journal_path.is_file():
        return False
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestoreError("检测到无法解析的恢复日志，拒绝自动覆盖当前数据") from exc

    rollback_dir = data_dir / journal["rollback_dir"]
    for key in ("database", "uploads", "token_secret"):
        if not journal["managed"][key]:
            continue
        target = data_dir / journal["targets"][key]
        had_original = bool(journal["had_original"][key])
        if key == "database":
            _restore_database_files(
                target=target,
                rollback_dir=rollback_dir,
                had_original=had_original,
            )
            continue
        rollback = rollback_dir / key
        if had_original:
            if rollback.exists():
                _remove_path(target)
                _move_path(rollback, target)
            elif not target.exists():
                raise RestoreError(f"恢复中断且回滚文件缺失：{key}")
        else:
            _remove_path(target)
    _remove_path(rollback_dir)
    journal_path.unlink(missing_ok=True)
    return True


def _write_journal(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def restore_complete_backup(
    archive_path: Path,
    settings: Settings,
    *,
    expected_checksum: str | None = None,
) -> RestoreResult:
    data_dir = settings.data_dir.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    recover_interrupted_restore(data_dir)
    package = inspect_backup_archive(archive_path, expected_checksum)
    if PurePosixPath(package.database_member).name != settings.database_filename:
        raise RestoreError("备份数据库文件名与当前系统不匹配")

    staging_dir = Path(tempfile.mkdtemp(prefix=".restore-staging-", dir=data_dir))
    rollback_dir = Path(tempfile.mkdtemp(prefix=".restore-rollback-", dir=data_dir))
    journal_path = data_dir / JOURNAL_NAME
    current_database = data_dir / settings.database_filename
    pre_restore_backup: BackupResult | None = None
    try:
        _extract_archive(package, staging_dir)
        staged_database = staging_dir / package.database_member
        staged_uploads = staging_dir / "uploads"
        staged_runtime = staging_dir / "config" / "runtime.json"
        staged_token = staging_dir / package.token_secret_member if package.token_secret_member else None
        try:
            runtime_config = json.loads(staged_runtime.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RestoreError("备份运行配置无法解析") from exc
        if runtime_config.get("database_filename") != settings.database_filename:
            raise RestoreError("备份运行配置中的数据库文件名不匹配")

        user_count, work_order_count, evidence_count = _validate_database(
            staged_database,
            staged_uploads,
            data_dir,
        )

        if current_database.is_file():
            pre_restore_backup = create_complete_backup(
                settings,
                trigger="pre_restore",
                system_settings=_read_system_settings(current_database),
            )

        targets = {
            "database": settings.database_filename,
            "uploads": "uploads",
            "token_secret": "token_secret",
        }
        had_original = {
            "database": current_database.exists(),
            "uploads": (data_dir / "uploads").exists(),
            "token_secret": (data_dir / "token_secret").exists(),
        }
        managed = {
            "database": True,
            "uploads": True,
            "token_secret": staged_token is not None,
        }
        _write_journal(
            journal_path,
            {
                "rollback_dir": rollback_dir.name,
                "targets": targets,
                "managed": managed,
                "had_original": had_original,
            },
        )

        for key in ("database", "uploads", "token_secret"):
            if not managed[key]:
                continue
            target = data_dir / targets[key]
            if had_original[key]:
                if key == "database":
                    _move_path(target, rollback_dir / "database")
                    for suffix in ("-wal", "-shm"):
                        sidecar = target.with_name(f"{target.name}{suffix}")
                        if sidecar.exists():
                            _move_path(sidecar, rollback_dir / f"database{suffix}")
                else:
                    _move_path(target, rollback_dir / key)
            elif key == "database":
                _remove_database_files(target)
            elif target.exists():
                _remove_path(target)

        for sidecar in _database_sidecars(current_database):
            _remove_path(sidecar)
        _move_path(staged_database, current_database)
        if staged_uploads.is_dir():
            _move_path(staged_uploads, data_dir / "uploads")
        else:
            (data_dir / "uploads").mkdir(parents=True, exist_ok=True)
        if staged_token:
            _move_path(staged_token, data_dir / "token_secret")

        _validate_database(current_database, data_dir / "uploads", data_dir)
        _write_restore_audit(
            current_database,
            package,
            result="success",
            detail={
                "users": user_count,
                "work_orders": work_order_count,
                "evidence_files": evidence_count,
                "pre_restore_backup": pre_restore_backup.file_name if pre_restore_backup else None,
                "restored_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        journal_path.unlink(missing_ok=True)
        try:
            _remove_path(rollback_dir)
        except OSError:
            pass
        return RestoreResult(
            archive_path=package.archive_path,
            pre_restore_backup=pre_restore_backup.file_path if pre_restore_backup else None,
            users=user_count,
            work_orders=work_order_count,
            evidence_files=evidence_count,
            restored_at=datetime.now().astimezone(),
        )
    except Exception as exc:
        recovery_error: Exception | None = None
        if journal_path.is_file():
            try:
                recover_interrupted_restore(data_dir)
            except Exception as rollback_exc:
                recovery_error = rollback_exc
        if recovery_error is not None:
            raise RestoreError(f"恢复失败且自动回滚失败：{recovery_error}") from exc
        if current_database.exists():
            try:
                _write_restore_audit(
                    current_database,
                    package,
                    result="failure",
                    detail={"error": str(exc)[:1000], "rolled_back": True},
                )
            except (OSError, sqlite3.Error):
                pass
        raise
    finally:
        _remove_path(staging_dir)
