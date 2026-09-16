import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.models import EvidenceFile, SystemSetting, User
from app.db.session import get_db
from app.services.audit import write_audit


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    employee_no: str | None = Field(default=None, max_length=64)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    avatar_file_id: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    employee_no: str = Field(min_length=1, max_length=64)


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserActiveRequest(BaseModel):
    is_active: bool


class SelfProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    avatar_file_id: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)


class AdminUserProfileUpdateRequest(SelfProfileUpdateRequest):
    employee_no: str | None = Field(default=None, max_length=64)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminRecoveryRequest(BaseModel):
    recovery_password: str = Field(min_length=1, max_length=256)


RECOVERY_ATTEMPTS_KEY = "admin_recovery_failed_attempts"
RECOVERY_LOCKED_UNTIL_KEY = "admin_recovery_locked_until"


def _normalize_employee_no(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else ""
    return normalized or None


def _public_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "is_active": user.is_active,
        "avatar_file_id": user.avatar_file_id,
        "phone": user.phone or "",
        "employee_no": user.employee_no or "",
        "must_change_password": user.must_change_password,
    }


def _validate_employee_no_available(db: Session, employee_no: str | None, *, exclude_user_id: int | None = None) -> None:
    normalized = _normalize_employee_no(employee_no)
    if normalized is None:
        return
    query = select(User.id).where(User.employee_no == normalized)
    if exclude_user_id is not None:
        query = query.where(User.id != exclude_user_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail={"code": "EMPLOYEE_NO_EXISTS", "message": "工号已存在"})


def _generate_reset_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


def _setting_value(db: Session, key: str) -> str | None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return setting.value if setting is not None else None


def _set_setting_value(db: Session, key: str, value: str) -> None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        setting.value = value


def _clear_setting_value(db: Session, key: str) -> None:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if setting is not None:
        db.delete(setting)


def _parse_utc_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_avatar_file(db: Session, avatar_file_id: str | None) -> None:
    if avatar_file_id is None:
        return
    if db.scalar(select(EvidenceFile).where(EvidenceFile.file_id == avatar_file_id)) is None:
        raise HTTPException(status_code=422, detail={"code": "AVATAR_FILE_NOT_FOUND", "message": "头像文件不存在"})


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "AUTH_REQUIRED", "message": "请先登录"})
    try:
        payload = decode_token(authorization[7:])
        user = db.scalar(select(User).where(User.id == int(payload["sub"]), User.is_active.is_(True)))
        if user is not None and int(payload.get("auth_version", 1)) != user.auth_version:
            user = None
    except (ValueError, TypeError):
        user = None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_TOKEN", "message": "登录已失效，请重新登录"})
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "ADMIN_REQUIRED", "message": "需要管理员权限"})
    return user


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    return _login(body, db, portal="app")


@router.post("/admin/login")
def admin_login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    return _login(body, db, portal="pc")


@router.post("/admin/recover")
def recover_admin_password(body: AdminRecoveryRequest, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.admin_recovery_secret_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ADMIN_RECOVERY_DISABLED", "message": "管理员紧急恢复功能尚未配置"},
        )

    now = datetime.now(timezone.utc)
    locked_until = _parse_utc_datetime(_setting_value(db, RECOVERY_LOCKED_UNTIL_KEY))
    if locked_until is not None:
        if locked_until > now:
            retry_after = max(1, int((locked_until - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "ADMIN_RECOVERY_LOCKED",
                    "message": f"恢复密码错误次数过多，请在 {max(1, (retry_after + 59) // 60)} 分钟后重试",
                    "retry_after_seconds": retry_after,
                },
            )
        _clear_setting_value(db, RECOVERY_LOCKED_UNTIL_KEY)
        _set_setting_value(db, RECOVERY_ATTEMPTS_KEY, "0")

    try:
        attempts = int(_setting_value(db, RECOVERY_ATTEMPTS_KEY) or "0")
    except ValueError:
        attempts = 0

    if not verify_password(body.recovery_password, settings.admin_recovery_secret_hash):
        attempts += 1
        if attempts >= settings.admin_recovery_max_attempts:
            next_lock = now + timedelta(minutes=settings.admin_recovery_lockout_minutes)
            _set_setting_value(db, RECOVERY_ATTEMPTS_KEY, "0")
            _set_setting_value(db, RECOVERY_LOCKED_UNTIL_KEY, next_lock.isoformat())
            write_audit(
                db,
                action="admin_password.recovery_locked",
                resource_type="user",
                resource_id="admin",
                result="failure",
                detail={"failed_attempts": attempts},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "ADMIN_RECOVERY_LOCKED",
                    "message": f"恢复密码错误次数过多，请在 {settings.admin_recovery_lockout_minutes} 分钟后重试",
                    "retry_after_seconds": settings.admin_recovery_lockout_minutes * 60,
                },
            )

        _set_setting_value(db, RECOVERY_ATTEMPTS_KEY, str(attempts))
        write_audit(
            db,
            action="admin_password.recovery_failed",
            resource_type="user",
            resource_id="admin",
            result="failure",
            detail={"failed_attempts": attempts},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_RECOVERY_PASSWORD",
                "message": "恢复密码不正确",
                "remaining_attempts": max(0, settings.admin_recovery_max_attempts - attempts),
            },
        )

    admin = db.scalar(select(User).where(User.role == "admin").order_by(User.id))
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ADMIN_ACCOUNT_NOT_FOUND", "message": "管理员账号不存在，请联系维护人员"},
        )

    temporary_password = _generate_reset_password()
    admin.password_hash = hash_password(temporary_password)
    admin.must_change_password = True
    admin.auth_version = (admin.auth_version or 1) + 1
    _set_setting_value(db, RECOVERY_ATTEMPTS_KEY, "0")
    _clear_setting_value(db, RECOVERY_LOCKED_UNTIL_KEY)
    write_audit(
        db,
        action="admin_password.recovered",
        resource_type="user",
        resource_id=admin.id,
        detail={"username": admin.username},
    )
    db.commit()
    return {
        "status": "ok",
        "username": admin.username,
        "temporary_password": temporary_password,
        "must_change_password": True,
        "message": "管理员密码已重置，请立即复制临时密码并在登录后修改",
    }


