from datetime import datetime, timedelta, timezone

GREEN = "#00C853"
RED = "#FF1744"
WHITE = "#FFFFFF"
YELLOW = "#FFD600"

MAX_FINISHED_AGE = timedelta(hours=24)


def _now_utc():
    return datetime.now(timezone.utc)


def _is_current(state, date):
    """Live matches always qualify; finished/other matches only if recent.

    Without this, a tournament ID with no games today (e.g. IPL out of
    season) keeps showing its last-ever final score indefinitely, since
    ESPN's scoreboard endpoint still returns that event with a non-"pre"
    state. Recency is elapsed time, not a UTC calendar-date match — a
    same-day comparison flips a same-day match to "not today" the moment
    UTC crosses midnight, well before it's actually stale.
    """
    if state == "in":
        return True
    if not date:
        return False
    try:
        played = datetime.fromisoformat(date.replace("Z", "+00:00"))
    except ValueError:
        return False
    return _now_utc() - played <= MAX_FINISHED_AGE


def _price_line(symbol, price, pct):
    sign = "+" if pct >= 0 else ""
    return {
        "text": "%s %.2f %s%.1f%%" % (symbol, price, sign, pct),
        "color": GREEN if pct >= 0 else RED,
        "live": False,
        "symbol": symbol,
    }


def format_stock(sym, q):
    if not q or not q.get("c"):
        return None
    return _price_line(sym, q["c"], q.get("dp") or 0.0)


def format_crypto(symbol, data):
    if not data or data.get("usd") is None:
        return None
    return _price_line(symbol, data["usd"], data.get("usd_24h_change") or 0.0)


def format_espn_event(event, always_show=()):
    status = event["status"]["type"]
    if status["state"] == "pre":
        return None
    competitors = event["competitions"][0]["competitors"]
    home = next(c for c in competitors if c["homeAway"] == "home")
    away = next(c for c in competitors if c["homeAway"] == "away")
    is_favorite = (home["team"]["abbreviation"] in always_show
                   or away["team"]["abbreviation"] in always_show)
    if not is_favorite and not _is_current(status["state"], event.get("date")):
        return None
    live = status["state"] == "in"
    text = "%s %s-%s %s %s" % (
        away["team"]["abbreviation"], away["score"],
        home["score"], home["team"]["abbreviation"],
        status.get("shortDetail", ""),
    )
    return {"text": text.strip(), "color": YELLOW if live else WHITE, "live": live}


def format_cricket_event(event):
    status = event["status"]["type"]
    if status["state"] == "pre":
        return None
    if not _is_current(status["state"], event.get("date")):
        return None
    competitors = event["competitions"][0]["competitors"]
    scored = [c for c in competitors if c.get("score")]
    if not scored:
        return None
    home = next((c for c in competitors if c["homeAway"] == "home"), competitors[0])
    away = next((c for c in competitors if c["homeAway"] == "away"), competitors[-1])
    live = status["state"] == "in"
    text = "%s %s v %s %s %s" % (
        away["team"]["abbreviation"], away.get("score", "-"),
        home["team"]["abbreviation"], home.get("score", "-"),
        status.get("shortDetail", ""),
    )
    return {"text": " ".join(text.split()), "color": YELLOW if live else WHITE, "live": live}
