from datetime import datetime, timezone

from sqlalchemy import DateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def TimestampMixin():
    return DateTime(timezone=True)
