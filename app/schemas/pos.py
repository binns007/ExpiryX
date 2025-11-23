from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class POSWebhookPayload(BaseModel):
    """Webhook payload from POS system"""
    transaction_id: str
    items: List[SaleCreate]
    timestamp: datetime
    branch_id: str


class POSSyncRequest(BaseModel):
    """Manual sync request"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None