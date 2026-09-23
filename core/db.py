"""Aurum — SQLite persistence layer.

Stores news events, price ticks, and signals for historical analysis
and cross-referencing.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/aurum.db")


def get_conn() -> sqlite3.Connection:
    """Return a connection with row factory for dict-like access."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            title TEXT NOT NULL,
            link TEXT,
            published_at TEXT,
            detected_at TEXT NOT NULL,
            sentiment REAL,
            processed INTEGER DEFAULT 0,
            UNIQUE(title, link)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS price_ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            price REAL NOT NULL,
            bid REAL,
            ask REAL,
            UNIQUE(symbol, timestamp)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal TEXT NOT NULL,
            confidence REAL,
            rationale TEXT,
            technical_score INTEGER,
            fundamental_score REAL,
            session TEXT,
            news_event_id INTEGER,
            generated_at TEXT NOT NULL,
            FOREIGN KEY (news_event_id) REFERENCES news_events(id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time
        ON price_ticks(symbol, timestamp)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_signals_time
        ON signals(generated_at)
    """)

    conn.commit()
    conn.close()


def insert_news(source: str, title: str, link: str,
                published_at: str | None, sentiment: float) -> int | None:
    """Insert a news item. Returns row id if new, None if duplicate."""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    try:
        cur.execute("""
            INSERT INTO news_events
            (source, title, link, published_at, detected_at, sentiment)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source, title, link, published_at, now, sentiment))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def insert_tick(symbol: str, timestamp: str, price: float,
                bid: float | None = None, ask: float | None = None) -> None:
    """Insert a price tick. Silently ignores duplicates."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT OR IGNORE INTO price_ticks
            (symbol, timestamp, price, bid, ask)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, timestamp, price, bid, ask))
        conn.commit()
    finally:
        conn.close()


def insert_signal(symbol: str, signal: str, confidence: float,
                  rationale: str, technical_score: int,
                  fundamental_score: float, session: str,
                  news_event_id: int | None = None) -> int:
    """Insert a generated signal."""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    cur.execute("""
        INSERT INTO signals
        (symbol, signal, confidence, rationale, technical_score,
         fundamental_score, session, news_event_id, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, signal, confidence, rationale, technical_score,
          fundamental_score, session, news_event_id, now))
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_recent_news(limit: int = 50) -> list[dict]:
    """Return the most recent news events."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM news_events
        ORDER BY detected_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_recent_signals(limit: int = 50) -> list[dict]:
    """Return the most recent generated signals."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM signals
        ORDER BY generated_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")

    # Smoke test
    nid = insert_news(
        source="test",
        title="Test headline for DB check",
        link="https://example.com/test",
        published_at=None,
        sentiment=0.25,
    )
    print(f"Inserted news id: {nid}")

    insert_tick("DXY", datetime.now(timezone.utc).isoformat(), 100.5)
    print("Inserted tick")

    print(f"Recent news count: {len(get_recent_news())}")