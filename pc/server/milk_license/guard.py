"""ASGI 守卫中间件（BL-LICENSE-003/005）。

在路由之前统一拦截，避免逐端点遗漏（含 SPA catch-all 路由）。

失败策略（B 级决策，记录在 DEC-066）：
  授权状态判定本身异常时 **fail-closed**，返回 503 LICENSE_STATE_UNAVAILABLE。
  理由：授权子系统损坏属于必须被发现的运行事故；若 fail-open，
  则「把状态文件搞坏」就成了绕过手段。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from milk_license import policy
from milk_license.service import LicenseService

logger = logging.getLogger("milk_license.guard")

AuditHook = Callable[[str, dict[str, Any]], None]

_CORS_HEADERS = [(b"access-control-allow-origin", b"*")]


async def _send_json(send, status_code: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode("ascii")),
        *_CORS_HEADERS,
    ]
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class LicenseGuard:
    """按授权状态拦截请求。"""

    def __init__(self, app, service: LicenseService, audit: AuditHook | None = None) -> None:
        self.app = app
        self.service = service
        self.audit = audit

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        try:
            mode = self.service.mode()
            transition = self.service.mode_transition()
        except Exception:  # noqa: BLE001 - 任何判定异常都必须 fail-closed
            logger.exception("授权状态判定失败，按不可用处理")
            await _send_json(
                send,
                503,
                {
                    "detail": {
                        "code": policy.ERROR_STATE_UNAVAILABLE,
                        "message": policy.ERROR_MESSAGES[policy.ERROR_STATE_UNAVAILABLE],
                    }
                },
            )
            return

        if transition is not None and self.audit is not None:
            try:
                self.audit("license.mode_changed", {"mode": transition, "path": path})
            except Exception:  # noqa: BLE001 - 审计失败不得影响请求处理
                logger.exception("授权状态变化审计写入失败")

        try:
            if self.audit is not None:
                status = self.service.status()
                if self.service.rollback_transition():
                    self.audit(
                        "license.clock_rollback",
                        {"mode": mode, "effective_now": status.effective_now, "path": path},
                    )
                if self.service.anomaly_transition():
                    self.audit(
                        "license.clock_anomaly",
                        {"mode": mode, "effective_now": status.effective_now, "path": path},
                    )
        except Exception:  # noqa: BLE001
            logger.exception("时钟异常审计写入失败")

        error = policy.check(path, method, mode)
        if error is None:
            await self.app(scope, receive, send)
            return

        await _send_json(
            send,
            403,
            {
                "detail": {
                    "code": error,
                    "message": policy.ERROR_MESSAGES[error],
                    "mode": mode,
                }
            },
        )


def install(app, service: LicenseService | None = None, audit: AuditHook | None = None) -> LicenseService:
    """把守卫挂到 FastAPI 应用上，并返回所使用的服务实例。"""
    resolved = service if service is not None else LicenseService()
    app.add_middleware(LicenseGuard, service=resolved, audit=audit)
    return resolved


def build_app():  # pragma: no cover - 交付入口，见 TASK-159
    """交付入口：返回已挂载守卫的应用。

    安装器与 Windows 服务应引用 ``milk_license.guard:build_app``，
    这样「不挂守卫」就不是一次调用层面的改动，而需要重写服务入口。
    """
    from app.main import app

    install(app)
    return app
