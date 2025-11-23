from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from app.config import settings
from app.database import init_db, close_db
from app.api.v1 import auth, stores, products, batches, inventory, pos_integration, alerts, dashboard, barcode

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events - startup and shutdown"""
    # Startup
    logger.info("Starting ExpiryX application...")
    await init_db()
    logger.info("Database initialized")
    
    # Start background tasks (expiry checker)
    from app.tasks.expiry_checker import start_expiry_checker
    start_expiry_checker()
    logger.info("Background tasks started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down ExpiryX...")
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Expiry Management System for Indian Retail Stores",
    lifespan=lifespan
)

# CORS middleware - UPDATED WITH FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local testing
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to ExpiryX - Expiry Management System",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


from app.api.v1.barcode import router_barcode
from app.api.v1.alerts import router as alerts_router
from app.api.v1.products import router_products
from app.api.v1.stores import router_stores


# Include API routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(router_stores, prefix=f"{settings.API_V1_PREFIX}/stores", tags=["Stores"])
app.include_router(router_products, prefix=f"{settings.API_V1_PREFIX}/products", tags=["Products"])
app.include_router(batches.router, prefix=f"{settings.API_V1_PREFIX}/batches", tags=["Batches"])
app.include_router(inventory.router, prefix=f"{settings.API_V1_PREFIX}/inventory", tags=["Inventory"])
app.include_router(pos_integration.router, prefix=f"{settings.API_V1_PREFIX}/pos", tags=["POS Integration"])
app.include_router(alerts_router, prefix=f"{settings.API_V1_PREFIX}/alerts", tags=["Alerts"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(router_barcode, prefix=f"{settings.API_V1_PREFIX}/barcode", tags=["Barcode"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )