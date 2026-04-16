from datetime import datetime
from django.utils import timezone

def ensure_datetime(value):
    """
    Normalize timestamp values into timezone-aware datetimes.
    Accepts ISO8601 strings or datetime objects.
    Ensures everything is stored as UTC aware datetime.
    """
    if isinstance(value, str):
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    if isinstance(value, datetime):
        # Make naive datetimes timezone-aware in UTC
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone=timezone.utc)
        return value

    return value  