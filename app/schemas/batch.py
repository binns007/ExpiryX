from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class BatchBase(BaseModel):
    batch_number: str
    product_id: Optional[int] = None
    barcode: Optional[str] = None  # Alternative to product_id
    initial_quantity: int = Field(..., gt=0)
    expiry_date: date
    manufacture_date: Optional[date] = None
    cost_price: Optional[float] = None
    selling_price: Optional[float] = None
    
    @validator('expiry_date')
    def validate_expiry_date(cls, v):
        if v < date.today():
            raise ValueError('Expiry date cannot be in the past')
        return v


class BatchCreate(BatchBase):
    product_name: Optional[str] = None  # For new products


class BatchUpdate(BaseModel):
    current_quantity: Optional[int] = None
    is_active: Optional[bool] = None


class BatchResponse(BaseModel):
    id: int
    batch_number: str
    product_id: int
    product_name: str
    product_barcode: str
    branch_id: int
    initial_quantity: int
    current_quantity: int
    expiry_date: date
    manufacture_date: Optional[date]
    cost_price: Optional[float]
    selling_price: Optional[float]
    is_active: bool
    is_expired: bool
    days_to_expiry: int
    created_at: datetime
    created_by: Optional[int]
    
    class Config:
        from_attributes = True