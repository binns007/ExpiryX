from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class BranchBase(BaseModel):
    branch_id: str
    name: str
    location: Optional[str] = None
    contact_phone: Optional[str] = None


class BranchCreate(BranchBase):
    store_id: str


class BranchResponse(BranchBase):
    id: int
    store_id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True