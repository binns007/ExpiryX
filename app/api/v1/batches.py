from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from datetime import date, datetime, timedelta
from typing import Optional, List
from app.database import get_db
from app.models import Batch, Product, User, Branch
from app.schemas.batch import BatchCreate, BatchUpdate, BatchResponse
from app.schemas.pagination import PaginatedResponse
from app.core.security import get_current_active_user, check_branch_access
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def calculate_days_to_expiry(expiry_date: date) -> int:
    """Calculate days remaining until expiry"""
    return (expiry_date - date.today()).days


async def get_or_create_product(db: AsyncSession, batch_data: BatchCreate) -> Product:
    """Get existing product or create new one"""
    
    # If product_id provided, fetch it
    if batch_data.product_id:
        result = await db.execute(
            select(Product).where(Product.id == batch_data.product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return product
    
    # If barcode provided, try to find existing product
    if batch_data.barcode:
        result = await db.execute(
            select(Product).where(Product.barcode == batch_data.barcode)
        )
        product = result.scalar_one_or_none()
        
        if product:
            return product
        
        # Create new product if not found
        if not batch_data.product_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product name required for new product"
            )
        
        new_product = Product(
            barcode=batch_data.barcode,
            name=batch_data.product_name,
        )
        db.add(new_product)
        await db.flush()
        return new_product
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either product_id or barcode must be provided"
    )


@router.post("/", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_data: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create new batch entry
    Staff can scan barcode or enter manually
    """
    
    # Verify branch access
    if not check_branch_access(current_user, current_user.branch_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get or create product
    product = await get_or_create_product(db, batch_data)
    
    # Check if batch already exists
    existing_batch = await db.execute(
        select(Batch).where(
            Batch.batch_number == batch_data.batch_number,
            Batch.branch_id == current_user.branch_id,
            Batch.product_id == product.id
        )
    )
    if existing_batch.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch with this number already exists for this product"
        )
    
    # Create new batch
    new_batch = Batch(
        batch_number=batch_data.batch_number,
        product_id=product.id,
        branch_id=current_user.branch_id,
        created_by=current_user.id,
        initial_quantity=batch_data.initial_quantity,
        current_quantity=batch_data.initial_quantity,
        expiry_date=batch_data.expiry_date,
        manufacture_date=batch_data.manufacture_date,
        cost_price=batch_data.cost_price,
        selling_price=batch_data.selling_price,
        is_expired=batch_data.expiry_date < date.today()
    )
    
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)
    
    logger.info(f"Batch {new_batch.batch_number} created by {current_user.username}")
    
    # Build response
    return BatchResponse(
        id=new_batch.id,
        batch_number=new_batch.batch_number,
        product_id=product.id,
        product_name=product.name,
        product_barcode=product.barcode,
        branch_id=new_batch.branch_id,
        initial_quantity=new_batch.initial_quantity,
        current_quantity=new_batch.current_quantity,
        expiry_date=new_batch.expiry_date,
        manufacture_date=new_batch.manufacture_date,
        cost_price=float(new_batch.cost_price) if new_batch.cost_price else None,
        selling_price=float(new_batch.selling_price) if new_batch.selling_price else None,
        is_active=new_batch.is_active,
        is_expired=new_batch.is_expired,
        days_to_expiry=calculate_days_to_expiry(new_batch.expiry_date),
        created_at=new_batch.created_at,
        created_by=new_batch.created_by
    )


@router.get("/", response_model=List[BatchResponse])
async def get_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    barcode: Optional[str] = None,
    batch_number: Optional[str] = None,
    expiring_soon: Optional[bool] = None,
    expired: Optional[bool] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get batches with filtering and pagination
    """
    
    query = select(Batch, Product).join(Product).where(
        Batch.branch_id == current_user.branch_id
    )
    
    # Filters
    if active_only:
        query = query.where(Batch.is_active == True)
    
    if barcode:
        query = query.where(Product.barcode == barcode)
    
    if batch_number:
        query = query.where(Batch.batch_number.ilike(f"%{batch_number}%"))
    
    if expiring_soon:
        soon_date = date.today() + timedelta(days=5)
        query = query.where(
            and_(
                Batch.expiry_date <= soon_date,
                Batch.expiry_date > date.today()
            )
        )
    
    if expired:
        query = query.where(Batch.expiry_date <= date.today())
    
    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    batches_with_products = result.all()
    
    # Build response
    batch_responses = []
    for batch, product in batches_with_products:
        batch_responses.append(
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
    
    return batch_responses


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get specific batch details"""
    
    result = await db.execute(
        select(Batch, Product)
        .join(Product)
        .where(
            Batch.id == batch_id,
            Batch.branch_id == current_user.branch_id
        )
    )
    batch_product = result.first()
    
    if not batch_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    batch, product = batch_product
    
    return BatchResponse(
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


@router.patch("/{batch_id}", response_model=BatchResponse)
async def update_batch(
    batch_id: int,
    batch_update: BatchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update batch (quantity, status)"""
    
    result = await db.execute(
        select(Batch, Product)
        .join(Product)
        .where(
            Batch.id == batch_id,
            Batch.branch_id == current_user.branch_id
        )
    )
    batch_product = result.first()
    
    if not batch_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    batch, product = batch_product
    
    # Update fields
    if batch_update.current_quantity is not None:
        batch.current_quantity = batch_update.current_quantity
    
    if batch_update.is_active is not None:
        batch.is_active = batch_update.is_active
    
    await db.commit()
    await db.refresh(batch)
    
    logger.info(f"Batch {batch.batch_number} updated by {current_user.username}")
    
    return BatchResponse(
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