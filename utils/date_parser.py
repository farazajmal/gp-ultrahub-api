from datetime import datetime, timedelta
import re


def parse_availability(text: str):

    now = datetime.now()

    text = text.strip()

    # Tomorrow, 5:30 pm

    if text.startswith("Tomorrow"):

        time_part = text.replace("Tomorrow,", "").strip()

        appointment = datetime.strptime(
            time_part,
            "%I:%M %p"
        )

        return datetime(
            now.year,
            now.month,
            now.day,
            appointment.hour,
            appointment.minute
        ) + timedelta(days=1)

    # in 8 days

    match = re.match(r"in (\d+) days?", text)

    if match:

        return now + timedelta(days=int(match.group(1)))

    # Thu, 12:15 pm

    try:

        day_part, time_part = text.split(",")

        target_day = day_part.strip()

        appointment = datetime.strptime(
            time_part.strip(),
            "%I:%M %p"
        )

        weekdays = {
            "Mon":0,
            "Tue":1,
            "Wed":2,
            "Thu":3,
            "Fri":4,
            "Sat":5,
            "Sun":6
        }

        today = now.weekday()

        target = weekdays[target_day]

        days = (target - today) % 7

        if days == 0:
            days = 7

        return datetime(
            now.year,
            now.month,
            now.day,
            appointment.hour,
            appointment.minute
        ) + timedelta(days=days)

    except:

        return datetime.max