from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserActiveRequest(BaseModel):
    is_active: bool


def _public_user(user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role, "is_active": user.is_active, "must_change_password": user.must_change_password}


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
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "INVALID_CREDENTIALS", "message": "账号或密码错误"})
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer", "user": _public_user(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if db.scalar(select(User).where(User.username == body.username)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "USERNAME_EXISTS", "message": "账号已存在"})
    user = User(username=body.username, display_name=body.display_name, password_hash=hash_password(body.password), role="operator")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user": _public_user(user)}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": _public_user(user)}


@router.get("/admin-check")
def admin_check(_user: User = Depends(require_admin)) -> dict[str, str]:
    return {"status": "ok"}


@router.get("/users")
def list_users(_user: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    users = db.scalars(select(User).order_by(User.created_at.desc())).all()
    return [_public_user(user) for user in users]


@router.post("/users/{user_id}/reset-password")
def reset_user_password(user_id: int, body: ResetPasswordRequest, _user: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "message": "用户不存在"})
    if user.role == "admin":
        raise HTTPException(status_code=422, detail={"code": "ADMIN_PASSWORD_BLOCKED", "message": "管理员密码不能通过此接口重置"})
    user.password_hash = hash_password(body.password)
    user.must_change_password = True
    db.commit()
    return {"user": _public_user(user)}


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
