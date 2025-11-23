from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class StoreBase(BaseModel):
    store_id: str
    name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None


class StoreCreate(StoreBase):
    pass


class StoreResponse(StoreBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True