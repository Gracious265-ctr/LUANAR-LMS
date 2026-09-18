from datetime import date, timedelta


def calculate_working_days(start_date: date, end_date: date) -> int:
    """
    TEMPORARY STUB (Unit 13). Excludes weekends only.
    TODO(unit-5): delegate to the real calendar/rule service once available,
    which must also exclude configured public holidays.
    """
    if start_date is None or end_date is None or end_date < start_date:
        return 0
    days = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Mon-Fri
            days += 1
        current += timedelta(days=1)
    return days
