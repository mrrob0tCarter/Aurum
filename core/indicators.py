"""Aurum — technical indicators.

Computes the standard technical analysis toolkit on OHLCV DataFrames
produced by core.data.fetch_prices().
"""

import pandas as pd
import pandas_ta_classic as ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with technical indicators appended."""
    out = df.copy()

    out["sma_50"] = ta.sma(out["close"], length=50)
    out["sma_200"] = ta.sma(out["close"], length=200)
    out["ema_21"] = ta.ema(out["close"], length=21)

    out["rsi_14"] = ta.rsi(out["close"], length=14)

    macd = ta.macd(out["close"], fast=12, slow=26, signal=9)
    if macd is not None:
        out["macd"] = macd["MACD_12_26_9"]
        out["macd_signal"] = macd["MACDs_12_26_9"]
        out["macd_hist"] = macd["MACDh_12_26_9"]

    out["atr_14"] = ta.atr(out["high"], out["low"], out["close"], length=14)

    out["resistance"] = out["high"].rolling(180, min_periods=20).max()
    out["support"] = out["low"].rolling(180, min_periods=20).min()

    return out


def latest_snapshot(df: pd.DataFrame) -> dict:
    """Return a dict of the most recent indicator values."""
    if df.empty:
        return {}

    last = df.iloc[-1]

    def safe(key):
        v = last.get(key)
        return float(v) if v is not None and not pd.isna(v) else None

    return {
        "close": safe("close"),
        "sma_50": safe("sma_50"),
        "sma_200": safe("sma_200"),
        "ema_21": safe("ema_21"),
        "rsi_14": safe("rsi_14"),
        "macd": safe("macd"),
        "macd_signal": safe("macd_signal"),
        "macd_hist": safe("macd_hist"),
        "atr_14": safe("atr_14"),
        "resistance": safe("resistance"),
        "support": safe("support"),
    }


if __name__ == "__main__":
    from core.data import fetch_prices

    print("=== Indicator snapshot: DXY ===")
    df = fetch_prices("DXY", period="1y")
    df = add_indicators(df)
    snap = latest_snapshot(df)

    for key, val in snap.items():
        if val is None:
            print(f"  {key:12s} = (n/a)")
        else:
            print(f"  {key:12s} = {val:>12.4f}")