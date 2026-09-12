import secrets
import string

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.models import EvidenceFile, User
from app.db.session import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    avatar_file_id: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    id_card: str | None = Field(default=None, max_length=64)


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserActiveRequest(BaseModel):
    is_active: bool


class UserProfileUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    avatar_file_id: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    id_card: str | None = Field(default=None, max_length=64)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def _mask_id_card(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 7:
        return "********"
    return value[:3] + "********" + value[-4:]


def _public_user(user: User, include_sensitive: bool = False) -> dict:
    id_card = user.id_card or ""
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "status": user.status,
        "is_active": user.is_active,
        "avatar_file_id": user.avatar_file_id,
        "phone": user.phone or "",
        "id_card": id_card if include_sensitive else _mask_id_card(id_card),
        "must_change_password": user.must_change_password,
    }


def _generate_reset_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))


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
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "账号或密码错误"})
    if user.status == "pending":
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_PENDING_APPROVAL", "message": "账号注册申请尚未审批通过"})
    if user.status == "rejected":
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_REJECTED", "message": "账号注册申请已被驳回，请联系管理员"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_DISABLED", "message": "账号已停用，请联系管理员"})
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer", "user": _public_user(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "USERNAME_EXISTS", "message": "账号已存在"})
    user = User(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role="operator",
        status="pending",
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "submitted": True,
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "status": "pending",
        "message": "注册申请已提交，等待管理员审批",
    }


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": _public_user(user, include_sensitive=True)}


@router.patch("/me", status_code=status.HTTP_200_OK)
def update_my_profile(body: UserProfileUpdateRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.avatar_file_id is not None:
        _validate_avatar_file(db, body.avatar_file_id)
        user.avatar_file_id = body.avatar_file_id
    if body.phone is not None:
        user.phone = body.phone
    db.commit()
    return {"user": _public_user(user, include_sensitive=True)}


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
def change_my_password(body: ChangePasswordRequest, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=422, detail={"code": "INVALID_CURRENT_PASSWORD", "message": "当前密码不正确"})
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
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
        id_card=body.id_card,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user": _public_user(user)}


@router.get("/users/{user_id}")
def get_user(user_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    return {"user": _public_user(user, include_sensitive=True)}


@router.patch("/users/{user_id}/profile", status_code=status.HTTP_200_OK)
def update_user_profile(user_id: int, body: UserProfileUpdateRequest, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.avatar_file_id is not None:
        _validate_avatar_file(db, body.avatar_file_id)
        user.avatar_file_id = body.avatar_file_id
    if body.phone is not None:
        user.phone = body.phone
    if body.id_card is not None:
        user.id_card = body.id_card
    db.commit()
    return {"user": _public_user(user, include_sensitive=True)}


@router.post("/users/{user_id}/approve", status_code=status.HTTP_200_OK)
def approve_user(user_id: int, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if user.role == "admin":
        raise HTTPException(status_code=422, detail={"code": "ADMIN_APPROVAL_BLOCKED", "message": "管理员账号不需要审批"})
    if user.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "USER_STATUS_CONFLICT", "message": "该账号当前不在待审批状态"})
    user.status = "active"
    user.is_active = True
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
    db.commit()
    return {"user": _public_user(user)}
