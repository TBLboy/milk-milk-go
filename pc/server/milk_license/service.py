"""LicenseService：授权状态查询、缓存、解锁。

- 状态判定基准时间 = max(当前时间, 已记录的最大已见时间)，见 state.evaluate。
- 首次运行时写入试用起点（BL-LICENSE-001）。
- 最大已见时间按小时节流持久化，避免每个请求都写磁盘/注册表。
- 结果做短 TTL 缓存，使守卫中间件不必每请求都读注册表。
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from milk_license import codec, keys, state
from milk_license.store import LicenseStore, build_default_store

SEEN_WRITE_INTERVAL = timedelta(hours=1)
DEFAULT_CACHE_TTL_SECONDS = 10.0


class LicenseService:
    def __init__(
        self,
        store: LicenseStore | None = None,
        public_key: bytes | None = None,
        now_fn: Callable[[], datetime] | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self.store = store if store is not None else build_default_store()
        self.public_key = public_key if public_key is not None else keys.public_key()
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._cache_ttl = cache_ttl
        self._lock = threading.RLock()
        self._cached: state.LicenseStatus | None = None
        self._cached_at: datetime | None = None
        self._last_mode: str | None = None
        self._last_rollback = False
        self._last_anomaly = False
        self._last_warn_node: int | None = None

    # ── 内部 ──────────────────────────────────────────────────

    def now(self) -> datetime:
        value = self._now_fn()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def invalidate(self) -> None:
        with self._lock:
            self._cached = None
            self._cached_at = None

    # ── 对外 ──────────────────────────────────────────────────

    def status(self, *, force: bool = False) -> state.LicenseStatus:
        """当前授权状态（带 TTL 缓存）。"""
        with self._lock:
            now = self.now()
            if (
                not force
                and self._cached is not None
                and self._cached_at is not None
                and (now - self._cached_at).total_seconds() < self._cache_ttl
            ):
                return self._cached

            merged = self.store.read_merged()
            if merged.get("trial_start") is None:
                # 首次运行：把当前时间登记为试用起点（三处冗余写入）
                self.store.update(trial_start=now, max_seen_time=now)
                merged = self.store.read_merged()

            result = state.evaluate(now, merged, self.public_key)

            seen = merged.get("max_seen_time")
            if seen is None or now > seen + SEEN_WRITE_INTERVAL:
                # 前向跳变必须被吸收（ALIGN-015/F4）：若只按上限推进，已锁定的客户把时钟调回
                # 上限之后即可重新变成 active，等于绕过了整个授权机制。
                # 因此这里吸收异常时间，恢复走「管理员输入解锁码」（unlock 会把基准重置为当前时间）。
                self.store.update(max_seen_time=now)

            self._cached = result
            self._cached_at = now
            return result

    def mode(self) -> str:
        return self.status().mode

    def mode_transition(self) -> str | None:
        """返回「刚刚观察到的状态」，仅在状态相对上次观察发生变化时返回，否则 None。

        进程启动后第一次调用也会返回（用于记录启动时的受限状态）。
        """
        current = self.mode()
        with self._lock:
            if current != self._last_mode:
                self._last_mode = current
                return current
        return None

    def rollback_transition(self) -> bool:
        """检测到时钟回拨时返回 True；仅在「未检测到 → 检测到」的跃迁时返回 True（BL-LICENSE-012）。

        回拨状态恢复后会复位，因此再次发生回拨仍会被记录。
        """
        detected = self.status().clock_rollback_detected
        with self._lock:
            if detected and not self._last_rollback:
                self._last_rollback = True
                return True
            if not detected:
                self._last_rollback = False
        return False

    def anomaly_transition(self) -> bool:
        """检测到前向时钟跳变异常时返回 True；仅在跃迁时返回 True（BL-LICENSE-012 的时钟异常事件）。"""
        detected = self.status().clock_anomaly_detected
        with self._lock:
            if detected and not self._last_anomaly:
                self._last_anomaly = True
                return True
            if not detected:
                self._last_anomaly = False
        return False

    def warn_node_transition(self) -> int | None:
        """返回刚跨入的到期提醒节点（30/15/7/3/1），仅在节点变化时返回（BL-LICENSE-012）。

        语义说明：按进程内跃迁去重；进程重启后若仍处于提醒窗口，会再记录一次该节点
        （审计日志因此可能包含重复节点，但不会漏记）。
        """
        node = self.status().warn_node
        with self._lock:
            if node != self._last_warn_node:
                self._last_warn_node = node
                return node
        return None

    def unlock(self, code: str) -> state.LicenseStatus:
        """校验解锁码并写入授权；验签失败抛 codec.LicenseError。"""
        payload = codec.decode_license(code, self.public_key)
        expires = codec.expires_at(payload)
        self.store.update(
            license_code=code,
            license_expires_at=expires,
            max_seen_time=self.now(),
        )
        self.invalidate()
        return self.status(force=True)
