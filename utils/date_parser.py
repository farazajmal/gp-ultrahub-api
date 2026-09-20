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

    # 4. Weekday: Mon, 12:15 pm or Monday
    weekdays = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
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
        if dt < now - timedelta(days=30):
            dt = datetime.strptime(f"{date_str} {now.year + 1} {time_str}", "%d %b %Y %I:%M %p")
        return dt
    except Exception:
        pass

    return datetime.max


def parse_time_to_minutes(time_str: str):
    """Converts time string like '10:00 am', '1pm', '3:30 pm' to minutes since midnight."""
    if not time_str:
        return None
    time_str = time_str.strip().lower()
    
    # Try %I:%M %p
    try:
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except ValueError:
        pass
        
    # Try %I %p (e.g. '1pm', '10am')
    try:
        dt = datetime.strptime(time_str, "%I%p")
        return dt.hour * 60 + dt.minute
    except ValueError:
        pass

    # Try %H:%M (24hr e.g. '13:00')
    try:
        dt = datetime.strptime(time_str, "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError:
        pass

    # Regex fallback for '1pm', '10:30am', '4 pm'
    m = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$', time_str)
    if m:
        hr = int(m.group(1))
        mn = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "pm" and hr < 12:
            hr += 12
        elif ampm == "am" and hr == 12:
            hr = 0
        return hr * 60 + mn

    return None


def match_patch_to_query(patch, day_query=None, time_query=None):
    """
    Checks if an availability patch matches day_query (e.g. 'Monday', 'today')
    and/or time_query (e.g. '1pm', 'after 4pm', 'morning').
    """
    if not patch:
        return False

    now = datetime.now()
    patch_date_str = patch.get("date")  # YYYY-MM-DD
    patch_day_name = patch.get("day_name", "").lower()  # e.g. "monday"

    # 1. Day Match
    if day_query:
        day_q = day_query.strip().lower()
        if day_q == "today":
            today_str = now.strftime("%Y-%m-%d")
            if patch_date_str != today_str:
                return False
        elif day_q == "tomorrow":
            tom_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            if patch_date_str != tom_str:
                return False
        elif day_q in ["mon", "monday", "tue", "tuesday", "wed", "wednesday", "thu", "thursday", "fri", "friday", "sat", "saturday", "sun", "sunday"]:
            if not patch_day_name.startswith(day_q[:3]):
                return False
        elif patch_date_str and day_q not in patch_date_str and day_q not in patch_day_name:
            return False

    # 2. Time Match
    if time_query:
        t_q = time_query.strip().lower()
        st_mins = parse_time_to_minutes(patch.get("start_time"))
        et_mins = parse_time_to_minutes(patch.get("end_time"))

        if st_mins is not None and et_mins is not None:
            # Special expressions
            if "after" in t_q:
                # e.g. "after 4pm" -> 16:00 = 960 mins
                m = re.search(r'after\s+(.*)', t_q)
                after_target = parse_time_to_minutes(m.group(1)) if m else 960
                if after_target is not None:
                    if et_mins < after_target:
                        return False
            elif "before" in t_q:
                # e.g. "before noon" -> 12:00 = 720 mins
                m = re.search(r'before\s+(.*)', t_q)
                before_target = parse_time_to_minutes(m.group(1)) if m else 720
                if before_target is not None:
                    if st_mins > before_target:
                        return False
            elif "morning" in t_q:
                # Morning: 07:00 to 12:00 (420 to 720)
                if et_mins < 420 or st_mins > 720:
                    return False
            elif "afternoon" in t_q or "lunchtime" in t_q:
                # Afternoon: 12:00 to 17:00 (720 to 1020)
                if et_mins < 720 or st_mins > 1020:
                    return False
            elif "evening" in t_q:
                # Evening: 17:00 to 21:00 (1020 to 1260)
                if et_mins < 1020:
                    return False
            else:
                # Specific time e.g. "1pm", "10:30am"
                target_mins = parse_time_to_minutes(t_q)
                if target_mins is not None:
                    # Check if target_mins falls within [st_mins, et_mins]
                    if not (st_mins <= target_mins <= et_mins):
                        return False

    return True
