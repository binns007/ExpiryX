from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional
from datetime import date, timedelta
from app.database import get_db
from app.models import Batch, Product, Sale, User
from app.schemas.batch import BatchResponse
from app.core.security import get_current_active_user
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary")
async def get_inventory_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get inventory summary for current branch
    Total stock, value, expiring items, etc.
    """
    
    today = date.today()
    
    # Get total inventory value
    value_result = await db.execute(
        select(
            func.sum(Batch.current_quantity * Batch.selling_price).label('total_value'),
            func.sum(Batch.current_quantity).label('total_units'),
            func.count(func.distinct(Batch.product_id)).label('unique_products')
        )
        .where(
            and_(
                Batch.branch_id == current_user.branch_id,
                Batch.is_active == True,
                Batch.current_quantity > 0
            )
        )
    )
    
    value_data = value_result.first()
    
    # Get expiring items breakdown
    expiry_result = await db.execute(
        select(
            func.count(Batch.id).label('total'),
            func.sum(
                func.case(
                    (Batch.expiry_date <= today + timedelta(days=1), 1),
                    else_=0
                )
            ).label('critical'),
            func.sum(
                func.case(
                    (and_(
                        Batch.expiry_date > today + timedelta(days=1),
                        Batch.expiry_date <= today + timedelta(days=5)
                    ), 1),
                    else_=0
                )
            ).label('warning')
        )
        .where(
            and_(
                Batch.branch_id == current_user.branch_id,
                Batch.is_active == True,
                Batch.expiry_date > today
            )
        )
    )
    
    expiry_data = expiry_result.first()
    
    # Get top products by value
    top_products_result = await db.execute(
        select(
            Product.name,
            Product.barcode,
            func.sum(Batch.current_quantity).label('total_quantity'),
            func.sum(Batch.current_quantity * Batch.selling_price).label('total_value')
        )
        .join(Product, Batch.product_id == Product.id)
        .where(
            and_(
                Batch.branch_id == current_user.branch_id,
                Batch.is_active == True
            )
        )
        .group_by(Product.id, Product.name, Product.barcode)
        .order_by(func.sum(Batch.current_quantity * Batch.selling_price).desc())
        .limit(10)
    )
    
    top_products = []
    for row in top_products_result:
        top_products.append({
            "product_name": row.name,
            "barcode": row.barcode,
            "total_quantity": row.total_quantity,
            "total_value": float(row.total_value or 0)
        })
    
    return {
        "total_inventory_value": float(value_data.total_value or 0),
        "total_units": value_data.total_units or 0,
        "unique_products": value_data.unique_products or 0,
        "expiring_batches": {
            "total": expiry_data.total or 0,
            "critical": expiry_data.critical or 0,
            "warning": expiry_data.warning or 0
        },
        "top_products_by_value": top_products
    }


@router.get("/movements")
async def get_inventory_movements(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get inventory movement history (sales)
    """
    
    query = (
        select(Sale, Batch, Product)
        .join(Batch, Sale.batch_id == Batch.id)
        .join(Product, Batch.product_id == Product.id)
        .where(Batch.branch_id == current_user.branch_id)
        .order_by(Sale.sale_timestamp.desc())
    )
    
    if start_date:
        query = query.where(Sale.sale_timestamp >= start_date)
    
    if end_date:
        query = query.where(Sale.sale_timestamp <= end_date)
    
    if product_id:
        query = query.where(Product.id == product_id)
    
    query = query.limit(100)
    
    result = await db.execute(query)
    movements = result.all()
    
    return [
        {
            "sale_id": sale.id,
            "product_name": product.name,
            "batch_number": batch.batch_number,
            "quantity_sold": sale.quantity_sold,
            "sale_price": float(sale.sale_price),
            "total_amount": float(sale.quantity_sold * sale.sale_price),
            "sale_timestamp": sale.sale_timestamp,
            "pos_transaction_id": sale.pos_transaction_id
        }
        for sale, batch, product in movements
    ]


@router.get("/stock-levels")
async def get_stock_levels(
    low_stock_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current stock levels for all products
    """
    
    query = (
        select(
            Product.id,
            Product.name,
            Product.barcode,
            Product.category,
            func.sum(Batch.current_quantity).label('total_quantity'),
            func.count(Batch.id).label('batch_count'),
            func.min(Batch.expiry_date).label('earliest_expiry')
        )
        .join(Product, Batch.product_id == Product.id)
        .where(
            and_(
                Batch.branch_id == current_user.branch_id,
                Batch.is_active == True
            )
        )
        .group_by(Product.id, Product.name, Product.barcode, Product.category)
    )
    
    if low_stock_only:
        query = query.having(func.sum(Batch.current_quantity) <= 10)
    
    result = await db.execute(query)
    stock_levels = result.all()
    
    return [
        {
            "product_id": row.id,
            "product_name": row.name,
            "barcode": row.barcode,
            "category": row.category,
            "total_quantity": row.total_quantity,
            "batch_count": row.batch_count,
            "earliest_expiry": row.earliest_expiry,
            "days_to_earliest_expiry": (row.earliest_expiry - date.today()).days if row.earliest_expiry else None
        }
        for row in stock_levels
    ]