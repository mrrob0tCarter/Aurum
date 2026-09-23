"""Aurum — data fetching layer.

Fetches raw market data and news from external sources.
Each function returns clean, typed data that other modules can consume.
"""

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


# Ticker map for the assets Aurum tracks.
TICKERS = {
    "DXY": "DX-Y.NYB",          # US Dollar Index futures
    "EURUSD": "EURUSD=X",       # Spot FX
    "GBPUSD": "GBPUSD=X",       # Spot FX
    "USDJPY": "USDJPY=X",       # Spot FX
    "AUDUSD": "AUDUSD=X",       # Spot FX
    "GOLD": "GC=F",             # COMEX gold futures (≈ spot + 0.5–1%)
    "SILVER": "SI=F",           # COMEX silver futures
    "WTI": "CL=F",              # NYMEX crude oil futures
    "BTC": "BTC-USD",           # Crypto spot
    "ETH": "ETH-USD",           # Crypto spot
    "US10Y": "^TNX",            # US 10Y Treasury yield (spot)
    "VIX": "^VIX",              # CBOE volatility index (spot)
}



# RSS feeds for news aggregation.
NEWS_FEEDS = {
    "ForexLive":        "https://www.forexlive.com/feed/news",
    "Investing.com":    "https://www.investing.com/rss/news_1.rss",
    "Federal Reserve":  "https://www.federalreserve.gov/feeds/press_all.xml",
    "Yahoo Finance":    "https://finance.yahoo.com/news/rssindex",
    "MarketWatch":      "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}


def fetch_prices(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV history for a single Aurum asset."""
    if symbol not in TICKERS:
        raise ValueError(f"Unknown symbol '{symbol}'. Known: {list(TICKERS)}")

    ticker = TICKERS[symbol]
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise RuntimeError(f"No data returned for {symbol} ({ticker}).")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns=str.lower)
    df = df[["open", "high", "low", "close", "volume"]].copy()

    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    df.index.name = "timestamp"
    df.attrs["symbol"] = symbol
    df.attrs["fetched_at"] = datetime.now(timezone.utc).isoformat()

    return df


def fetch_news(limit_per_feed: int = 5) -> list[dict]:
    """Fetch latest headlines from configured RSS feeds."""
    import feedparser

    items: list[dict] = []

    for source, url in NEWS_FEEDS.items():
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:limit_per_feed]:
                items.append({
                    "source": source,
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "published_parsed": entry.get("published_parsed"),
                })
        except Exception as e:
            print(f"[news] {source} failed: {e}")

    def sort_key(item):
        p = item.get("published_parsed")
        return datetime(*p[:6]) if p else datetime.min

    items.sort(key=sort_key, reverse=True)
    return items


def fetch_economic_calendar(
    currency: str | None = None,
    min_importance: str = "medium",
) -> list[dict]:
    """Fetch upcoming economic events via biquote."""
    from biquote import Biquote

    client = Biquote()
    raw = client.calendar_upcoming()

    rank = {"low": 0, "medium": 1, "high": 2}
    threshold = rank.get(min_importance, 1)

    events = []
    for ev in raw:
        imp = (ev.get("importance") or "low").lower()
        if rank.get(imp, 0) < threshold:
            continue
        if currency and ev.get("currency") != currency:
            continue
        events.append({
            "time": ev.get("time"),
            "country": ev.get("countryCode"),
            "currency": ev.get("currency"),
            "event": ev.get("name"),
            "importance": imp,
            "actual": ev.get("actual"),
            "forecast": ev.get("forecast"),
            "previous": ev.get("previous"),
            "source": ev.get("source"),
        })

    events.sort(key=lambda e: e["time"] or "")
    return events


if __name__ == "__main__":
    print("=== Prices ===")
    for sym in ["DXY", "EURUSD", "GOLD", "BTC"]:
        try:
            data = fetch_prices(sym, period="6mo")
            last_close = float(data["close"].iloc[-1])
            print(f"{sym:8s} | rows: {len(data):4d} | last close: {last_close:.4f}")
        except Exception as e:
            print(f"{sym:8s} | ERROR: {e}")

    print()
    print("=== News ===")
    for item in fetch_news(limit_per_feed=2)[:8]:
        print(f"[{item['source']:18s}] {item['title'][:70]}")

    print()
    print("=== Calendar (medium+ importance) ===")
    events = fetch_economic_calendar(min_importance="medium")
    if not events:
        print("(no events)")
    else:
        for ev in events[:10]:
            print(f"[{ev['country']:4s} {ev['currency']:4s}] {ev['time']:20s} | {ev['importance']:6s} | {ev['event'][:55]}")