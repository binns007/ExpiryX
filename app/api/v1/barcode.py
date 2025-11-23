from fastapi import APIRouter, Depends
from app.schemas.barcode import BarcodeProductInfo
import httpx
from app.config import settings

router_barcode = APIRouter()


@router_barcode.get("/lookup/{barcode}", response_model=BarcodeProductInfo)
async def lookup_barcode(barcode: str):
    """
    Look up product information by barcode
    Uses external API or database
    """
    
    try:
        # Try external barcode API if configured
        if settings.BARCODE_API_KEY:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.BARCODE_API_URL}",
                    params={"upc": barcode},
                    headers={"Authorization": f"Bearer {settings.BARCODE_API_KEY}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("items"):
                        item = data["items"][0]
                        return BarcodeProductInfo(
                            barcode=barcode,
                            name=item.get("title"),
                            brand=item.get("brand"),
                            category=item.get("category"),
                            description=item.get("description"),
                            found=True
                        )
        
        # Return not found
        return BarcodeProductInfo(
            barcode=barcode,
            name=None,
            brand=None,
            category=None,
            description=None,
            found=False
        )
    
    except Exception as e:
        logger.error(f"Barcode lookup error: {str(e)}")
        return BarcodeProductInfo(
            barcode=barcode,
            name=None,
            brand=None,
            category=None,
            description=None,
            found=False
        )
