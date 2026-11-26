"""Centralized Indian Standard Time (Asia/Kolkata, UTC+05:30) datetime helpers.

Design contract:
- Database columns remain TIMESTAMPTZ stored consistently in UTC.
- Application code always constructs timezone-aware datetimes (never naive).
- Display / export helpers convert stored UTC instants to Asia/Kolkata without double-shifting.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

IST_TIMEZONE = "Asia/Kolkata"
IST = ZoneInfo(IST_TIMEZONE)
UTC = timezone.utc


def get_ist_now() -> datetime:
    """Return the current system time as a timezone-aware Asia/Kolkata datetime."""
    return datetime.now(IST)


def get_utc_now() -> datetime:
    """Return the current system time as a timezone-aware UTC datetime for DB storage."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware in UTC without mutating the underlying instant.

    SQLite strips tzinfo when returning DateTime(timezone=True) rows (which are stored in UTC),
    whereas PostgreSQL TIMESTAMPTZ returns aware datetimes.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_ist(dt: datetime) -> datetime:
    """Convert any datetime (naive treated as stored UTC, or any aware offset) to Asia/Kolkata."""
    return ensure_utc(dt).astimezone(IST)


def to_ist_iso(dt: datetime | None) -> str | None:
    """Serialize a datetime to an ISO 8601 string in Asia/Kolkata (+05:30)."""
    if dt is None:
        return None
    return to_ist(dt).isoformat()


def format_ist_display(dt: datetime | None, *, long_month: bool = False) -> str:
    """Format a datetime for human-readable UI and PDF/TXT exports in IST."""
    if dt is None:
        return "Unknown time"
    ist_dt = to_ist(dt)
    fmt = "%d %B %Y, %I:%M %p IST" if long_month else "%d %b %Y, %I:%M %p IST"
    return ist_dt.strftime(fmt)


def get_ist_today() -> date:
    """Return the current calendar date in Asia/Kolkata."""
    return get_ist_now().date()
