from datetime import datetime

from dateutil.relativedelta import relativedelta, MO

DEFAULT_DATE = datetime(year=2022, month=1, day=1)


def round_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def adjust_date(date_str: object) -> datetime:
    """If the date is not empty string, parse it.
    Otherwise, assign `DEFAULT_DATE`.
    """
    if not isinstance(date_str, str) or not date_str.strip():
        return DEFAULT_DATE
    return round_to_minute(datetime.fromisoformat(date_str.split("T")[0]))


def get_last_monday() -> datetime:
    today = datetime.now()
    last_monday = today + relativedelta(weekday=MO(-1))
    return last_monday.replace(hour=8, minute=0, second=0, microsecond=0)
