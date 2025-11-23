from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from datetime import date, timedelta
from typing import List, Optional
from app.database import get_db
from app.models import Batch, Product, Alert, Sale, Branch, User, UserRole
from app.schemas.dashboard import DashboardResponse, DashboardStats, ExpiryBreakdown, CategoryStats
from app.schemas.alert import AlertResponse
from app.schemas.batch import BatchResponse

from app.core.security import get_current_active_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def calculate_days_to_expiry(expiry_date: date) -> int:
    """Calculate days remaining until expiry"""
    return (expiry_date - date.today()).days


@router.get("/", response_model=DashboardResponse)
async def get_dashboard(
    branch_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get comprehensive dashboard data for store manager
    Shows: stats, expiry breakdown, alerts, top expiring items
    """
    
    # Determine which branch(es) to query
    if current_user.role == UserRole.STAFF:
        # Staff can only see their own branch
        branch_filter = current_user.branch_id
    elif branch_id:
        # Manager requesting specific branch
        branch_filter = branch_id
    else:
        # Manager viewing all branches (aggregate)
        branch_filter = None
    
    today = date.today()
    five_days = today + timedelta(days=5)
    one_day = today + timedelta(days=1)
    
    # Build base query
    base_query = select(Batch).where(Batch.is_active == True)
    if branch_filter:
        base_query = base_query.where(Batch.branch_id == branch_filter)
    else:
        # Manager can see all branches in their store
        branches_result = await db.execute(
            select(Branch.id).where(Branch.store_id == current_user.store_id)
        )
        branch_ids = [b[0] for b in branches_result.all()]
        base_query = base_query.where(Batch.branch_id.in_(branch_ids))
    
    # 1. Overall Statistics
    stats_result = await db.execute(
        select(
            func.count(Batch.id).label('total_batches'),
            func.sum(case((Batch.is_active == True, 1), else_=0)).label('active_batches'),
            func.sum(case((Batch.is_expired == True, 1), else_=0)).label('expired_batches'),
            func.sum(
                case(
                    (and_(Batch.expiry_date <= five_days, Batch.expiry_date > today), 1),
                    else_=0
                )
            ).label('expiring_soon'),
            func.sum(
                case(
                    (and_(Batch.expiry_date <= one_day, Batch.expiry_date > today), 1),
                    else_=0
                )
            ).label('critical_expiry'),
            func.count(func.distinct(Batch.product_id)).label('total_products'),
            func.sum(case((Batch.current_quantity < 5, 1), else_=0)).label('low_stock')
        )
        .select_from(Batch)
        .where(base_query.whereclause)
    )
    stats_row = stats_result.first()
    
    # Get alert counts
    alert_query = select(func.count(Alert.id)).where(Alert.status == 'pending')
    if branch_filter:
        alert_query = alert_query.where(Alert.branch_id == branch_filter)
    else:
        alert_query = alert_query.where(Alert.branch_id.in_(branch_ids))
    
    alert_count_result = await db.execute(alert_query)
    pending_alerts = alert_count_result.scalar() or 0
    
    stats = DashboardStats(
        total_batches=stats_row.total_batches or 0,
        active_batches=stats_row.active_batches or 0,
        expired_batches=stats_row.expired_batches or 0,
        expiring_soon=stats_row.expiring_soon or 0,
        critical_expiry=stats_row.critical_expiry or 0,
        total_products=stats_row.total_products or 0,
        low_stock_items=stats_row.low_stock or 0,
        total_alerts=pending_alerts,
        pending_alerts=pending_alerts
    )
    
    # 2. Expiry Breakdown
    expiry_result = await db.execute(
        select(
            func.sum(case((Batch.expiry_date < today, 1), else_=0)).label('expired'),
            func.sum(
                case(
                    (and_(Batch.expiry_date >= today, Batch.expiry_date <= one_day), 1),
                    else_=0
                )
            ).label('critical'),
            func.sum(
                case(
                    (and_(Batch.expiry_date > one_day, Batch.expiry_date <= five_days), 1),
                    else_=0
                )
            ).label('warning'),
            func.sum(case((Batch.expiry_date > five_days, 1), else_=0)).label('safe')
        )
        .select_from(Batch)
        .where(base_query.whereclause)
    )
    expiry_row = expiry_result.first()
    
    expiry_breakdown = ExpiryBreakdown(
        expired=expiry_row.expired or 0,
        critical=expiry_row.critical or 0,
        warning=expiry_row.warning or 0,
        safe=expiry_row.safe or 0
    )
    
    # 3. Category Statistics
    category_result = await db.execute(
        select(
            Product.category,
            func.count(Batch.id).label('total_batches'),
            func.sum(
                case(
                    (and_(Batch.expiry_date <= five_days, Batch.expiry_date > today), 1),
                    else_=0
                )
            ).label('expiring_soon'),
            func.sum(Batch.current_quantity * Batch.selling_price).label('total_value')
        )
        .select_from(Batch)
        .join(Product)
        .where(base_query.whereclause)
        .group_by(Product.category)
        .order_by(func.count(Batch.id).desc())
        .limit(10)
    )
    
    category_stats = []
    for row in category_result:
        category_stats.append(
            CategoryStats(
                category=row.category or "Uncategorized",
                total_batches=row.total_batches,
                expiring_soon=row.expiring_soon or 0,
                total_value=float(row.total_value or 0)
            )
        )
    
    # 4. Recent Alerts
    alerts_query = (
        select(Alert, Batch, Product)
        .join(Batch, Alert.batch_id == Batch.id)
        .join(Product, Batch.product_id == Product.id)
        .where(Alert.status == 'pending')
        .order_by(Alert.created_at.desc())
        .limit(10)
    )
    
    if branch_filter:
        alerts_query = alerts_query.where(Alert.branch_id == branch_filter)
    else:
        alerts_query = alerts_query.where(Alert.branch_id.in_(branch_ids))
    
    alerts_result = await db.execute(alerts_query)
    
    recent_alerts = []
    for alert, batch, product in alerts_result:
        recent_alerts.append(
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
        )
    
    # 5. Top Expiring Batches
    expiring_query = (
        select(Batch, Product)
        .join(Product)
        .where(
            and_(
                base_query.whereclause,
                Batch.expiry_date > today,
                Batch.expiry_date <= five_days,
                Batch.is_active == True
            )
        )
        .order_by(Batch.expiry_date.asc())
        .limit(10)
    )
    
    expiring_result = await db.execute(expiring_query)
    
    top_expiring = []
    for batch, product in expiring_result:
        top_expiring.append(
            BatchResponse(
                id=batch.id,
                batch_number=batch.batch_number,
                product_id=product.id,
                product_name=product.name,
                product_barcode=product.barcode,
                branch_id=batch.branch_id,
                initial_quantity=batch.initial_quantity,
                current_quantity=batch.current_quantity,
                expiry_date=batch.expiry_date,
                manufacture_date=batch.manufacture_date,
                cost_price=float(batch.cost_price) if batch.cost_price else None,
                selling_price=float(batch.selling_price) if batch.selling_price else None,
                is_active=batch.is_active,
                is_expired=batch.is_expired,
                days_to_expiry=calculate_days_to_expiry(batch.expiry_date),
                created_at=batch.created_at,
                created_by=batch.created_by
            )
        )
    
    return DashboardResponse(
        stats=stats,
        expiry_breakdown=expiry_breakdown,
        category_stats=category_stats,
        recent_alerts=recent_alerts,
        top_expiring_batches=top_expiring
    )


@router.get("/branches")
async def get_branch_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get overview of all branches (Manager only)
    """
    
    if current_user.role == UserRole.STAFF:
        return {"error": "Insufficient permissions"}
    
    # Get all branches for this store
    branches_result = await db.execute(
        select(Branch).where(
            Branch.store_id == current_user.store_id,
            Branch.is_active == True
        )
    )
    branches = branches_result.scalars().all()
    
    branch_data = []
    today = date.today()
    five_days = today + timedelta(days=5)
    
    for branch in branches:
        # Get stats for this branch
        stats_result = await db.execute(
            select(
                func.count(Batch.id).label('total_batches'),
                func.sum(case((Batch.is_active == True, 1), else_=0)).label('active'),
                func.sum(
                    case(
                        (and_(Batch.expiry_date <= five_days, Batch.expiry_date > today), 1),
                        else_=0
                    )
                ).label('expiring_soon')
            )
            .where(Batch.branch_id == branch.id)
        )
        stats = stats_result.first()
        
        # Get alert count
        alert_result = await db.execute(
            select(func.count(Alert.id))
            .where(Alert.branch_id == branch.id, Alert.status == 'pending')
        )
        alert_count = alert_result.scalar() or 0
        
        branch_data.append({
            "branch_id": branch.branch_id,
            "branch_name": branch.name,
            "location": branch.location,
            "total_batches": stats.total_batches or 0,
            "active_batches": stats.active or 0,
            "expiring_soon": stats.expiring_soon or 0,
            "pending_alerts": alert_count
        })
    
    return {"branches": branch_data}