"""Aurum — continuous price streamer.

Runs forever. Polls biquote every N seconds for live quotes.
Writes ticks to SQLite. Skips stale/closed markets.

Run:  python -m services.price_streamer
Stop: Ctrl+C
"""

import signal
import time
from datetime import datetime, timezone

from biquote import Biquote, BiquoteError

from core import db


POLL_INTERVAL_SECONDS = 5
LOG_PREFIX = "[price_streamer]"


# Symbols to poll on biquote. Use short keys matching our TICKERS convention.
STREAM_SYMBOLS = [
    "DXY",
    "XAUUSD",
    "BTCUSD",
    "ETHUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
]


_running = True


def _handle_sigint(sig, frame):
    global _running
    print(f"\n{LOG_PREFIX} Shutdown requested. Finishing current cycle...")
    _running = False


def _log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{ts} {LOG_PREFIX} {msg}", flush=True)


def poll_once(client: Biquote) -> int:
    """Poll all symbols once. Returns number of ticks inserted."""
    inserted = 0

    for sym in STREAM_SYMBOLS:
        try:
            t = client.tick(sym, allow_stale=False)
        except BiquoteError as e:
            # Unknown symbol, or quote older than 5 minutes
            _log(f"SKIP {sym}: {e}")
            continue
        except Exception as e:
            _log(f"ERROR {sym}: {e}")
            continue

        # Skip if market is closed
        if t.get("marketState") != "open":
            continue

        ts = t.get("timestamp") or t.get("lastQuoteAt")
        if not ts:
            continue

        db.insert_tick(
            symbol=sym,
            timestamp=ts,
            price=float(t.get("mid", 0)),
            bid=float(t.get("bid", 0)),
            ask=float(t.get("ask", 0)),
        )
        inserted += 1

    return inserted


def run_forever() -> None:
    signal.signal(signal.SIGINT, _handle_sigint)

    db.init_db()
    client = Biquote()

    _log(f"Starting. Polling {len(STREAM_SYMBOLS)} symbols "
         f"every {POLL_INTERVAL_SECONDS}s.")

    cycle = 0
    while _running:
        cycle += 1
        start = time.time()
        try:
            n = poll_once(client)
            elapsed = time.time() - start
            _log(f"Cycle {cycle} done in {elapsed:.2f}s. Ticks: {n}")
        except Exception as e:
            _log(f"Cycle {cycle} failed: {e}")

        for _ in range(POLL_INTERVAL_SECONDS):
            if not _running:
                break
            time.sleep(1)

    _log("Stopped cleanly.")


if __name__ == "__main__":
    run_forever()
    