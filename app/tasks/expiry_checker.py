from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, and_
from datetime import date, timedelta
from typing import List
import logging
from app.database import engine
from app.models import Batch, Alert, Product, Branch  # REMOVED AlertLevel, AlertStatus
from app.config import settings
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Create async session for background tasks
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def check_expiring_batches():
    """
    Background task to check for expiring batches and create alerts
    Runs periodically (e.g., daily at midnight and noon)
    """
    
    logger.info("Starting expiry check task...")
    
    async with AsyncSessionLocal() as db:
        try:
            today = date.today()
            warning_date = today + timedelta(days=settings.EXPIRY_WARNING_DAYS)
            critical_date = today + timedelta(days=settings.EXPIRY_CRITICAL_DAYS)
            
            # Find batches expiring soon
            result = await db.execute(
                select(Batch, Product, Branch)
                .join(Product, Batch.product_id == Product.id)
                .join(Branch, Batch.branch_id == Branch.id)
                .where(
                    and_(
                        Batch.is_active == True,
                        Batch.expiry_date > today,
                        Batch.expiry_date <= warning_date,
                        Batch.current_quantity > 0
                    )
                )
            )
            
            batches_to_alert = result.all()
            
            alerts_created = 0
            notifications_sent = 0
            
            for batch, product, branch in batches_to_alert:
                days_remaining = (batch.expiry_date - today).days
                
                # Determine alert level - USE LOWERCASE STRINGS
                if days_remaining <= settings.EXPIRY_CRITICAL_DAYS:
                    alert_level = "critical"  # lowercase string
                    alert_type = "expiry_critical"
                    message = (
                        f"CRITICAL: {product.name} (Batch: {batch.batch_number}) "
                        f"expires in {days_remaining} day(s)! "
                        f"{batch.current_quantity} units remaining."
                    )
                else:
                    alert_level = "warning"  # lowercase string
                    alert_type = "expiry_warning"
                    message = (
                        f"WARNING: {product.name} (Batch: {batch.batch_number}) "
                        f"expires in {days_remaining} days. "
                        f"{batch.current_quantity} units remaining."
                    )
                
                # Check if alert already exists for today
                existing_alert = await db.execute(
                    select(Alert).where(
                        and_(
                            Alert.batch_id == batch.id,
                            Alert.alert_type == alert_type,
                            Alert.created_at >= today
                        )
                    )
                )
                
                if existing_alert.scalar_one_or_none():
                    continue  # Alert already created today
                
                # Create alert - FIXED: Use the variables, not hardcoded values!
                new_alert = Alert(
                    batch_id=batch.id,
                    branch_id=branch.id,
                    alert_level=alert_level,  # Use the variable!
                    alert_type=alert_type,    # Use the variable!
                    message=message,
                    days_to_expiry=days_remaining,  # Added this field
                    status="pending"  # lowercase string
                )
                
                db.add(new_alert)
                alerts_created += 1
                
                # Send notification
                try:
                    notification_service = NotificationService()
                    await notification_service.send_expiry_alert(
                        branch=branch,
                        product=product,
                        batch=batch,
                        days_remaining=days_remaining,
                        alert_level=alert_level
                    )
                    notifications_sent += 1
                except Exception as e:
                    logger.error(f"Failed to send notification: {str(e)}")
            
            # Check for expired batches
            expired_result = await db.execute(
                select(Batch)
                .where(
                    and_(
                        Batch.is_active == True,
                        Batch.expiry_date <= today,
                        Batch.is_expired == False
                    )
                )
            )
            
            expired_batches = expired_result.scalars().all()
            expired_count = 0
            
            for batch in expired_batches:
                batch.is_expired = True
                batch.is_active = False
                expired_count += 1
            
            await db.commit()
            
            logger.info(
                f"Expiry check completed: "
                f"{alerts_created} alerts created, "
                f"{notifications_sent} notifications sent, "
                f"{expired_count} batches marked as expired"
            )
            
        except Exception as e:
            logger.error(f"Error in expiry check task: {str(e)}", exc_info=True)
            await db.rollback()


async def check_low_stock():
    """
    Check for low stock items and create alerts
    """
    
    logger.info("Starting low stock check...")
    
    async with AsyncSessionLocal() as db:
        try:
            LOW_STOCK_THRESHOLD = 5
            
            result = await db.execute(
                select(Batch, Product, Branch)
                .join(Product, Batch.product_id == Product.id)
                .join(Branch, Batch.branch_id == Branch.id)
                .where(
                    and_(
                        Batch.is_active == True,
                        Batch.current_quantity > 0,
                        Batch.current_quantity <= LOW_STOCK_THRESHOLD
                    )
                )
            )
            
            low_stock_batches = result.all()
            alerts_created = 0
            
            for batch, product, branch in low_stock_batches:
                # Check if alert already exists - FIXED: use string not enum
                existing_alert = await db.execute(
                    select(Alert).where(
                        and_(
                            Alert.batch_id == batch.id,
                            Alert.alert_type == "low_stock",
                            Alert.status == "pending"  # lowercase string
                        )
                    )
                )
                
                if existing_alert.scalar_one_or_none():
                    continue
                
                message = (
                    f"LOW STOCK: {product.name} (Batch: {batch.batch_number}) "
                    f"has only {batch.current_quantity} units remaining."
                )
                
                # FIXED: Use strings, not enums
                new_alert = Alert(
                    batch_id=batch.id,
                    branch_id=branch.id,
                    alert_level="info",  # lowercase string
                    alert_type="low_stock",
                    message=message,
                    status="pending"  # lowercase string
                )
                
                db.add(new_alert)
                alerts_created += 1
            
            await db.commit()
            
            logger.info(f"Low stock check completed: {alerts_created} alerts created")
            
        except Exception as e:
            logger.error(f"Error in low stock check: {str(e)}", exc_info=True)
            await db.rollback()


def start_expiry_checker():
    """
    Start the background scheduler for expiry checks
    """
    
    scheduler = AsyncIOScheduler()
    
    # Run expiry check twice daily (midnight and noon)
    scheduler.add_job(
        check_expiring_batches,
        CronTrigger(hour='0,12', minute='0'),
        id='expiry_check',
        name='Check expiring batches',
        replace_existing=True
    )
    
    # Run low stock check every 6 hours
    scheduler.add_job(
        check_low_stock,
        CronTrigger(hour='*/6'),
        id='low_stock_check',
        name='Check low stock items',
        replace_existing=True
    )
    
    # Run immediately on startup
    scheduler.add_job(
        check_expiring_batches,
        'date',
        run_date=None,  # Run immediately
        id='expiry_check_startup'
    )
    
    scheduler.start()
    logger.info("Expiry checker scheduler started")
    
    return scheduler