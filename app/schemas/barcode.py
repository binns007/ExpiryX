from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum



class BarcodeProductInfo(BaseModel):
    barcode: str
    name: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    description: Optional[str]
    found: bool