def _authenticate_user(body: LoginRequest, db: Session) -> User:
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "账号或密码错误"})
    if user.status == "pending":
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_PENDING_APPROVAL", "message": "账号注册申请尚未审批通过"})
    if user.status == "rejected":
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_REJECTED", "message": "账号注册申请已被驳回，请联系管理员"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_DISABLED", "message": "账号已停用，请联系管理员"})
    return user


def _login(body: LoginRequest, db: Session, *, portal: str) -> dict:
    try:
        user = _authenticate_user(body, db)
        if portal == "pc" and user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ADMIN_PORTAL_REQUIRED", "message": "普通操作员账号不能登录电脑管理端"},
            )
    except HTTPException as exc:
        candidate = db.scalar(select(User).where(User.username == body.username))
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        write_audit(
            db,
            actor_id=candidate.id if candidate else None,
            action="auth.admin_login" if portal == "pc" else "auth.login",
            resource_type="session",
            result="failure",
            detail={
                "username": body.username,
                "portal": portal,
                "code": detail.get("code", "LOGIN_FAILED"),
            },
        )
        db.commit()
        raise

    write_audit(
        db,
        actor_id=user.id,
        action="auth.admin_login" if portal == "pc" else "auth.login",
        resource_type="session",
        resource_id=user.id,
        detail={"username": user.username, "portal": portal},
    )
    db.commit()
    return _login_response(user)


def _login_response(user: User) -> dict:
    return {
        "access_token": create_token(user.id, user.role, user.auth_version),
        "token_type": "bearer",
        "user": _public_user(user),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "USERNAME_EXISTS", "message": "账号已存在"})
    employee_no = _normalize_employee_no(body.employee_no)
    _validate_employee_no_available(db, employee_no)
    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role="operator",
        status="pending",
        is_active=False,
        employee_no=employee_no,
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        actor_id=None,
        action="account.registered",
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username, "display_name": user.display_name, "employee_no": user.employee_no},
    )
    db.commit()
    db.refresh(user)
    return {
        "submitted": True,
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "employee_no": user.employee_no or "",
        "status": "pending",
        "message": "注册申请已提交，等待管理员审批",
    }


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": _public_user(user)}


