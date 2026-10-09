"""授权守卫、策略与解锁接口的集成测试（TASK-155/156）。

测试用固定密钥对覆盖内置公钥（MILK_LICENSE_PUBLIC_KEY），
从而不需要真实签发私钥即可端到端验证「签发 → 解锁 → 恢复」。
"""

import json
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from milk_license import codec, policy, state

# RFC 8032 TEST 3 密钥对（仅用于测试）
TEST_SEED = bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7")
TEST_PUBLIC_HEX = "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025"

LICENSE_CODES = {policy.ERROR_EXPIRED, policy.ERROR_LOCKED}


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def issue(expires_days: int = 365, licensee: str = "乍甸乳业") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "v": 1,
        "licensee": licensee,
        "issued_at": iso(now),
        "expires_at": iso(now + timedelta(days=expires_days)),
        "level": "full",
    }
    return codec.issue_license(payload, TEST_SEED)


@pytest.fixture
def license_env(tmp_path, monkeypatch):
    """启动应用，并把授权状态目录、公钥与注册表隔离到测试环境。"""
    monkeypatch.setenv("MILK_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MILK_LICENSE_STATE_DIR", str(tmp_path / "license-state"))
    monkeypatch.setenv("MILK_LICENSE_DISABLE_REGISTRY", "1")
    for name in list(sys.modules):
        # 只重载 app.*：删除 milk_license 会破坏已编译模块的类标识，
        # 使 pytest.raises(codec.LicenseError) 等断言在其他测试文件中失效。
        if name == "app" or name.startswith("app."):
            del sys.modules[name]
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.db.session import engine

    engine.dispose()
    # 公钥不允许被环境变量覆盖（ALIGN-015/F3）：测试改为覆盖模块常量
    import milk_license.keys as license_keys

    monkeypatch.setattr(license_keys, "DEFAULT_PUBLIC_KEY_HEX", TEST_PUBLIC_HEX)
    from app.main import app

    with TestClient(app) as client:
        yield client, tmp_path / "license-state"
    get_settings.cache_clear()


def seed_state(state_dir, **fields) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "license-state.json").write_text(json.dumps(fields), encoding="utf-8")


def admin_headers(client) -> dict:
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def blocked(response) -> bool:
    """该响应是否由授权守卫拦截。"""
    if response.status_code != 403:
        return False
    detail = response.json().get("detail")
    return isinstance(detail, dict) and detail.get("code") in LICENSE_CODES


def trial_start_for(offset_days: int) -> datetime:
    """构造一个让「现在」正好落在期望窗口内的试用起点。

    ``offset_days`` 为正表示把起点往前推（更接近/超过到期）。
    """
    now = datetime.now(timezone.utc)
    return state.add_months(now, -state.TRIAL_MONTHS) - timedelta(days=offset_days)


# ── 策略单元测试 ──────────────────────────────────────────────


def test_active_mode_allows_everything():
    for path, method in [
        ("/api/v1/work-orders", "POST"),
        ("/api/v1/work-orders", "GET"),
        ("/api/v1/settings", "PUT"),
    ]:
        assert policy.check(path, method, policy.MODE_ACTIVE) is None


def test_read_only_blocks_writes_and_allows_reads():
    assert policy.check("/api/v1/work-orders", "POST", policy.MODE_READ_ONLY) == policy.ERROR_EXPIRED
    assert policy.check("/api/v1/work-orders", "GET", policy.MODE_READ_ONLY) is None
    assert policy.check("/api/v1/auth/users", "POST", policy.MODE_READ_ONLY) == policy.ERROR_EXPIRED
    assert policy.check("/api/v1/settings", "PUT", policy.MODE_READ_ONLY) == policy.ERROR_EXPIRED


def test_read_only_allows_designated_read_only_posts():
    for path in [
        "/api/v1/labels/export-pdf",
        "/api/v1/labels/excel-validate",
        "/api/v1/master-data/products/import-validate",
        "/api/v1/evidence/work-orders/WO-1/steps/1/qr/validate",
        "/api/v1/evidence/work-orders/WO-1/steps/1/weight/validate",
    ]:
        assert policy.check(path, "POST", policy.MODE_READ_ONLY) is None, path


