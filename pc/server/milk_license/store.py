"""授权状态的三处冗余存储。

设计要点（BL-LICENSE-001 / BL-LICENSE-009）：
  - 授权状态必须独立于数据库备份：恢复旧备份不得回滚试用起点或授权。
  - 多副本读取时：``trial_start`` 取**最早**（防把起点往后改以重置试用），
    ``max_seen_time`` 取**最大**（防时钟回拨），授权串取**到期最晚**者。
  - 任一副本缺失都不影响判定，只要还有一份可读。

后端可插拔：注册表（Windows）、系统级文件（ProgramData）、内存（测试）。
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

STATE_FILENAME = "license-state.json"
REGISTRY_SUBKEY = r"Software\Muheng\MilkWeigh"
REGISTRY_VALUE = "LicenseState"


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_time(value)
        return None if parsed is None else format_time(parsed)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class Backend(Protocol):
    name: str

    def read(self) -> dict[str, Any] | None: ...

    def write(self, state: dict[str, Any]) -> None: ...


class MemoryBackend:
    """内存后端（测试用）。"""

    def __init__(self, name: str = "memory", initial: dict[str, Any] | None = None) -> None:
        self.name = name
        self._state = dict(initial) if initial else None

    def read(self) -> dict[str, Any] | None:
        return dict(self._state) if self._state else None

    def write(self, state: dict[str, Any]) -> None:
        self._state = dict(state)


class FileBackend:
    """系统级 JSON 文件后端（默认 ``%PROGRAMDATA%\\MilkWeigh``）。"""

    def __init__(self, path: Path | str, name: str = "file") -> None:
        self.path = Path(path)
        self.name = name

    def read(self) -> dict[str, Any] | None:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2)
        # 原子写：先写临时文件再替换，避免断电产生半个文件
        fd, tmp_name = tempfile.mkstemp(dir=str(self.path.parent), prefix=".license-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


class RegistryBackend:
    """Windows 注册表后端。非 Windows 上为 no-op。"""

    def __init__(self, hive: str = "HKLM", name: str | None = None, subkey: str = REGISTRY_SUBKEY) -> None:
        self.hive_name = hive
        self.name = name or f"registry:{hive.lower()}"
        self.subkey = subkey
        self.available = os.name == "nt"

    def _hive(self):
        import winreg

        return {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[self.hive_name]

    def read(self) -> dict[str, Any] | None:
        if not self.available:
            return None
        import winreg

        try:
            with winreg.OpenKey(self._hive(), self.subkey) as key:
                raw, _ = winreg.QueryValueEx(key, REGISTRY_VALUE)
        except OSError:
            return None
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def write(self, state: dict[str, Any]) -> None:
        if not self.available:
            return
        import winreg

        raw = json.dumps(state, ensure_ascii=False, sort_keys=True)
        with winreg.CreateKeyEx(self._hive(), self.subkey, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, REGISTRY_VALUE, 0, winreg.REG_SZ, raw)


class LicenseStore:
    """多副本授权状态存储。"""

    def __init__(self, backends: list[Backend]) -> None:
        self.backends = list(backends)

    def read_all(self) -> list[dict[str, Any]]:
        copies: list[dict[str, Any]] = []
        for backend in self.backends:
            try:
                state = backend.read()
            except Exception:  # 单个副本损坏不应影响整体判定
                state = None
            if state:
                copies.append(state)
        return copies

    def read_merged(self) -> dict[str, Any]:
        """按「起点取最早 / 最大已见时间取最大 / 授权取到期最晚」合并所有副本。"""
        merged: dict[str, Any] = {
            "trial_start": None,
            "max_seen_time": None,
            "license_code": None,
            "license_expires_at": None,
        }
        for state in self.read_all():
            start = parse_time(state.get("trial_start"))
            if start and (merged["trial_start"] is None or start < merged["trial_start"]):
                merged["trial_start"] = start

            seen = parse_time(state.get("max_seen_time"))
            if seen and (merged["max_seen_time"] is None or seen > merged["max_seen_time"]):
                merged["max_seen_time"] = seen

            code = state.get("license_code")
            if isinstance(code, str) and code:
                expires = parse_time(state.get("license_expires_at"))
                current = merged["license_expires_at"]
                if merged["license_code"] is None or (expires and (current is None or expires > current)):
                    merged["license_code"] = code
                    merged["license_expires_at"] = expires
        return merged

    def write(self, state: dict[str, Any]) -> None:
        for backend in self.backends:
            try:
                backend.write(state)
            except Exception:  # 单个副本写失败不阻塞其余副本
                continue

    def update(self, **changes: Any) -> dict[str, Any]:
        merged = self.read_merged()
        for key, value in changes.items():
            if isinstance(value, datetime):
                value = format_time(value)
            merged[key] = value
        payload = {
            "trial_start": format_time(merged["trial_start"]),
            "max_seen_time": format_time(merged["max_seen_time"]),
            "license_code": merged.get("license_code"),
            "license_expires_at": format_time(merged.get("license_expires_at")),
        }
        self.write(payload)
        return payload


def default_state_dir() -> Path:
    """系统级状态目录。

    安全约束：**不读取任何环境变量**（否则客户可用环境变量把状态重定向到空目录以重置试用，
    见 ALIGN-015/F3）。开发/测试需要改目录时，由 app 层显式传入（见 app/license_runtime.py）。
    """
    if os.name == "nt":
        return Path(r"C:\ProgramData") / "MilkWeigh"
    return Path.home() / ".milkweigh"


def build_default_store() -> LicenseStore:
    """生产默认：注册表（HKLM/HKCU）+ 系统级文件。

    数据库副本由 app 层通过 ``DatabaseBackend`` 注入（见 app/license_db.py），
    以保持 milk_license 不依赖 SQLAlchemy。
    """
    backends: list[Backend] = []
    if os.name == "nt":
        backends.append(RegistryBackend("HKLM"))
        backends.append(RegistryBackend("HKCU"))
    backends.append(FileBackend(default_state_dir() / STATE_FILENAME))
    return LicenseStore(backends)
