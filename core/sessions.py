"""Aurum — trading session awareness.

Determines which forex session(s) are currently active.
Signals during high-liquidity sessions carry more weight.

All session definitions are in UTC. Display timezone is separate.
"""

from datetime import datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo


class Session(str, Enum):
    SYDNEY = "Sydney"
    TOKYO = "Tokyo"
    LONDON = "London"
    NEW_YORK = "New York"
    OVERLAP_LDN_NY = "London-New York Overlap"
    CLOSED = "Closed (Rollover)"


# All times in UTC. Approximate standard hours.
SESSION_HOURS = {
    Session.SYDNEY:    (21, 6),
    Session.TOKYO:     (0, 9),
    Session.LONDON:    (7, 16),
    Session.NEW_YORK:  (12, 21),
}


def current_session(now: datetime | None = None) -> Session:
    """Return the currently active session (or overlap/closed)."""
    now = now or datetime.now(timezone.utc)
    h = now.hour

    # Weekend closed
    weekday = now.weekday()  # Mon=0, Sun=6
    if weekday == 5:
        return Session.CLOSED
    if weekday == 6 and h < 21:
        return Session.CLOSED
    if weekday == 4 and h >= 21:
        return Session.CLOSED

    # Rollover: 21:00–22:00 UTC daily
    if h == 21:
        return Session.CLOSED

    # London–NY overlap: 12:00–16:00 UTC — highest USD liquidity
    if 12 <= h < 16:
        return Session.OVERLAP_LDN_NY

    for sess, (start, end) in SESSION_HOURS.items():
        if start < end:
            if start <= h < end:
                return sess
        else:
            if h >= start or h < end:
                return sess

    return Session.CLOSED


def session_weight(session: Session, symbol: str) -> float:
    """Return a confidence multiplier based on session and asset."""
    if session == Session.CLOSED:
        return 0.0
    if session == Session.OVERLAP_LDN_NY:
        return 1.0
    if session in (Session.LONDON, Session.NEW_YORK):
        return 0.95
    if session in (Session.TOKYO, Session.SYDNEY):
        if symbol in {"USDJPY", "AUDUSD"}:
            return 0.85
        return 0.55
    return 0.7


# --- Display timezone support --------------------------------------------

def get_local_tz() -> ZoneInfo:
    """Return the system's local timezone. Falls back to UTC."""
    try:
        import tzlocal
        return ZoneInfo(str(tzlocal.get_localzone()))
    except Exception:
        return ZoneInfo("UTC")


def to_local(dt_utc: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Convert a UTC datetime to a target timezone."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    tz = tz or get_local_tz()
    return dt_utc.astimezone(tz)


def session_in_local_time(
    session: Session, tz: ZoneInfo | None = None
) -> tuple[str, str]:
    """Return (start_local, end_local) as HH:MM strings."""
    if session not in SESSION_HOURS:
        return ("—", "—")

    start_h, end_h = SESSION_HOURS[session]
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    start_utc = today.replace(hour=start_h)
    end_utc = today.replace(hour=end_h)
    if end_h <= start_h:
        from datetime import timedelta
        end_utc = end_utc + timedelta(days=1)

    tz = tz or get_local_tz()
    return (
        start_utc.astimezone(tz).strftime("%H:%M"),
        end_utc.astimezone(tz).strftime("%H:%M"),
    )


def all_sessions_local(tz: ZoneInfo | None = None) -> list[dict]:
    """Return all sessions with their local start/end times."""
    tz = tz or get_local_tz()
    out = []
    for sess in [Session.SYDNEY, Session.TOKYO, Session.LONDON, Session.NEW_YORK]:
        start, end = session_in_local_time(sess, tz)
        out.append({
            "session": sess.value,
            "start_local": start,
            "end_local": end,
            "timezone": str(tz),
        })
    return out


if __name__ == "__main__":
    tz = get_local_tz()
    print(f"Your local timezone: {tz}")
    print()

    sess = current_session()
    print(f"Current session:  {sess.value}")
    print(f"DXY weight:       {session_weight(sess, 'DXY'):.2f}")
    print(f"EURUSD weight:    {session_weight(sess, 'EURUSD'):.2f}")
    print(f"USDJPY weight:    {session_weight(sess, 'USDJPY'):.2f}")
    print()

    print("All sessions in your local time:")
    for s in all_sessions_local(tz):
        print(f"  {s['session']:28s}  {s['start_local']} – {s['end_local']}")