def test_locked_blocks_business_but_keeps_recovery_channels():
    assert policy.check("/api/v1/work-orders", "GET", policy.MODE_LOCKED) == policy.ERROR_LOCKED
    assert policy.check("/api/v1/work-orders", "POST", policy.MODE_LOCKED) == policy.ERROR_LOCKED
    for path, method in [
        ("/api/v1/health", "GET"),
        ("/api/v1/auth/login", "POST"),
        ("/api/v1/auth/admin/login", "POST"),
        ("/api/v1/auth/me", "GET"),
        ("/api/v1/license/status", "GET"),
        ("/api/v1/license/unlock", "POST"),
        ("/api/v1/operations/backups", "POST"),
        ("/api/v1/operations/backups", "GET"),
        ("/api/v1/operations/restore/candidates", "GET"),
        ("/api/v1/operations/restore", "POST"),
        ("/api/v1/operations/audit-logs", "GET"),
    ]:
        assert policy.check(path, method, policy.MODE_LOCKED) is None, (path, method)


def test_static_and_spa_paths_are_never_blocked():
    for path in ["/", "/index.html", "/assets/app.js", "/work-orders"]:
        assert policy.check(path, "GET", policy.MODE_LOCKED) is None


# ── 集成：试用与倒计时 ────────────────────────────────────────


def test_fresh_install_starts_two_month_trial(license_env):
    client, _ = license_env
    body = client.get("/api/v1/license/status", headers=admin_headers(client)).json()
    assert body["mode"] == "active"
    assert body["source"] == "trial"
    assert body["trial_months"] == 2
    assert 58 <= body["days_remaining"] <= 63


def test_state_is_persisted_to_three_copies(license_env):
    client, state_dir = license_env
    client.get("/api/v1/license/status", headers=admin_headers(client))
    assert (state_dir / "license-state.json").is_file()

    from app.db.models import SystemSetting
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == "license_state"))
        assert row is not None and "trial_start" in row.value
    finally:
        db.close()


def test_countdown_warns_inside_thirty_days(license_env):
    client, state_dir = license_env
    seed_state(state_dir, trial_start=iso(trial_start_for(-29)))
    body = client.get("/api/v1/license/status", headers=admin_headers(client)).json()
    assert body["mode"] == "active"
    assert body["warn"] is True
    assert body["days_remaining"] in (28, 29)


# ── 集成：只读宽限期 ──────────────────────────────────────────


def test_read_only_grace_blocks_writes_but_allows_reads(license_env):
    client, state_dir = license_env
    seed_state(state_dir, trial_start=iso(trial_start_for(1)))
    headers = admin_headers(client)

    status_body = client.get("/api/v1/license/status", headers=headers).json()
    assert status_body["mode"] == "read_only"
    assert status_body["grace_days_remaining"] >= 1

    blocked_response = client.post("/api/v1/work-orders", headers=headers, json={})
    assert blocked_response.json()["detail"]["code"] == policy.ERROR_EXPIRED

    assert client.get("/api/v1/work-orders", headers=headers).status_code == 200
    assert client.get("/api/v1/operations/backups", headers=headers).status_code == 200
    assert not blocked(client.post("/api/v1/labels/export-pdf", headers=headers, json={"items": []}))
    assert blocked(client.post("/api/v1/auth/users", headers=headers, json={}))
    assert blocked(client.put("/api/v1/settings", headers=headers, json={"values": {"x": "y"}}))


# ── 集成：完全锁定 ────────────────────────────────────────────


def test_locked_blocks_reads_and_writes_but_keeps_recovery(license_env):
    client, state_dir = license_env
    seed_state(state_dir, trial_start=iso(trial_start_for(20)))
    headers = admin_headers(client)

    assert client.get("/api/v1/license/status", headers=headers).json()["mode"] == "locked"
    assert client.get("/api/v1/work-orders", headers=headers).json()["detail"]["code"] == policy.ERROR_LOCKED
    assert client.get("/api/v1/operations/audit-logs", headers=headers).status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/").status_code == 200


