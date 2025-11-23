from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Boolean, Text, Enum, Date, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.database import Base


# Enums
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    STORE_MANAGER = "store_manager"
    STAFF = "staff"


class AlertLevel(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class POSIntegrationType(str, enum.Enum):
    API = "api"
    WEBHOOK = "webhook"
    MIDDLEWARE = "middleware"


# Models
class Store(Base):
    """Store/Retail Chain"""
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "RELIANCE10008"
    name = Column(String(200), nullable=False)
    contact_email = Column(String(100))
    contact_phone = Column(String(20))
    address = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    branches = relationship("Branch", back_populates="store", cascade="all, delete-orphan")
    users = relationship("User", back_populates="store", cascade="all, delete-orphan")


class Branch(Base):
    """Store Branches"""
    __tablename__ = "branches"
    
    id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(String(50), nullable=False, index=True)  # e.g., "ALAPPUZHA1009"
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    location = Column(String(200))
    contact_phone = Column(String(20))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="branches")
    users = relationship("User", back_populates="branch")
    batches = relationship("Batch", back_populates="branch")
    alerts = relationship("Alert", back_populates="branch")
    pos_configs = relationship("POSConfig", back_populates="branch")


class User(Base):
    """Users (Staff & Managers)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    role = Column(Enum(UserRole, name="userrole", values_callable=lambda x: [e.value for e in x]), nullable=False, default=UserRole.STAFF)
    
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"))
    
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    store = relationship("Store", back_populates="users")
    branch = relationship("Branch", back_populates="users")
    batches_created = relationship("Batch", back_populates="created_by_user")


class Product(Base):
    """Products Master"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    barcode = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(300), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    brand = Column(String(100))
    unit = Column(String(50))  # e.g., "packet", "kg", "liter"
    image_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    batches = relationship("Batch", back_populates="product")


class Batch(Base):
    """Product Batches with Expiry"""
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_number = Column(String(100), nullable=False, index=True)
    
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    initial_quantity = Column(Integer, nullable=False)
    current_quantity = Column(Integer, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    manufacture_date = Column(Date)
    
    cost_price = Column(Numeric(10, 2))
    selling_price = Column(Numeric(10, 2))
    
    is_active = Column(Boolean, default=True)
    is_expired = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    product = relationship("Product", back_populates="batches")
    branch = relationship("Branch", back_populates="batches")
    created_by_user = relationship("User", back_populates="batches_created")
    sales = relationship("Sale", back_populates="batch")
    alerts = relationship("Alert", back_populates="batch")


class Sale(Base):
    """Sales Transactions from POS"""
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    
    quantity_sold = Column(Integer, nullable=False)
    sale_price = Column(Numeric(10, 2), nullable=False)
    
    pos_transaction_id = Column(String(100), unique=True, index=True)  # From POS system
    sale_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    batch = relationship("Batch", back_populates="sales")


class Alert(Base):
    """Expiry Alerts"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    
    # Use String instead of Enum - PostgreSQL will still enforce the enum constraint
    alert_level = Column(String(20), nullable=False)  # Changed from Enum
    alert_type = Column(String(50), nullable=False)
    
    message = Column(Text, nullable=False)
    days_to_expiry = Column(Integer)
    
    status = Column(String(20), default="pending")  # Changed from Enum
    acknowledged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    batch = relationship("Batch", back_populates="alerts")
    branch = relationship("Branch", back_populates="alerts")


class POSConfig(Base):
    """POS Integration Configuration"""
    __tablename__ = "pos_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    
    integration_type = Column(Enum(POSIntegrationType), nullable=False)
    
    # API Configuration
    api_endpoint = Column(String(500))
    api_key = Column(String(255))
    webhook_url = Column(String(500))
    
    # Middleware Configuration
    middleware_host = Column(String(100))
    middleware_port = Column(Integer)
    
    is_active = Column(Boolean, default=True)
    last_sync = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    branch = relationship("Branch", back_populates="pos_configs")