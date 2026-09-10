from datetime import datetime, timedelta
import re


def parse_availability(text: str):
    if not text:
        return datetime.max

    now = datetime.now()
    text = text.strip()

    # 1. Today, 5:30 pm
    if text.lower().startswith("today"):
        try:
            time_part = text.split(",", 1)[1].strip()
            t = datetime.strptime(time_part, "%I:%M %p")
            return datetime(now.year, now.month, now.day, t.hour, t.minute)
        except Exception:
            return now

    # 2. Tomorrow, 5:30 pm
    if text.lower().startswith("tomorrow"):
        try:
            time_part = text.split(",", 1)[1].strip()
            t = datetime.strptime(time_part, "%I:%M %p")
            return datetime(now.year, now.month, now.day, t.hour, t.minute) + timedelta(days=1)
        except Exception:
            return now + timedelta(days=1)

    # 3. in X days
    match = re.match(r"in (\d+) days?", text, re.IGNORECASE)
    if match:
        return now + timedelta(days=int(match.group(1)))

    # 4. Weekday: Mon, 12:15 pm
    weekdays = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
    try:
        parts = [p.strip() for p in text.split(",")]
        day_str = parts[0].lower()
        if day_str in weekdays:
            time_part = parts[1] if len(parts) > 1 else "12:00 pm"
            t = datetime.strptime(time_part, "%I:%M %p")
            today_weekday = now.weekday()
            target_weekday = weekdays[day_str]
            days_ahead = (target_weekday - today_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7
            return datetime(now.year, now.month, now.day, t.hour, t.minute) + timedelta(days=days_ahead)
    except Exception:
        pass

    # 5. Day Month: 25 Sep, 8:30 am or 25 Sep
    try:
        parts = [p.strip() for p in text.split(",")]
        date_str = parts[0]
        time_str = parts[1] if len(parts) > 1 else "09:00 am"
        dt = datetime.strptime(f"{date_str} {now.year} {time_str}", "%d %b %Y %I:%M %p")
        if dt < now - timedelta(days=30):  # next year wrap-around
            dt = datetime.strptime(f"{date_str} {now.year + 1} {time_str}", "%d %b %Y %I:%M %p")
        return dt
    except Exception:
        pass

    return datetime.max
