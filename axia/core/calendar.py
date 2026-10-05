"""Meeting slots in India time, shared by agents that book meetings."""

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def free_slots(at, meeting, booked, count=3):
    """Next open slots from tomorrow, inside working hours.

    meeting: {"minutes", "days" (e.g. ["Mon", ...]), "start_hour", "end_hour"}.
    Offers a spread of choices: at most two per day, hours apart.
    """
    length = timedelta(minutes=meeting["minutes"])
    day = (at.astimezone(IST) + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    slots = []
    for _ in range(30):
        if DAYS[day.weekday()] in meeting["days"]:
            start = day.replace(hour=meeting["start_hour"])
            while start + length <= day.replace(hour=meeting["end_hour"]):
                if start not in booked:
                    slots.append(start)
                    if sum(s.date() == day.date() for s in slots) == 2:
                        break
                    start += length * 2
                start += length
        if len(slots) >= count:
            return slots[:count]
        day += timedelta(days=1)
    return slots


def fmt(slots):
    return ", ".join(s.astimezone(IST).strftime("%a %d %b %I:%M %p") for s in slots)


def pick(text, offered):
    """The offered slot the AI says was chosen, or None. Never trusts a made-up time."""
    try:
        chosen = datetime.fromisoformat(text) if text else None
    except ValueError:
        return None
    return chosen if chosen in offered else None
