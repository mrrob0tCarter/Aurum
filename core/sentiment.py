"""Aurum — news sentiment scoring.

Rule-based keyword sentiment for financial headlines.
Inspired by the Loughran-McDonald lexicon, scoped to USD/EUR/Gold macro news.

Deterministic. No LLM. Same headline always scores the same.
"""

import re
from datetime import datetime, timezone


# --- Sentiment lexicons ---------------------------------------------------

USD_POSITIVE = {
    "hawkish", "hike", "hikes", "raised", "raise", "tightening",
    "strong", "stronger", "beat", "beats", "robust", "accelerate",
    "resilient", "upbeat", "surge", "surges", "rally", "rallies",
    "outperform", "optimism", "gains", "jump", "jumps",
}

USD_NEGATIVE = {
    "dovish", "cut", "cuts", "lowered", "lower", "easing",
    "weak", "weaker", "miss", "misses", "slow", "slows",
    "recession", "crisis", "contraction", "slump", "slumps",
    "drop", "drops", "plunge", "plunges", "selloff", "sell-off",
    "pessimism", "fears", "worry", "worries", "uncertainty",
    "downgrade", "downgrades", "layoffs", "default",
}

INTENSIFIERS = {"sharp", "sharply", "major", "significantly", "massive"}
NEGATORS = {"no", "not", "without", "fails", "fail", "denies", "denied"}


# --- Relevance filter -----------------------------------------------------

IRRELEVANT_MARKERS = {
    "stock", "stocks", "shares", "earnings", "ceo", "ipo",
    "dividend", "analyst", "rating", "upgrade",
    "retire", "retirement", "401k", "mortgage", "alzheimer",
    "family", "husband", "wife", "mother", "father",
    "nfl", "nba", "movie", "celebrity",
}

RELEVANCE_MARKERS = {
    "dollar", "usd", "fed", "fomc", "federal", "treasury",
    "yield", "yields", "inflation", "cpi", "ppi", "nfp",
    "payrolls", "unemployment", "gdp", "recession",
    "hawkish", "dovish", "rate", "rates", "hike", "cut",
    "eur", "euro", "gbp", "pound", "jpy", "yen",
    "forex", "fx", "currency", "currencies",
    "gold", "oil", "crude", "commodity", "commodities",
    "ecb", "boe", "boj", "rba", "pboc",
    "tariff", "sanctions", "geopolitical",
}


_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def is_usd_relevant(title: str) -> bool:
    """Return True if headline appears to concern USD/macro."""
    tokens = _tokens(title)
    if any(t in IRRELEVANT_MARKERS for t in tokens):
        return False
    return any(t in RELEVANCE_MARKERS for t in tokens)


def score_headline(title: str) -> float:
    """Score one headline for USD direction. Returns [-1.0, +1.0].

    Returns 0.0 if the headline is not USD/macro-relevant.
    """
    if not is_usd_relevant(title):
        return 0.0

    tokens = _tokens(title)
    pos = neg = 0
    for i, tok in enumerate(tokens):
        prev = tokens[i - 1] if i > 0 else ""
        flip = prev in NEGATORS

        if tok in USD_POSITIVE:
            if flip:
                neg += 1
            else:
                pos += 1
        elif tok in USD_NEGATIVE:
            if flip:
                pos += 1
            else:
                neg += 1

    raw = pos - neg
    if raw == 0:
        return 0.0

    if any(t in INTENSIFIERS for t in tokens):
        raw *= 1.25

    return max(-1.0, min(1.0, raw / 3.0))


def score_news(items: list[dict], hours_half_life: float = 24.0) -> dict:
    """Score a batch of news items with time decay."""
    now = datetime.now(timezone.utc)
    weighted_sum = 0.0
    weight_total = 0.0
    scored = []

    for item in items:
        s = score_headline(item.get("title", ""))
        if s == 0.0:
            continue

        p = item.get("published_parsed")
        if p:
            published = datetime(*p[:6], tzinfo=timezone.utc)
            age_hours = max(0.0, (now - published).total_seconds() / 3600.0)
        else:
            age_hours = 6.0

        weight = 0.5 ** (age_hours / hours_half_life)
        weighted_sum += s * weight
        weight_total += weight
        scored.append((item.get("title", ""), s))

    if weight_total == 0:
        return {
            "sentiment": 0.0,
            "n_items": 0,
            "top_bullish": None,
            "top_bearish": None,
        }

    sentiment = weighted_sum / weight_total
    scored.sort(key=lambda x: x[1], reverse=True)

    return {
        "sentiment": round(sentiment, 4),
        "n_items": len(scored),
        "top_bullish": scored[0] if scored[0][1] > 0 else None,
        "top_bearish": scored[-1] if scored[-1][1] < 0 else None,
    }


if __name__ == "__main__":
    from core.data import fetch_news

    print("=== Scoring recent headlines for USD ===")
    news = fetch_news(limit_per_feed=3)
    result = score_news(news)

    print(f"Overall sentiment: {result['sentiment']:+.3f} "
          f"(from {result['n_items']} scored headlines)")
    if result["top_bullish"]:
        print(f"  Most bullish: {result['top_bullish'][0][:70]}")
    if result["top_bearish"]:
        print(f"  Most bearish: {result['top_bearish'][0][:70]}")