@router.patch("/me", status_code=status.HTTP_200_OK)
def update_my_profile(body: SelfProfileUpdateRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    changed_fields = []
    if body.display_name is not None:
        user.display_name = body.display_name
        changed_fields.append("display_name")
    if body.avatar_file_id is not None:
        _validate_avatar_file(db, body.avatar_file_id)
        user.avatar_file_id = body.avatar_file_id
        changed_fields.append("avatar_file_id")
    if body.phone is not None:
        user.phone = body.phone
        changed_fields.append("phone")
    write_audit(
        db,
        actor_id=user.id,
        action="account.profile_updated",
        resource_type="user",
        resource_id=user.id,
        detail={"changed_fields": changed_fields},
    )
    db.commit()
    return {"user": _public_user(user)}


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
def change_my_password(body: ChangePasswordRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        write_audit(
            db,
            actor_id=user.id,
            action="account.password_changed",
            resource_type="user",
            resource_id=user.id,
            result="failure",
            detail={"reason": "INVALID_CURRENT_PASSWORD"},
        )
        db.commit()
        raise HTTPException(status_code=422, detail={"code": "INVALID_CURRENT_PASSWORD", "message": "当前密码不正确"})
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    write_audit(
        db,
        actor_id=user.id,
        action="account.password_changed",
        resource_type="user",
        resource_id=user.id,
    )
    db.commit()
    return {"status": "ok", "message": "密码修改成功"}


@router.get("/admin-check")
def admin_check(_user: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok"}


@router.get("/users")
def list_users(_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [_public_user(user) for user in users]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(body: CreateUserRequest, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "USERNAME_EXISTS", "message": "账号已存在"})
    employee_no = _normalize_employee_no(body.employee_no)
    if employee_no is None:
        raise HTTPException(status_code=422, detail={"code": "EMPLOYEE_NO_REQUIRED", "message": "普通操作员工号不能为空"})
    _validate_employee_no_available(db, employee_no)
    _validate_avatar_file(db, body.avatar_file_id)
    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role="operator",
        status="active",
        is_active=True,
        avatar_file_id=body.avatar_file_id,
        phone=body.phone,
        employee_no=employee_no,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    write_audit(
        db,
        actor_id=_user.id,
        action="account.created",
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username, "employee_no": user.employee_no},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "EMPLOYEE_NO_EXISTS", "message": "工号已存在"}) from exc
    db.refresh(user)
    return {"user": _public_user(user)}


@router.get("/users/{user_id}")
def get_user(user_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    return {"user": _public_user(user)}


@router.patch("/users/{user_id}/profile", status_code=status.HTTP_200_OK)
def update_user_profile(user_id: int, body: AdminUserProfileUpdateRequest, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    changed_fields = []
    if body.display_name is not None:
        user.display_name = body.display_name
        changed_fields.append("display_name")
    if body.avatar_file_id is not None:
        _validate_avatar_file(db, body.avatar_file_id)
        user.avatar_file_id = body.avatar_file_id
        changed_fields.append("avatar_file_id")
    if body.phone is not None:
        user.phone = body.phone
        changed_fields.append("phone")
    if body.employee_no is not None:
        employee_no = _normalize_employee_no(body.employee_no)
        if user.role == "operator" and employee_no is None:
            raise HTTPException(status_code=422, detail={"code": "EMPLOYEE_NO_REQUIRED", "message": "普通操作员工号不能为空"})
        _validate_employee_no_available(db, employee_no, exclude_user_id=user.id)
        user.employee_no = employee_no
        changed_fields.append("employee_no")
    write_audit(
        db,
        actor_id=_user.id,
        action="account.admin_profile_updated",
        resource_type="user",
        resource_id=user.id,
        detail={"target_username": user.username, "changed_fields": changed_fields},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "EMPLOYEE_NO_EXISTS", "message": "工号已存在"}) from exc
    return {"user": _public_user(user)}


@router.post("/users/{user_id}/approve", status_code=status.HTTP_200_OK)
def approve_user(user_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if user.role == "admin":
        raise HTTPException(status_code=422, detail={"code": "ADMIN_APPROVAL_BLOCKED", "message": "管理员账号不需要审批"})
    if user.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "USER_STATUS_CONFLICT", "message": "该账号当前不在待审批状态"})
    if not user.employee_no:
        raise HTTPException(status_code=422, detail={"code": "EMPLOYEE_NO_REQUIRED", "message": "请先为普通操作员设置唯一工号"})
    _validate_employee_no_available(db, user.employee_no, exclude_user_id=user.id)
    user.status = "active"
    user.is_active = True
    write_audit(
        db,
        actor_id=_user.id,
        action="account.approved",
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username, "employee_no": user.employee_no},
    )
    db.commit()
    return {"user": _public_user(user)}


@router.post("/users/{user_id}/reject", status_code=status.HTTP_200_OK)
def reject_user(user_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if user.role == "admin":
        raise HTTPException(status_code=422, detail={"code": "ADMIN_REJECTION_BLOCKED", "message": "管理员账号不能驳回"})
    if user.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "USER_STATUS_CONFLICT", "message": "该账号当前不在待审批状态"})
    user.status = "rejected"
    user.is_active = False
    write_audit(
        db,
        actor_id=_user.id,
        action="account.rejected",
        resource_type="user",
        resource_id=user.id,
        result="rejected",
        detail={"username": user.username},
    )
    db.commit()
    return {"user": _public_user(user)}


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if user.role == "admin":
        raise HTTPException(status_code=422, detail={"code": "ADMIN_PASSWORD_BLOCKED", "message": "管理员密码不能通过此接口重置"})
    temporary_password = _generate_reset_password()
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.auth_version = (user.auth_version or 1) + 1
    write_audit(
        db,
        actor_id=_user.id,
        action="account.password_reset",
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username},
    )
    db.commit()
    return {
        "username": user.username,
        "display_name": user.display_name,
        "temporary_password": temporary_password,
        "must_change_password": True,
        "message": "密码已重置为一次随机初始密码",
    }


@router.patch("/users/{user_id}/active")
def set_user_active(user_id: int, body: UserActiveRequest, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if user.role == "admin":
        raise HTTPException(status_code=422, detail={"code": "ADMIN_STATUS_BLOCKED", "message": "管理员账号不能停用"})
    user.is_active = body.is_active
    write_audit(
        db,
        actor_id=_user.id,
        action="account.activation_changed",
        resource_type="user",
        resource_id=user.id,
        detail={"username": user.username, "is_active": body.is_active},
    )
    db.commit()
    return {"user": _public_user(user)}
