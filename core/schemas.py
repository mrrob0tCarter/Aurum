# core/schemas.py
from pydantic import BaseModel
from datetime import datetime

class PriceBar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class NewsItem(BaseModel):
    timestamp: datetime
    source: str
    headline: str
    url: str
    impact: str | None  # HIGH / MEDIUM / LOW

class AssetSnapshot(BaseModel):
    symbol: str
    prices: list[PriceBar]
    news: list[NewsItem]
    fundamentals: dict  # yields, DXY level, correlations