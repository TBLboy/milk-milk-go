"""授权状态存储与判定测试（BL-LICENSE-001/002/003/005/008/009）。

覆盖：
  - 多副本合并规则：起点取最早、最大已见时间取最大、授权取到期最晚
  - 副本损坏/缺失不影响判定
  - 文件后端原子写（不残留临时文件）
  - 注册表后端真实往返（Windows）
  - 状态机边界：试用中 / 只读宽限 / 完全锁定
  - 时钟回拨防护、自然月推进、授权覆盖试用、验签失败回退试用
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from milk_license import codec, state
from milk_license.store import (
    FileBackend,
    LicenseStore,
    MemoryBackend,
    RegistryBackend,
    parse_time,
)

PUBLIC = bytes.fromhex("fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025")
SEED = bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")
T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def license_state(**overrides) -> dict:
    payload = {
        "v": 1,
        "licensee": "乍甸乳业",
        "issued_at": iso(T0),
        "expires_at": iso(T0 + timedelta(days=365)),
        "level": "full",
    }
    payload.update(overrides)
    return {"license_code": codec.issue_license(payload, SEED)}


# ── 多副本合并 ────────────────────────────────────────────────


def test_merge_takes_earliest_trial_start():
    store = LicenseStore(
        [
            MemoryBackend("a", {"trial_start": "2026-03-01T00:00:00Z"}),
            MemoryBackend("b", {"trial_start": "2026-01-01T00:00:00Z"}),
        ]
    )
    assert store.read_merged()["trial_start"] == parse_time("2026-01-01T00:00:00Z")


def test_merge_takes_latest_max_seen_time():
    store = LicenseStore(
        [
            MemoryBackend("a", {"max_seen_time": "2026-03-01T00:00:00Z"}),
            MemoryBackend("b", {"max_seen_time": "2026-06-01T00:00:00Z"}),
        ]
    )
    assert store.read_merged()["max_seen_time"] == parse_time("2026-06-01T00:00:00Z")


def test_merge_takes_license_with_latest_expiry():
    store = LicenseStore(
        [
            MemoryBackend("a", {"license_code": "AAA", "license_expires_at": "2027-01-01T00:00:00Z"}),
            MemoryBackend("b", {"license_code": "BBB", "license_expires_at": "2028-01-01T00:00:00Z"}),
        ]
    )
    assert store.read_merged()["license_code"] == "BBB"


def test_corrupted_copy_is_ignored():
    class Boom:
        name = "boom"

        def read(self):
            raise RuntimeError("disk on fire")

        def write(self, state):
            raise RuntimeError("disk on fire")

    store = LicenseStore([Boom(), MemoryBackend("good", {"trial_start": "2026-01-01T00:00:00Z"})])
    assert store.read_merged()["trial_start"] == parse_time("2026-01-01T00:00:00Z")


def test_write_failure_on_one_backend_does_not_block_others():
    class Boom:
        name = "boom"

        def read(self):
            return None

        def write(self, state):
            raise RuntimeError("read-only medium")

    good = MemoryBackend("good")
    LicenseStore([Boom(), good]).write({"trial_start": "2026-01-01T00:00:00Z"})
    assert good.read()["trial_start"] == "2026-01-01T00:00:00Z"


def test_update_merges_and_persists_all_backends():
    store = LicenseStore([MemoryBackend("a"), MemoryBackend("b")])
    store.update(trial_start=T0, max_seen_time=T0 + timedelta(days=3))
    merged = store.read_merged()
    assert merged["trial_start"] == T0
    assert merged["max_seen_time"] == T0 + timedelta(days=3)
    assert store.backends[0].read()["trial_start"] == iso(T0)


# ── 文件后端 ──────────────────────────────────────────────────


def test_file_backend_round_trip(tmp_path):
    backend = FileBackend(tmp_path / "nested" / "license-state.json")
    backend.write({"trial_start": iso(T0)})
    assert backend.read()["trial_start"] == iso(T0)


def test_file_backend_leaves_no_temp_files(tmp_path):
    backend = FileBackend(tmp_path / "license-state.json")
    for index in range(5):
        backend.write({"trial_start": iso(T0), "seq": index})
    assert backend.read()["seq"] == 4
    assert [p.name for p in tmp_path.iterdir()] == ["license-state.json"]


def test_file_backend_tolerates_corrupt_json(tmp_path):
    path = tmp_path / "license-state.json"
    path.write_text("{not json", encoding="utf-8")
    assert FileBackend(path).read() is None


def test_file_backend_ignores_non_object_json(tmp_path):
    path = tmp_path / "license-state.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert FileBackend(path).read() is None


# ── 注册表后端（仅 Windows） ──────────────────────────────────


@pytest.mark.skipif(__import__("os").name != "nt", reason="仅 Windows 有注册表")
def test_registry_backend_round_trip():
    import winreg

    subkey = rf"Software\Muheng\MilkWeighTest-{uuid.uuid4().hex[:12]}"
    backend = RegistryBackend("HKCU", subkey=subkey)
    try:
        assert backend.read() is None
        backend.write({"trial_start": iso(T0)})
        assert backend.read()["trial_start"] == iso(T0)
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, subkey)
        except OSError:
            pass


def test_registry_backend_is_noop_off_windows(monkeypatch):
    backend = RegistryBackend("HKCU")
    backend.available = False
    assert backend.read() is None
    backend.write({"trial_start": iso(T0)})  # 不抛异常


# ── 状态机 ────────────────────────────────────────────────────


def status_at(now: datetime, state_dict: dict) -> state.LicenseStatus:
    return state.evaluate(now, state_dict, PUBLIC)


def test_trial_is_active_within_two_calendar_months():
    deadline = state.add_months(T0, 2)
    result = status_at(deadline - timedelta(days=1), {"trial_start": T0})
    assert result.mode == state.MODE_ACTIVE
    assert result.source == "trial"
    assert result.days_remaining == 1


def test_trial_becomes_read_only_after_deadline():
    deadline = state.add_months(T0, 2)
    result = status_at(deadline + timedelta(days=1), {"trial_start": T0})
    assert result.mode == state.MODE_READ_ONLY
    assert result.days_remaining == 0
    assert result.grace_days_remaining == 14


def test_trial_locks_after_grace_period():
    deadline = state.add_months(T0, 2)
    result = status_at(deadline + timedelta(days=15), {"trial_start": T0})
    assert result.mode == state.MODE_LOCKED
    assert result.grace_days_remaining == 0


def test_grace_boundary_last_moment_is_still_read_only():
    deadline = state.add_months(T0, 2)
    result = status_at(deadline + timedelta(days=15) - timedelta(seconds=1), {"trial_start": T0})
    assert result.mode == state.MODE_READ_ONLY
    assert result.grace_days_remaining == 1


def test_warn_flag_inside_thirty_days():
    deadline = state.add_months(T0, 2)
    assert status_at(deadline - timedelta(days=29), {"trial_start": T0}).warn is True
    assert status_at(deadline - timedelta(days=31), {"trial_start": T0}).warn is False
    assert state.warn_node(7) is True
    assert state.warn_node(8) is False


def test_license_overrides_trial():
    state_dict = {"trial_start": T0, **license_state()}
    result = status_at(T0 + timedelta(days=100), state_dict)
    assert result.source == "license"
    assert result.mode == state.MODE_ACTIVE
    assert result.licensee == "乍甸乳业"
    assert result.days_remaining == 265


def test_expired_license_locks_after_grace():
    payload = {
        "v": 1,
        "licensee": "乍甸乳业",
        "issued_at": iso(T0),
        "expires_at": iso(T0 + timedelta(days=10)),
        "level": "full",
    }
    state_dict = {"trial_start": T0, "license_code": codec.issue_license(payload, SEED)}
    assert status_at(T0 + timedelta(days=20), state_dict).mode == state.MODE_READ_ONLY
    assert status_at(T0 + timedelta(days=30), state_dict).mode == state.MODE_LOCKED


def test_tampered_license_is_ignored_and_trial_applies():
    code = license_state()["license_code"]
    body, signature = code.split(".")
    forged = codec._b64encode(
        codec._canonical(
            {
                "v": 1,
                "licensee": "乍甸乳业",
                "issued_at": iso(T0),
                "expires_at": iso(T0 + timedelta(days=9999)),
                "level": "full",
            }
        )
    )
    state_dict = {"trial_start": T0, "license_code": f"{forged}.{signature}"}
    result = status_at(T0 + timedelta(days=70), state_dict)
    assert result.source == "trial"
    assert result.mode == state.MODE_READ_ONLY  # 2 个月已过，进入只读宽限


def test_missing_trial_start_treats_now_as_start():
    result = status_at(T0, {})
    assert result.mode == state.MODE_ACTIVE
    assert result.trial_start == iso(T0)


# ── 时钟回拨（BL-LICENSE-008） ────────────────────────────────


def test_clock_rollback_does_not_extend_license():
    deadline = state.add_months(T0, 2)
    rolled_back = T0 - timedelta(days=400)
    result = status_at(rolled_back, {"trial_start": T0, "max_seen_time": deadline + timedelta(days=20)})
    assert result.clock_rollback_detected is True
    assert result.mode == state.MODE_LOCKED
    assert result.effective_now == iso(deadline + timedelta(days=20))


def test_clock_rollback_keeps_remaining_days_unchanged():
    deadline = state.add_months(T0, 2)
    seen = deadline - timedelta(days=10)
    normal = status_at(seen, {"trial_start": T0, "max_seen_time": seen})
    rolled_back = status_at(seen - timedelta(days=365), {"trial_start": T0, "max_seen_time": seen})
    assert normal.days_remaining == rolled_back.days_remaining == 10


# ── 自然月推进 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "start,months,expected",
    [
        (datetime(2026, 1, 15, tzinfo=timezone.utc), 2, datetime(2026, 3, 15, tzinfo=timezone.utc)),
        (datetime(2026, 1, 31, tzinfo=timezone.utc), 1, datetime(2026, 2, 28, tzinfo=timezone.utc)),
        (datetime(2024, 2, 29, tzinfo=timezone.utc), 12, datetime(2025, 2, 28, tzinfo=timezone.utc)),
        (datetime(2026, 11, 30, tzinfo=timezone.utc), 2, datetime(2027, 1, 30, tzinfo=timezone.utc)),
        (datetime(2026, 12, 31, tzinfo=timezone.utc), 2, datetime(2027, 2, 28, tzinfo=timezone.utc)),
    ],
)
def test_add_months_calendar_semantics(start, months, expected):
    assert state.add_months(start, months) == expected


# ── 前向时钟跳变异常恢复（ALIGN-015/F4） ──────────────────────


def test_large_forward_jump_is_flagged_as_anomaly():
    result = status_at(T0 + timedelta(days=400), {"trial_start": T0, "max_seen_time": T0})
    assert result.clock_anomaly_detected is True
    assert result.clock_rollback_detected is False


def test_small_forward_step_is_not_anomaly():
    result = status_at(T0 + timedelta(days=3), {"trial_start": T0, "max_seen_time": T0})
    assert result.clock_anomaly_detected is False


def test_service_flags_forward_jump_and_recovers_via_unlock():
    """F4：前向跳变被标记并审计；异常时间必须被吸收，恢复只能走解锁码。

    若改为「只按上限推进」，已锁定的客户把时钟调回上限之后即可重新 active，
    等于绕过整个授权机制 —— 因此此处显式验证吸收行为。
    """
    from milk_license.service import LicenseService

    store = LicenseStore([MemoryBackend("mem")])
    clock = {"now": T0}
    service = LicenseService(store=store, public_key=PUBLIC, now_fn=lambda: clock["now"], cache_ttl=0)

    service.status(force=True)  # 首次运行登记起点
    assert store.read_merged()["max_seen_time"] == T0

    clock["now"] = T0 + timedelta(days=400)  # 时钟异常跳到 400 天后
    jumped = service.status(force=True)
    assert jumped.clock_anomaly_detected is True
    assert jumped.mode == state.MODE_LOCKED
    # 异常时间被吸收：否则回拨到上限之后即可绕过锁定
    assert store.read_merged()["max_seen_time"] == T0 + timedelta(days=400)

    clock["now"] = T0 + timedelta(days=5)  # 时钟校准回来：仍锁定（安全代价）
    still = service.status(force=True)
    assert still.mode == state.MODE_LOCKED
    assert still.clock_rollback_detected is True

    # 恢复路径：管理员输入有效解锁码 → 基准重置为当前（已校准）时间
    code = codec.issue_license(
        {
            "v": 1,
            "licensee": "乍甸乳业",
            "issued_at": iso(T0),
            "expires_at": iso(T0 + timedelta(days=365)),
            "level": "full",
        },
        SEED,
    )
    recovered = service.unlock(code)
    assert recovered.mode == state.MODE_ACTIVE
    assert store.read_merged()["max_seen_time"] == T0 + timedelta(days=5)


def test_service_still_blocks_rollback_after_normal_running():
    """正常运行时回拨仍被拦截：不得因为 F4 的修复而削弱防回拨。"""
    from milk_license.service import LicenseService

    store = LicenseStore([MemoryBackend("mem")])
    clock = {"now": T0}
    service = LicenseService(store=store, public_key=PUBLIC, now_fn=lambda: clock["now"], cache_ttl=0)
    service.status(force=True)

    clock["now"] = T0 + timedelta(days=40)  # 正常运行 40 天
    service.status(force=True)
    assert store.read_merged()["max_seen_time"] == T0 + timedelta(days=40)

    clock["now"] = T0 + timedelta(days=1)  # 回拨
    rolled = service.status(force=True)
    assert rolled.clock_rollback_detected is True
    assert rolled.effective_now == iso(T0 + timedelta(days=40))
