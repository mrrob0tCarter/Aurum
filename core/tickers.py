"""Aurum — ticker discovery helpers.

Optional utilities for looking up ticker symbols across exchanges.
Not required for Aurum's core operation — used only by UI search features
later in the project.

Sources:
    - CoinGecko: free, no API key needed for the public coin list.
    - adanos-software/free-ticker-database: GitHub-hosted JSON/CSV/SQLite
      with 60k+ tickers across 80+ exchanges.
"""

import json
from pathlib import Path

import pandas as pd
import requests


# --- Crypto tickers (CoinGecko, no key required) -------------------------

COINGECKO_COINS_URL = "https://api.coingecko.com/api/v3/coins/list"


def get_free_crypto_tickers() -> pd.DataFrame:
    """Fetch the full list of crypto coins CoinGecko tracks.

    Returns a DataFrame with columns: id, symbol, name.
    ~15,000 coins, no API key needed, rate limit ~30 calls/min.
    """
    response = requests.get(COINGECKO_COINS_URL, timeout=15)
    response.raise_for_status()
    data = response.json()

    df = pd.DataFrame(data)
    # Keep only the useful columns and normalize case.
    df = df[["id", "symbol", "name"]].copy()
    df["symbol"] = df["symbol"].str.upper()
    df = df.sort_values("symbol").reset_index(drop=True)
    return df


# --- Global ticker database (adanos-software, no key required) -----------

# Download the repo once and store it here.
# Repo: https://github.com/adanos-software/free-ticker-database
# Expected files: tickers.json / tickers.csv / tickers.db
TICKER_DB_DIR = Path("data/cache/tickers")
TICKER_DB_JSON = TICKER_DB_DIR / "tickers.json"


def load_global_ticker_db() -> pd.DataFrame:
    """Load the local free-ticker-database file if present.

    You must download the JSON file once from the GitHub repo and place it at
    data/cache/tickers/tickers.json. Returns an empty DataFrame if the file
    doesn't exist yet, so callers don't need to guard against it.
    """
    if not TICKER_DB_JSON.exists():
        return pd.DataFrame(columns=["symbol", "name", "exchange", "type"])

    with open(TICKER_DB_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.DataFrame(raw)
    # Normalize whatever columns exist — the repo's schema may vary.
    df.columns = [c.lower() for c in df.columns]
    return df


# --- Aurum's own macro ticker map ----------------------------------------

def get_macro_ticker_map() -> dict[str, str]:
    """Aurum's canonical macro symbols — mirrors core.data.TICKERS."""
    return {
        "DXY": "DX-Y.NYB",       # US Dollar Index futures
        "EURUSD": "EURUSD=X",    # Spot FX
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
        "AUDUSD": "AUDUSD=X",
        "GOLD": "GC=F",          # COMEX gold futures
        "SILVER": "SI=F",
        "WTI": "CL=F",
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "US10Y": "^TNX",         # 10Y Treasury yield
        "VIX": "^VIX",
    }


if __name__ == "__main__":
    print("=== Crypto tickers (CoinGecko) ===")
    try:
        crypto = get_free_crypto_tickers()
        print(f"Loaded {len(crypto)} crypto tickers.")
        print(crypto.head(5).to_string(index=False))
    except Exception as e:
        print(f"Failed: {e}")

    print()
    print("=== Global ticker DB (local file) ===")
    global_db = load_global_ticker_db()
    if global_db.empty:
        print("Not present. Download from:")
        print("  https://github.com/adanos-software/free-ticker-database")
        print(f"  Save as: {TICKER_DB_JSON}")
    else:
        print(f"Loaded {len(global_db)} tickers.")

    print()
    print("=== Aurum macro map ===")
    for sym, yf_ticker in get_macro_ticker_map().items():
        print(f"  {sym:8s} -> {yf_ticker}")