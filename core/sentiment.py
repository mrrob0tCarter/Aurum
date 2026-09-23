"""Aurum — news sentiment scoring.

Rule-based keyword sentiment for financial headlines.
Inspired by the Loughran-McDonald lexicon, scoped to USD/EUR/Gold macro news.

This is intentionally simple and deterministic. No LLM. Same headline always
scores the same. That reproducibility matters for a decision-support tool.
"""

import re
from datetime import datetime, timezone


# --- Lexicons -------------------------------------------------------------
# Scoped per currency/asset. A word like "hawkish" is USD-positive for the
# Fed but EUR-positive for the ECB. For MVP we only build USD + gold.

USD_POSITIVE = {
    # Hawkish / growth
    "hawkish", "hike", "hikes", "raised", "raise", "tightening",
    "strong", "stronger", "beat", "beats", "robust", "accelerate",
    "resilient", "upbeat", "surge", "surges", "rally", "rallies",
    "outperform", "optimism", "gains", "jump", "jumps",
}

USD_NEGATIVE = {
    # Dovish / weakness
    "dovish", "cut", "cuts", "lowered", "lower", "easing",
    "weak", "weaker", "miss", "misses", "slow", "slows",
    "recession", "crisis", "contraction", "slump", "slumps",
    "drop", "drops", "plunge", "plunges", "selloff", "sell-off",
    "pessimism", "fears", "worry", "worries", "uncertainty",
    "downgrade", "downgrades", "layoffs", "default",
}

# Magnifier — words that intensify whatever follows/precedes.
# For MVP we just detect them and bump the magnitude slightly.
INTENSIFIERS = {"sharp", "sharply", "major", "significantly", "massive"}

# Negators flip polarity within a short window.
NEGATORS = {"no", "not", "without", "fails", "fail", "denies", "denied"}


# --- Scoring --------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


def score_headline(title: str) -> float:
    """Score a single headline for USD direction.

    Returns:
        float in [-1.0, +1.0]. Positive = USD bullish, negative = USD bearish.
    """
    tokens = _tokens(title)
    if not tokens:
        return 0.0

    pos = neg = 0
    for i, tok in enumerate(tokens):
        # Look one token back for a negator (e.g. "not strong")
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

    # Intensify if any magnifier present
    if any(t in INTENSIFIERS for t in tokens):
        raw *= 1.25

    # Squash to [-1, 1]
    return max(-1.0, min(1.0, raw / 3.0))


def score_news(items: list[dict], hours_half_life: float = 24.0) -> dict:
    """Score a batch of news items with time decay.

    Args:
        items: list of dicts from core.data.fetch_news()
        hours_half_life: hours until a headline's weight halves. 24 = one day.

    Returns:
        {
          "sentiment": float in [-1, 1],   # weighted average
          "n_items": int,
          "top_bullish": (title, score) | None,
          "top_bearish": (title, score) | None,
        }
    """
    import math

    now = datetime.now(timezone.utc)
    weighted_sum = 0.0
    weight_total = 0.0
    scored = []

    for item in items:
        s = score_headline(item.get("title", ""))
        if s == 0.0:
            continue

        # Time decay — parse published_parsed if present
        p = item.get("published_parsed")
        if p:
            published = datetime(*p[:6], tzinfo=timezone.utc)
            age_hours = max(0.0, (now - published).total_seconds() / 3600.0)
        else:
            age_hours = 6.0  # unknown → assume reasonably fresh

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