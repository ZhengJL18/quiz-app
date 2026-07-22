"""Auth schemas."""
from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    password: str
    api_key: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    api_key_masked: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
