"""
Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class StockSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str


class StockCreate(BaseModel):
    symbol: str
    name: str
    exchange: str = "NSE"
    buy_price_min: Optional[float] = Field(default=None, ge=0)
    buy_price_max: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None


class StockUpdate(BaseModel):
    buy_price_min: Optional[float] = None
    buy_price_max: Optional[float] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class StockOut(BaseModel):
    id: int
    symbol: str
    name: str
    exchange: str
    buy_price_min: Optional[float]
    buy_price_max: Optional[float]
    notes: Optional[str]
    is_active: bool
    last_price: Optional[float]
    last_rsi: Optional[float]
    last_updated: Optional[datetime]
    signal: Optional[str] = None

    class Config:
        from_attributes = True


class RefreshResult(BaseModel):
    symbol: str
    success: bool
    price: Optional[float] = None
    rsi: Optional[float] = None
    signal: Optional[str] = None
    error: Optional[str] = None


class RagQuery(BaseModel):
    question: str


class RagResponse(BaseModel):
    answer: str
    sources: List[str]
    mode: str
