from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.models import User, UserRole
from app.database import get_db
from app.schemas.auth import TokenData
import logging

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token security
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    # IMPORTANT: Convert sub (user_id) to string - JWT requires string subjects
    if 'sub' in to_encode:
        to_encode['sub'] = str(to_encode['sub'])
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    logger.info(f"Created token for user_id: {data.get('sub')}")
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    
    # Convert sub to string
    if 'sub' in to_encode:
        to_encode['sub'] = str(to_encode['sub'])
    
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def decode_token(token: str) -> TokenData:
    """Decode and validate JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # Get user_id from sub (it's a string in JWT, convert back to int)
        user_id_str: str = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        
        logger.debug(f"Decoded token - user_id_str: {user_id_str}, username: {username}, role: {role}")
        
        if user_id_str is None or username is None:
            logger.error("Token missing required fields")
            raise credentials_exception
        
        # Convert user_id back to integer
        try:
            user_id = int(user_id_str)
        except (ValueError, TypeError):
            logger.error(f"Invalid user_id in token: {user_id_str}")
            raise credentials_exception
            
        return TokenData(user_id=user_id, username=username, role=role)
    except JWTError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Token decode error: {str(e)}")
        raise credentials_exception


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        logger.debug(f"Received token: {token[:20]}...")
        
        token_data = await decode_token(token)
        
        result = await db.execute(
            select(User).where(User.id == token_data.user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            logger.error(f"User not found or inactive for user_id: {token_data.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        logger.debug(f"User authenticated: {user.username}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure user is active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


class RoleChecker:
    """Check user roles for authorization"""
    
    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user


# Role dependency shortcuts
require_manager = RoleChecker([UserRole.STORE_MANAGER, UserRole.SUPER_ADMIN])
require_admin = RoleChecker([UserRole.SUPER_ADMIN])


def check_branch_access(user: User, branch_id: int) -> bool:
    """Check if user has access to a specific branch"""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    
    if user.role == UserRole.STORE_MANAGER:
        # Managers can access all branches in their store
        return True
    
    # Staff can only access their assigned branch
    return user.branch_id == branch_id


async def verify_branch_access(
    branch_id: int,
    user: User = Depends(get_current_active_user)
) -> bool:
    """Dependency to verify branch access"""
    if not check_branch_access(user, branch_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this branch"
        )
    return True