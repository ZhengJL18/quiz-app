"""Authentication router — login, signup, me, update profile."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from jose import jwt
import bcrypt

from app.config import settings
from app.db.engine import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.services.redis_state import login_failure_check
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserOut

router = APIRouter()


def _create_token(user_id: int, role: str = "user") -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_db)):
    # Brute-force protection
    if not await login_failure_check(body.username):
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")

    user = db.query(User).filter_by(username=body.username, is_active=True).first()
    if not user or not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return TokenResponse(access_token=_create_token(user.id, user.role or "user"), user=UserOut.model_validate(user))


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, db=Depends(get_db)):
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少8位")

    user = User(
        username=body.username,
        password_hash=bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode(),
        api_key=body.api_key or None,
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenResponse(access_token=_create_token(user.id, user.role or "user"), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


class UpdateMeRequest(BaseModel):
    username: str | None = None
    old_password: str | None = None
    password: str | None = None
    api_key: str | None = None


@router.put("/me", response_model=UserOut)
def update_me(body: UpdateMeRequest, db=Depends(get_db), current_user: User = Depends(get_current_user)):
    user = db.query(User).filter_by(id=current_user.id).first()
    if not user:
        raise HTTPException(status_code=404)
    if body.username is not None:
        existing = db.query(User).filter(User.username == body.username, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="用户名已被占用")
        user.username = body.username
    if body.password is not None:
        if len(body.password) < 8:
            raise HTTPException(status_code=400, detail="密码至少8位")
        if not body.old_password:
            raise HTTPException(status_code=400, detail="修改密码需要提供旧密码")
        if not bcrypt.checkpw(body.old_password.encode(), user.password_hash.encode()):
            raise HTTPException(status_code=403, detail="旧密码不正确")
        user.password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    if body.api_key is not None:
        user.api_key = body.api_key if body.api_key.strip() else None
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
