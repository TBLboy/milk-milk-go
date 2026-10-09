"""授权访问策略（BL-LICENSE-003/004/005）。

策略必须与实现一起编译（DEC-062）：修改策略文件即可绕过授权，
因此不允许把这份清单放在可读的 app 层。

分级：
  - ``active``     ：全部放行
  - ``read_only``  ：放行读方法 + 明确允许的只读 POST + 始终放行清单；其余返回 LICENSE_EXPIRED
  - ``locked``     ：只放行始终放行清单；其余返回 LICENSE_LOCKED

始终放行清单的依据：
  - BL-LICENSE-005：健康检查、管理员登录、授权状态查询、提交解锁码、备份与导出
  - BL-LICENSE-006：任何锁定状态下备份/恢复/导出必须保持可用
  - 会话自检（/auth/me、/auth/admin-check）不算业务数据，必须放行，
    否则前端无法渲染「已锁定」页面
"""

from __future__ import annotations

from fnmatch import fnmatchcase

API_PREFIX = "/api/v1"

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# 非 API 路径（SPA 壳、静态资源、接口文档）始终放行：锁定页本身也要能加载。
STATIC_ALWAYS_ALLOWED = True

# (method, path pattern)；path 支持 fnmatch 通配
ALWAYS_ALLOWED: tuple[tuple[str, str], ...] = (
    ("GET", f"{API_PREFIX}/health"),
    # 登录与会话自检：解锁码必须在 PC 端输入，因此管理员登录通道必须保留
    ("POST", f"{API_PREFIX}/auth/login"),
    ("POST", f"{API_PREFIX}/auth/admin/login"),
    ("POST", f"{API_PREFIX}/auth/admin/recover"),
    ("GET", f"{API_PREFIX}/auth/me"),
    ("GET", f"{API_PREFIX}/auth/admin-check"),
    # 授权本身
    ("GET", f"{API_PREFIX}/license/status"),
    ("POST", f"{API_PREFIX}/license/unlock"),
    # 备份 / 恢复 / 导出（BL-LICENSE-006：数据安全通道永不关闭）
    ("POST", f"{API_PREFIX}/operations/backups"),
    ("GET", f"{API_PREFIX}/operations/backups"),
    ("GET", f"{API_PREFIX}/operations/restore/candidates"),
    ("POST", f"{API_PREFIX}/operations/restore"),
    ("POST", f"{API_PREFIX}/operations/select-directory"),
    # 审计日志：受限期间仍可查证授权事件与历史操作
    ("GET", f"{API_PREFIX}/operations/audit-logs"),
)

# 只读宽限期额外允许的「只读型 POST」（校验、导出、预览）
READ_ONLY_EXTRA: tuple[tuple[str, str], ...] = (
    ("POST", f"{API_PREFIX}/labels/export-pdf"),
    ("POST", f"{API_PREFIX}/labels/excel-validate"),
    ("POST", f"{API_PREFIX}/master-data/products/import-validate"),
    ("POST", f"{API_PREFIX}/evidence/work-orders/*/steps/*/qr/validate"),
    ("POST", f"{API_PREFIX}/evidence/work-orders/*/steps/*/weight/validate"),
)

MODE_ACTIVE = "active"
MODE_READ_ONLY = "read_only"
MODE_LOCKED = "locked"

ERROR_EXPIRED = "LICENSE_EXPIRED"
ERROR_LOCKED = "LICENSE_LOCKED"
ERROR_STATE_UNAVAILABLE = "LICENSE_STATE_UNAVAILABLE"

ERROR_MESSAGES = {
    ERROR_EXPIRED: "软件授权已到期，当前为只读状态，请联系供应商续期",
    ERROR_LOCKED: "软件授权已到期并被锁定，请输入解锁码后继续使用",
    ERROR_STATE_UNAVAILABLE: "授权状态不可用，请联系供应商处理",
}


def _matches(rules: tuple[tuple[str, str], ...], path: str, method: str) -> bool:
    for rule_method, pattern in rules:
        if rule_method != method:
            continue
        if fnmatchcase(path, pattern):
            return True
    return False


def is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def check(path: str, method: str, mode: str) -> str | None:
    """返回 None 表示放行；否则返回错误码。"""
    if mode == MODE_ACTIVE:
        return None
    if not is_api_path(path):
        return None if STATIC_ALWAYS_ALLOWED else ERROR_LOCKED

    method = method.upper()
    if method == "OPTIONS":
        # CORS 预检不携带业务语义；锁定态也必须放行，否则跨域客户端无法提交解锁码（ALIGN-015/F6）
        return None
    if _matches(ALWAYS_ALLOWED, path, method):
        return None

    if mode == MODE_READ_ONLY:
        if method in READ_METHODS:
            return None
        if _matches(READ_ONLY_EXTRA, path, method):
            return None
        return ERROR_EXPIRED

    return ERROR_LOCKED
