from datetime import datetime


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_str(value, default=""):
    return str(value).strip() if value is not None else default


def try_parse_date(date_str):
    date_str = safe_str(date_str)
    if not date_str:
        return None
    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def try_parse_time(time_str):
    time_str = safe_str(time_str)
    if not time_str:
        return "00:00:00"
    if time_str.count(':') == 1:
        time_str = time_str + ":00"
    formats = ["%H:%M:%S", "%H:%M", "%H:%M:%S.%f", "%H时%M分%S秒", "%H时%M分"]
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    return "00:00:00"


def is_hourly(time_str):
    t = try_parse_time(time_str)
    return t.endswith(":00:00")
