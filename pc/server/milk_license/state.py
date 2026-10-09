"""授权状态判定。

状态机（BL-LICENSE-002/003/005）：

    试用中 / 授权有效 ──到期──▶ 只读宽限（15 天）──宽限满──▶ 完全锁定

关键不变量：
  - 判定基准时间 = max(系统当前时间, 已记录的最大已见时间)，使时钟回拨无法延长授权。
  - 试用期按「自然月」计算（2 个月），不是固定 60 天。
  - 只有验签通过的授权串才参与判定；验签失败一律退回试用口径。
"""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from milk_license import codec

TRIAL_MONTHS = 2
WARN_DAYS = 30
GRACE_DAYS = 15
WARN_NODES = (30, 15, 7, 3, 1)
# 单次前向跳变上限：超过即判定为时钟异常，不把异常未来时间吸收为「已见最大时间」
# （否则主板电池失效等导致的时间跳变会造成永久锁定，ALIGN-015/F4）
MAX_FORWARD_JUMP_DAYS = 7

MODE_ACTIVE = "active"
MODE_READ_ONLY = "read_only"
MODE_LOCKED = "locked"


def add_months(value: datetime, months: int) -> datetime:
    """按自然月推进（处理月末与闰年）。"""
    total = value.month - 1 + months
    year = value.year + total // 12
    month = total % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


@dataclass
class LicenseStatus:
    mode: str
    source: str  # "trial" | "license"
    licensee: str | None
    issued_at: str | None
    expires_at: str | None
    deadline: str | None
    days_remaining: int
    grace_days_remaining: int
    warn: bool
    clock_rollback_detected: bool
    clock_anomaly_detected: bool
    effective_now: str
    trial_start: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def _days_between(later: datetime, earlier: datetime) -> int:
    """向下取整的天数差；同日内为 0。"""
    return max(0, (later - earlier).days)


def evaluate(
    now: datetime,
    state: dict,
    public_key: bytes,
    *,
    trial_months: int = TRIAL_MONTHS,
    grace_days: int = GRACE_DAYS,
    warn_days: int = WARN_DAYS,
) -> LicenseStatus:
    """计算当前授权状态。``state`` 为 ``LicenseStore.read_merged()`` 的结果。"""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    trial_start = state.get("trial_start")
    if isinstance(trial_start, str):
        from milk_license.store import parse_time

        trial_start = parse_time(trial_start)
    if trial_start is None:
        trial_start = now

    max_seen = state.get("max_seen_time")
    if isinstance(max_seen, str):
        from milk_license.store import parse_time

        max_seen = parse_time(max_seen)

    rollback = bool(max_seen and now < max_seen)
    anomaly = bool(max_seen and (now - max_seen) > timedelta(days=MAX_FORWARD_JUMP_DAYS))
    effective_now = max(now, max_seen) if max_seen else now

    payload = None
    code = state.get("license_code")
    if isinstance(code, str) and code:
        try:
            payload = codec.decode_license(code, public_key)
        except codec.LicenseError:
            payload = None  # 验签失败的授权一律不参与判定

    if payload is not None:
        source = "license"
        deadline = codec.expires_at(payload)
        licensee = payload.get("licensee")
        issued = payload.get("issued_at")
        expires = payload.get("expires_at")
    else:
        source = "trial"
        deadline = add_months(trial_start, trial_months)
        licensee = None
        issued = None
        expires = None

    grace_end = deadline + timedelta(days=grace_days)
    if effective_now < deadline:
        mode = MODE_ACTIVE
        days_remaining = _days_between(deadline, effective_now)
        grace_remaining = 0
    elif effective_now < grace_end:
        mode = MODE_READ_ONLY
        days_remaining = 0
        grace_remaining = max(1, (grace_end - effective_now).days + (1 if (grace_end - effective_now).seconds else 0))
    else:
        mode = MODE_LOCKED
        days_remaining = 0
        grace_remaining = 0

    return LicenseStatus(
        mode=mode,
        source=source,
        licensee=licensee,
        issued_at=issued,
        expires_at=expires,
        deadline=deadline.isoformat().replace("+00:00", "Z"),
        days_remaining=days_remaining,
        grace_days_remaining=grace_remaining,
        warn=mode == MODE_ACTIVE and days_remaining <= warn_days,
        clock_rollback_detected=rollback,
        clock_anomaly_detected=anomaly,
        effective_now=effective_now.isoformat().replace("+00:00", "Z"),
        trial_start=trial_start.isoformat().replace("+00:00", "Z"),
    )


def warn_node(days_remaining: int) -> bool:
    """是否命中显著提醒节点（BL-LICENSE-002）。"""
    return days_remaining in WARN_NODES
