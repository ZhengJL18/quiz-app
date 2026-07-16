"""FastAPI dependencies: DB session, JWT auth."""

from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings
from app.db.engine import SessionLocal
from app.db.models import User

security_scheme = HTTPBearer()


def get_db():
    """Yield a DB session, close after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db=Depends(get_db),
) -> User:
    """Decode JWT token and return the current user."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=401, detail="Invalid token: no subject")
        user_id = int(user_id_str)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter_by(id=user_id, is_active=True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user
