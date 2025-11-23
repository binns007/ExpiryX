from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum



class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    STORE_MANAGER = "store_manager"
    STAFF = "staff"
    
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole


class UserResponse(UserBase):
    id: int
    store_id: int
    branch_id: Optional[int]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str
    store_id: str
    branch_id: Optional[str] = None