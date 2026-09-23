"""Aurum — AI Logic Matrix.

Combines technical indicators, fundamental sentiment, and inter-market
signals into a single BUY / SELL / NO TRADE decision with rationale.

Design: rule-based, deterministic, no LLM. Default answer is NO TRADE.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum

import pandas as pd

from core import indicators, sentiment


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO TRADE"


# --- Tuning constants (locked after research) -----------------------------
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
EVENT_WINDOW_MINUTES = 30
ATR_PERCENTILE_BLOCK = 90
CORR_BREAK_THRESHOLD = -0.3
MIN_CONVICTION = 0.30


# --- Safety gates ---------------------------------------------------------

def check_events(calendar: list[dict], now: datetime | None = None) -> str | None:
    """Veto if a high-impact USD event is within ±30 min."""
    now = now or datetime.now(timezone.utc)
    window = timedelta(minutes=EVENT_WINDOW_MINUTES)

    for ev in calendar:
        if ev.get("currency") != "USD":
            continue
        if ev.get("importance") != "high":
            continue

        time_str = ev.get("time")
        if not time_str:
            continue

        try:
            ev_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        delta = abs(now - ev_time)
        if delta <= window:
            return (
                f"High-impact USD event '{ev.get('event')}' at "
                f"{ev_time.strftime('%H:%M UTC')} is within ±"
                f"{EVENT_WINDOW_MINUTES} min."
            )

    return None


def check_volatility(df: pd.DataFrame) -> str | None:
    """Veto if current ATR is in the extreme percentile."""
    atr = df["atr_14"].dropna()
    if len(atr) < 30:
        return None

    recent = atr.iloc[-1]
    percentile = (atr < recent).mean() * 100

    if percentile > ATR_PERCENTILE_BLOCK:
        return (
            f"ATR at {percentile:.0f}th percentile — volatility extreme. "
            "Wait for conditions to normalize."
        )
    return None


# --- Technical score ------------------------------------------------------

def technical_score(snap: dict) -> tuple[int, list[str]]:
    """Score technical setup from -4 to +4. Returns (score, notes)."""
    score = 0
    notes: list[str] = []

    close = snap.get("close")
    rsi = snap.get("rsi_14")
    macd = snap.get("macd")
    macd_sig = snap.get("macd_signal")
    sma200 = snap.get("sma_200")
    ema21 = snap.get("ema_21")

    if rsi is not None:
        if rsi < RSI_OVERSOLD:
            score += 1
            notes.append(f"RSI {rsi:.0f} oversold")
        elif rsi > RSI_OVERBOUGHT:
            score -= 1
            notes.append(f"RSI {rsi:.0f} overbought")

    if macd is not None and macd_sig is not None:
        if macd > macd_sig:
            score += 1
            notes.append("MACD above signal")
        else:
            score -= 1
            notes.append("MACD below signal")

    if close is not None and sma200 is not None:
        if close > sma200:
            score += 1
            notes.append("Above 200-SMA")
        else:
            score -= 1
            notes.append("Below 200-SMA")

    if close is not None and ema21 is not None:
        if close > ema21:
            score += 1
            notes.append("Above 21-EMA")
        else:
            score -= 1
            notes.append("Below 21-EMA")

    return score, notes


# --- Inter-market check ---------------------------------------------------

def check_dxy_gold_correlation(
    dxy_df: pd.DataFrame,
    gold_df: pd.DataFrame,
    window: int = 30,
) -> tuple[float | None, bool]:
    """Rolling 30d correlation between DXY and Gold returns."""
    if dxy_df.empty or gold_df.empty:
        return None, True

    dxy_ret = dxy_df["close"].pct_change().dropna()
    gold_ret = gold_df["close"].pct_change().dropna()

    joined = pd.concat([dxy_ret, gold_ret], axis=1, join="inner").dropna()
    joined.columns = ["dxy", "gold"]

    if len(joined) < window:
        return None, True

    corr_series = joined["dxy"].rolling(window).corr(joined["gold"])
    clean = corr_series.dropna()
    if clean.empty:
        return None, True

    latest = float(clean.iloc[-1])
    intact = latest <= CORR_BREAK_THRESHOLD
    return latest, intact


# --- Main decision --------------------------------------------------------

def decide(
    symbol: str,
    prices_df: pd.DataFrame,
    news: list[dict],
    calendar: list[dict],
    dxy_df: pd.DataFrame | None = None,
    gold_df: pd.DataFrame | None = None,
) -> dict:
    """Combine all signals into one final call."""
    with_ind = indicators.add_indicators(prices_df)
    snap = indicators.latest_snapshot(with_ind)

    # Step 1: safety gates
    veto = check_events(calendar)
    if not veto:
        veto = check_volatility(with_ind)

    if veto:
        return {
            "symbol": symbol,
            "signal": Signal.NO_TRADE.value,
            "confidence": 0.0,
            "rationale": veto,
            "technical_score": 0,
            "fundamental_score": 0.0,
            "notes": ["Blocked by safety gate"],
            "veto_reason": veto,
        }

    # Step 2: technical score
    t_score, t_notes = technical_score(snap)

    # Step 3: fundamental sentiment
    senti = sentiment.score_news(news)
    f_score = senti["sentiment"]

    # Step 4: inter-market check
    corr = None
    corr_intact = True
    if dxy_df is not None and gold_df is not None:
        corr, corr_intact = check_dxy_gold_correlation(dxy_df, gold_df)

    # Step 5: combine
    total = (t_score / 4.0) * 0.6 + f_score * 0.4

    if abs(total) < MIN_CONVICTION:
        rationale = (
            "Technical and fundamental signals conflict or are too weak. "
            f"T-score {t_score:+d}, sentiment {f_score:+.2f}."
        )
        return {
            "symbol": symbol,
            "signal": Signal.NO_TRADE.value,
            "confidence": round(abs(total), 3),
            "rationale": rationale,
            "technical_score": t_score,
            "fundamental_score": f_score,
            "notes": t_notes,
            "veto_reason": None,
        }

    if symbol in {"GOLD", "SILVER", "BTC", "ETH"} and not corr_intact and corr is not None:
        rationale = (
            f"DXY/Gold correlation is {corr:+.2f} — inverse relationship broken. "
            "Directional bets are unreliable in this regime."
        )
        return {
            "symbol": symbol,
            "signal": Signal.NO_TRADE.value,
            "confidence": 0.0,
            "rationale": rationale,
            "technical_score": t_score,
            "fundamental_score": f_score,
            "notes": t_notes + [f"DXY/Gold corr {corr:+.2f}"],
            "veto_reason": "correlation broken",
        }

    if total > 0:
        sig = Signal.BUY
        direction = "bullish"
    else:
        sig = Signal.SELL
        direction = "bearish"

    top_notes = ", ".join(t_notes[:2]) if t_notes else "no strong indicators"
    rationale = (
        f"{len(t_notes)} technical signals {direction} ({top_notes}), "
        f"sentiment {f_score:+.2f}. Combined score {total:+.2f}."
    )

    return {
        "symbol": symbol,
        "signal": sig.value,
        "confidence": round(min(abs(total), 1.0), 3),
        "rationale": rationale,
        "technical_score": t_score,
        "fundamental_score": f_score,
        "notes": t_notes,
        "veto_reason": None,
    }


# --- Manual test ----------------------------------------------------------

if __name__ == "__main__":
    from core.data import fetch_prices, fetch_news, fetch_economic_calendar

    print("Fetching data (may take ~15 seconds)...\n")
    news = fetch_news(limit_per_feed=3)
    calendar = fetch_economic_calendar(min_importance="high")
    dxy_df = fetch_prices("DXY", period="1y")
    gold_df = fetch_prices("GOLD", period="1y")

    for sym in ["DXY", "EURUSD", "GOLD", "BTC"]:
        prices = fetch_prices(sym, period="1y")
        result = decide(
            sym,
            prices,
            news,
            calendar,
            dxy_df=dxy_df,
            gold_df=gold_df,
        )
        print(f"--- {sym} ---")
        print(f"  Signal:      {result['signal']}")
        print(f"  Confidence:  {result['confidence']}")
        print(f"  Tech score:  {result['technical_score']:+d}")
        print(f"  Fund score:  {result['fundamental_score']:+.2f}")
        print(f"  Rationale:   {result['rationale']}")
        print()