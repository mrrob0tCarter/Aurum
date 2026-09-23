"""Aurum — data fetching layer.

Fetches raw market data and news from external sources.
Each function returns clean, typed data that other modules can consume.
"""

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


# Ticker map for the assets Aurum tracks.
# yfinance symbols, verified as of the current yfinance release.
TICKERS = {
    "DXY": "DX-Y.NYB",       # US Dollar Index
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "GOLD": "GC=F",          # Gold futures
    "SILVER": "SI=F",        # Silver futures
    "WTI": "CL=F",           # Crude Oil WTI futures
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "US10Y": "^TNX",         # US 10Y Treasury yield
    "VIX": "^VIX",           # Volatility index
}


def fetch_prices(symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV history for a single Aurum asset.

    Args:
        symbol: One of the keys in TICKERS (e.g. "DXY", "GOLD").
        period: yfinance period string ("1mo", "6mo", "1y", "2y", "5y", "max").
        interval: yfinance interval ("1d", "1h", "1wk").

    Returns:
        DataFrame indexed by timestamp (UTC), with columns:
        open, high, low, close, volume
    """
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

    # yfinance returns a MultiIndex when there's one ticker but newer versions
    # sometimes flatten it. Normalize either way.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns=str.lower)
    df = df[["open", "high", "low", "close", "volume"]].copy()

    # Force UTC timezone-aware index.
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    else:
        df.index = df.index.tz_convert("UTC")

    df.index.name = "timestamp"
    df.attrs["symbol"] = symbol
    df.attrs["fetched_at"] = datetime.now(timezone.utc).isoformat()

    return df


if __name__ == "__main__":
    # Quick manual test when running this file directly.
    for sym in ["DXY", "EURUSD", "GOLD", "BTC"]:
        try:
            data = fetch_prices(sym, period="6mo")
            last_close = float(data["close"].iloc[-1])
            print(f"{sym:8s} | rows: {len(data):4d} | last close: {last_close:.4f}")
        except Exception as e:
            print(f"{sym:8s} | ERROR: {e}")