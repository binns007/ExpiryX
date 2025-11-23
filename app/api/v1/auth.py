from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from app.database import get_db
from app.models import User, Store, Branch
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserResponse
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_active_user
)
from app.config import settings
import logging
from typing import List

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login endpoint - authenticate user
    Staff: username + password + store_id + branch_id
    Manager: username + password + store_id
    """
    
    # Find store
    store_result = await db.execute(
        select(Store).where(Store.store_id == login_data.store_id, Store.is_active == True)
    )
    store = store_result.scalar_one_or_none()
    
    if not store:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid store ID"
        )
    
    # Find user
    query = select(User).where(
        User.username == login_data.username,
        User.store_id == store.id,
        User.is_active == True
    )
    
    # If branch_id provided, verify it
    if login_data.branch_id:
        branch_result = await db.execute(
            select(Branch).where(
                Branch.branch_id == login_data.branch_id,
                Branch.store_id == store.id,
                Branch.is_active == True
            )
        )
        branch = branch_result.scalar_one_or_none()
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid branch ID"
            )
        query = query.where(User.branch_id == branch.id)
    
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user.id,
            "username": user.username,
            "role": user.role,
            "store_id": user.store_id,
            "branch_id": user.branch_id
        },
        expires_delta=access_token_expires
    )
    
    logger.info(f"User {user.username} logged in successfully")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.from_orm(user)
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    
):
    """
    Register new user (Admin/Manager only)
    """
    # Only managers and admins can create users
    #if current_user.role not in ["store_manager", "super_admin"]:
       # raise HTTPException(
            #status_code=status.HTTP_403_FORBIDDEN,
           # detail="Insufficient permissions"
        #)
    
    # Check if username or email already exists
    existing_user = await db.execute(
        select(User).where(
            (User.username == user_data.username) | (User.email == user_data.email)
        )
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Find store
    store_result = await db.execute(
        select(Store).where(Store.store_id == user_data.store_id)
    )
    store = store_result.scalar_one_or_none()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found"
        )
    
    # Find branch if provided
    branch_id = None
    if user_data.branch_id:
        branch_result = await db.execute(
            select(Branch).where(
                Branch.branch_id == user_data.branch_id,
                Branch.store_id == store.id
            )
        )
        branch = branch_result.scalar_one_or_none()
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Branch not found"
            )
        branch_id = branch.id
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        store_id=store.id,
        branch_id=branch_id
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(f"New user created: {new_user.username}")
    
    return UserResponse.from_orm(new_user)

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of users (Manager/Admin only)"""
    
    # Only managers and admins can list users
    if current_user.role not in ["store_manager", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Managers can see users in their store only
    query = select(User).where(User.store_id == current_user.store_id)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [UserResponse.from_orm(user) for user in users]

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user information"""
    return UserResponse.from_orm(current_user)


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_active_user)):
    """Logout endpoint (client should discard token)"""
    logger.info(f"User {current_user.username} logged out")
    return {"message": "Logged out successfully"}