def test_unlock_channel_is_reachable_while_locked(license_env):
    client, state_dir = license_env
    seed_state(state_dir, trial_start=iso(trial_start_for(20)))
    headers = admin_headers(client)  # 登录通道必须保持可用

    response = client.post("/api/v1/license/unlock", headers=headers, json={"code": "not-a-license"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "LICENSE_CODE_INVALID"


# ── 集成：解锁 ────────────────────────────────────────────────


def test_unlock_restores_full_access_and_is_audited(license_env):
    client, state_dir = license_env
    seed_state(state_dir, trial_start=iso(trial_start_for(20)))
    headers = admin_headers(client)
    assert client.get("/api/v1/license/status", headers=headers).json()["mode"] == "locked"

    response = client.post("/api/v1/license/unlock", headers=headers, json={"code": issue(expires_days=365)})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "active"
    assert body["source"] == "license"
    assert body["licensee"] == "乍甸乳业"

    # 恢复后写操作不再被授权守卫拦截
    assert not blocked(client.post("/api/v1/work-orders", headers=headers, json={}))

    logs = client.get("/api/v1/operations/audit-logs", headers=headers, params={"action": "license.unlock"})
    assert logs.status_code == 200
    actions = [item["action"] for item in logs.json()["items"]]
    assert "license.unlock" in actions


def test_unlock_with_invalid_code_keeps_locked_state(license_env):
    client, state_dir = license_env
    seed_state(state_dir, trial_start=iso(trial_start_for(20)))
    headers = admin_headers(client)

    body = issue(expires_days=365)
    body_b64, signature_b64 = body.split(".")
    broken = bytearray(codec._b64decode(signature_b64))
    broken[0] ^= 0x01
    tampered = f"{body_b64}.{codec._b64encode(bytes(broken))}"

    response = client.post("/api/v1/license/unlock", headers=headers, json={"code": tampered})
    assert response.status_code == 422
    assert client.get("/api/v1/license/status", headers=headers).json()["mode"] == "locked"

    logs = client.get("/api/v1/operations/audit-logs", headers=headers, params={"action": "license.unlock"})
    results = [item["result"] for item in logs.json()["items"] if item["action"] == "license.unlock"]
    assert "rejected" in results


# ── 集成：时钟回拨 ────────────────────────────────────────────


def test_clock_rollback_does_not_extend_trial(license_env):
    client, state_dir = license_env
    future = datetime.now(timezone.utc) + timedelta(days=400)
    seed_state(
        state_dir,
        trial_start=iso(trial_start_for(-10)),  # 正常应是试用中
        max_seen_time=iso(future),  # 但系统曾见过 400 天后的时间
    )
    body = client.get("/api/v1/license/status", headers=admin_headers(client)).json()
    assert body["clock_rollback_detected"] is True
    assert body["mode"] == "locked"


def test_clock_rollback_is_audited(license_env):
    """BL-LICENSE-012：时钟回拨必须可在审计日志中查到。"""
    client, state_dir = license_env
    future = datetime.now(timezone.utc) + timedelta(days=400)
    seed_state(state_dir, trial_start=iso(trial_start_for(-10)), max_seen_time=iso(future))
    headers = admin_headers(client)
    assert client.get("/api/v1/license/status", headers=headers).json()["clock_rollback_detected"] is True

    logs = client.get("/api/v1/operations/audit-logs", headers=headers, params={"action": "license.clock_rollback"})
    assert logs.status_code == 200
    assert "license.clock_rollback" in [item["action"] for item in logs.json()["items"]]


def test_public_key_cannot_be_overridden_by_environment(monkeypatch):
    """ALIGN-015/F3：交付物中的公钥不得被环境变量替换。"""
    from milk_license import keys

    monkeypatch.setenv("MILK_LICENSE_PUBLIC_KEY", "00" * 32)
    assert keys.public_key().hex() == keys.DEFAULT_PUBLIC_KEY_HEX


def test_state_dir_ignores_environment(monkeypatch):
    """ALIGN-015/F3：编译模块不得按环境变量重定向状态目录。"""
    from milk_license.store import default_state_dir

    monkeypatch.setenv("MILK_LICENSE_STATE_DIR", r"C:\definitely-not-this")
    assert "definitely-not-this" not in str(default_state_dir())
