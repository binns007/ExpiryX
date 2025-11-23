from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.schemas.product import ProductCreate, ProductResponse
from app.models import Product
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.core.security import get_current_user
from sqlalchemy import select

router_products = APIRouter()


@router_products.post("/", response_model=ProductResponse, status_code=201)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new product"""
    
    # Check if barcode exists
    existing = await db.execute(
        select(Product).where(Product.barcode == product_data.barcode)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Product with this barcode already exists")
    
    new_product = Product(**product_data.dict())
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    
    return ProductResponse.from_orm(new_product)


@router_products.get("/{barcode}", response_model=ProductResponse)
async def get_product_by_barcode(
    barcode: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get product by barcode"""
    
    result = await db.execute(
        select(Product).where(Product.barcode == barcode)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return ProductResponse.from_orm(product)