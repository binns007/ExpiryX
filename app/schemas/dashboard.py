from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from app.schemas.batch import BatchResponse
from app.schemas.alert import AlertLevel, AlertStatus, AlertResponse



class DashboardStats(BaseModel):
    total_batches: int
    active_batches: int
    expired_batches: int
    expiring_soon: int  # Within 5 days
    critical_expiry: int  # Within 1 day
    total_products: int
    low_stock_items: int
    total_alerts: int
    pending_alerts: int


class ExpiryBreakdown(BaseModel):
    expired: int
    critical: int  # 0-1 days
    warning: int  # 2-5 days
    safe: int  # > 5 days


class CategoryStats(BaseModel):
    category: str
    total_batches: int
    expiring_soon: int
    total_value: float


class DashboardResponse(BaseModel):
    stats: DashboardStats
    expiry_breakdown: ExpiryBreakdown
    category_stats: List[CategoryStats]
    recent_alerts: List[AlertResponse]
    top_expiring_batches: List[BatchResponse]

