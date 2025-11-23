from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import Alert, Batch, Product, User, AlertStatus
from app.schemas.alert import AlertResponse, AlertAcknowledge
from app.core.security import get_current_active_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[AlertStatus] = None,
    alert_level: Optional[str] = None,
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get alerts for current branch/store"""
    
    query = (
        select(Alert, Batch, Product)
        .join(Batch, Alert.batch_id == Batch.id)
        .join(Product, Batch.product_id == Product.id)
        .where(Alert.branch_id == current_user.branch_id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    
    if status:
        query = query.where(Alert.status == status)
    
    if alert_level:
        query = query.where(Alert.alert_level == alert_level)
    
    result = await db.execute(query)
    alerts = result.all()
    
    return [
        AlertResponse(
            id=alert.id,
            batch_id=batch.id,
            batch_number=batch.batch_number,
            product_name=product.name,
            product_barcode=product.barcode,
            branch_id=alert.branch_id,
            alert_level=alert.alert_level,
            alert_type=alert.alert_type,
            message=alert.message,
            days_to_expiry=alert.days_to_expiry,
            status=alert.status,
            created_at=alert.created_at,
            acknowledged_at=alert.acknowledged_at
        )
        for alert, batch, product in alerts
    ]


@router.post("/acknowledge")
async def acknowledge_alerts(
    ack_data: AlertAcknowledge,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Acknowledge one or more alerts"""
    
    result = await db.execute(
        select(Alert).where(
            and_(
                Alert.id.in_(ack_data.alert_ids),
                Alert.branch_id == current_user.branch_id
            )
        )
    )
    alerts = result.scalars().all()
    
    for alert in alerts:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = current_user.id
        alert.acknowledged_at = datetime.utcnow()
    
    await db.commit()
    
    logger.info(f"{len(alerts)} alerts acknowledged by {current_user.username}")
    
    return {"acknowledged": len(alerts), "alert_ids": ack_data.alert_ids}

