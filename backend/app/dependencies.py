"""FastAPI dependencies: DB session, JWT auth, per-user AI client."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings
from app.db.engine import SessionLocal
from app.db.models import User
from app.ai_service.client import DeepSeekClient

security_scheme = HTTPBearer()


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db=Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if not user: raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def get_ai_client(user: User = Depends(get_current_user)) -> DeepSeekClient:
    """Return a DeepSeekClient using the user's personal API key if set."""
    return DeepSeekClient(api_key=user.api_key)
