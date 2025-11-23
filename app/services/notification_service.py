from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from typing import List
from jinja2 import Template
from app.config import settings
from app.models import Branch, Product, Batch, AlertLevel, User
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications (email, in-app, etc.)"""
    
    def __init__(self):
        self.mail_config = ConnectionConfig(
            MAIL_USERNAME=settings.MAIL_USERNAME,
            MAIL_PASSWORD=settings.MAIL_PASSWORD,
            MAIL_FROM=settings.MAIL_FROM,
            MAIL_PORT=settings.MAIL_PORT,
            MAIL_SERVER=settings.MAIL_SERVER,
            MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
            MAIL_STARTTLS=settings.MAIL_TLS,
            MAIL_SSL_TLS=settings.MAIL_SSL,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True
        )
        self.fast_mail = FastMail(self.mail_config)
    
    async def send_expiry_alert(
        self,
        branch: Branch,
        product: Product,
        batch: Batch,
        days_remaining: int,
        alert_level: AlertLevel
    ):
        """Send expiry alert notification"""
        
        try:
            # Email template
            subject = f"{'CRITICAL' if alert_level == AlertLevel.CRITICAL else 'WARNING'}: Product Expiry Alert"
            
            html_template = """
            <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2 style="color: {{ color }};">{{ title }}</h2>
                    <p><strong>Branch:</strong> {{ branch_name }}</p>
                    <p><strong>Product:</strong> {{ product_name }}</p>
                    <p><strong>Batch Number:</strong> {{ batch_number }}</p>
                    <p><strong>Expiry Date:</strong> {{ expiry_date }}</p>
                    <p><strong>Days Remaining:</strong> {{ days_remaining }}</p>
                    <p><strong>Current Stock:</strong> {{ current_quantity }} units</p>
                    <hr>
                    <p style="color: #666;">
                        This is an automated alert from ExpiryX. 
                        Please take necessary action to clear the stock before expiry.
                    </p>
                </body>
            </html>
            """
            
            color = "#dc3545" if alert_level == AlertLevel.CRITICAL else "#ffc107"
            title = "CRITICAL: Immediate Action Required!" if alert_level == AlertLevel.CRITICAL else "Warning: Product Expiring Soon"
            
            template = Template(html_template)
            html_content = template.render(
                color=color,
                title=title,
                branch_name=branch.name,
                product_name=product.name,
                batch_number=batch.batch_number,
                expiry_date=batch.expiry_date.strftime("%d-%m-%Y"),
                days_remaining=days_remaining,
                current_quantity=batch.current_quantity
            )
            
            # For demo purposes, we'll log instead of actually sending
            # In production, uncomment the email sending code below
            
            logger.info(
                f"Alert notification prepared for {branch.name}: "
                f"{product.name} expires in {days_remaining} days"
            )
            
            # Uncomment for actual email sending:
            # if branch.contact_email:
            #     message = MessageSchema(
            #         subject=subject,
            #         recipients=[branch.contact_email],
            #         body=html_content,
            #         subtype="html"
            #     )
            #     await self.fast_mail.send_message(message)
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
            raise
    
    async def send_low_stock_alert(
        self,
        branch: Branch,
        product: Product,
        batch: Batch
    ):
        """Send low stock alert"""
        
        logger.info(
            f"Low stock alert for {branch.name}: "
            f"{product.name} - {batch.current_quantity} units remaining"
        )
    
    async def send_batch_sold_out_notification(
        self,
        branch: Branch,
        product: Product,
        batch: Batch
    ):
        """Notify when a batch is sold out"""
        
        logger.info(
            f"Batch sold out: {product.name} (Batch: {batch.batch_number}) "
            f"at {branch.name}"
        )