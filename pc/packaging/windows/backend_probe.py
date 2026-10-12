"""安装后自检：确认后端真的可用（API 有响应且首页可打开）。

由安装器在启动服务之后调用。退出码 0 = 正常，非 0 = 失败。

要点（都是踩过的坑）：
1. 只使用标准库，避免探针自身的依赖问题掩盖真实故障。
2. 健康检查路径是 ``/api/v1/health``（所有路由器都挂在 settings.api_prefix 下）。
   ``/health`` 不是路由，会落到 SPA catch-all 返回 index.html —— 只判断
   "有响应" 会假通过，所以必须校验 JSON 内容。
3. 显式绕过代理：工厂/办公网络常配系统代理，若代理未排除 loopback，
   127.0.0.1 的请求会被劫持而超时，产生假失败。
4. 历史上安装器只自检 SMTP、不验证后端，导致"缺依赖起不来"的交付包
   装完毫无提示，客户只看到打不开（见 DEC-070）。
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8011"
HEALTH_URL = BASE_URL + "/api/v1/health"
INDEX_URL = BASE_URL + "/"
TIMEOUT_SECONDS = 60.0
INTERVAL_SECONDS = 2.0

# 不走任何代理（ProxyHandler({}) 会覆盖环境变量与系统代理设置）
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(url: str) -> tuple[int, bytes]:
    with _OPENER.open(url, timeout=5) as response:
        return response.status, response.read()


def check_api() -> str:
    """返回空字符串表示通过，否则返回失败原因。"""
    status, body = _get(HEALTH_URL)
    if status != 200:
        return f"{HEALTH_URL} -> HTTP {status}"
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return f"{HEALTH_URL} -> 响应不是 JSON（{type(exc).__name__}）"
    if payload.get("status") != "ok":
        return f"{HEALTH_URL} -> status={payload.get('status')!r}"
    return ""


def check_index() -> str:
    """返回空字符串表示通过，否则返回失败原因。"""
    status, body = _get(INDEX_URL)
    if status != 200:
        return f"{INDEX_URL} -> HTTP {status}"
    if b"<div id=\"root\">" not in body and b"<!doctype html>" not in body.lower():
        return f"{INDEX_URL} -> 返回内容不像管理界面"
    return ""


def probe() -> tuple[bool, str]:
    """轮询直到 API 与首页都就绪，返回 (是否成功, 细节)。"""
    deadline = time.monotonic() + TIMEOUT_SECONDS
    last_error = "未发起请求"
    while time.monotonic() < deadline:
        try:
            error = check_api()
            if not error:
                error = check_index()
            if not error:
                return True, f"API 与首页均正常（{HEALTH_URL}）"
            last_error = error
        except Exception as exc:  # noqa: BLE001 - 任何异常都只表示"还没起来"
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(INTERVAL_SECONDS)
    return False, last_error


if __name__ == "__main__":
    ok, detail = probe()
    print(("OK   " if ok else "FAIL ") + detail)
    sys.exit(0 if ok else 1)
