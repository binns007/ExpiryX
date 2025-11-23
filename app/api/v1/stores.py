from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.store import StoreCreate, StoreResponse
from app.schemas.branch import BranchCreate, BranchResponse
from app.models import Store, Branch
from app.core.security import require_admin
from app.database import get_db
from app.models import User


router_stores = APIRouter()


@router_stores.post("/", response_model=StoreResponse, status_code=201)
async def create_store(
    store_data: StoreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create new store (Admin only)"""
    
    # Check if store_id exists
    existing = await db.execute(
        select(Store).where(Store.store_id == store_data.store_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Store ID already exists")
    
    new_store = Store(**store_data.dict())
    db.add(new_store)
    await db.commit()
    await db.refresh(new_store)
    
    return StoreResponse.from_orm(new_store)


@router_stores.post("/{store_id}/branches", response_model=BranchResponse, status_code=201)
async def create_branch(
    store_id: str,
    branch_data: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create new branch for store"""
    
    # Find store
    store_result = await db.execute(
        select(Store).where(Store.store_id == store_id)
    )
    store = store_result.scalar_one_or_none()
    
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    new_branch = Branch(
        branch_id=branch_data.branch_id,
        store_id=store.id,
        name=branch_data.name,
        location=branch_data.location,
        contact_phone=branch_data.contact_phone
    )
    
    db.add(new_branch)
    await db.commit()
    await db.refresh(new_branch)
    
    return BranchResponse.from_orm(new_branch)