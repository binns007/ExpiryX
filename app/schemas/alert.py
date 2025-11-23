from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class AlertResponse(BaseModel):
    id: int
    batch_id: int
    batch_number: str
    product_name: str
    product_barcode: str
    branch_id: int
    alert_level: AlertLevel
    alert_type: str
    message: str
    days_to_expiry: Optional[int]
    status: AlertStatus
    created_at: datetime
    acknowledged_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    alert_ids: List[int]