from pydantic_settings import BaseSettings
from typing import Optional, List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # Application
    APP_NAME: str = "ExpiryX"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:abhi@localhost:5432/expiryx_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production-minimum-32-characters"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Requirements
    MIN_PASSWORD_LENGTH: int = 8
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Email Configuration
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@expiryx.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_FROM_NAME: str = "ExpiryX Alerts"
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False
    
    # Redis (for Celery & Caching)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Expiry Alert Configuration
    EXPIRY_WARNING_DAYS: int = 5  # Alert 5 days before expiry
    EXPIRY_CRITICAL_DAYS: int = 1  # Critical alert 1 day before
    
    # Barcode API (for product information)
    BARCODE_API_KEY: Optional[str] = None  # UPC Database API key
    BARCODE_API_URL: str = "https://api.upcitemdb.com/prod/trial/lookup"
    
    # POS Integration
    POS_WEBHOOK_SECRET: str = "AeSqL87Ui9009IOPPzsde2"
    POS_SYNC_INTERVAL_SECONDS: int = 60  # Real-time sync check interval
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100
    
    # File Upload
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "pdf"]
    
    # Timezone
    TIMEZONE: str = "Asia/Kolkata"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "expiryx.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()