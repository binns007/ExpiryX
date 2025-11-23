from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class SaleCreate(BaseModel):
    batch_id: Optional[int] = None
    barcode: Optional[str] = None
    batch_number: Optional[str] = None
    quantity_sold: int = Field(..., gt=0)
    sale_price: float = Field(..., gt=0)
    pos_transaction_id: str
    sale_timestamp: datetime


class SaleResponse(BaseModel):
    id: int
    batch_id: int
    quantity_sold: int
    sale_price: float
    pos_transaction_id: str
    sale_timestamp: datetime
    synced_at: datetime
    
    class Config:
        from_attributes = True