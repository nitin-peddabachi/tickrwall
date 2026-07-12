GREEN = "#00C853"
RED = "#FF1744"
WHITE = "#FFFFFF"
YELLOW = "#FFD600"


def format_stock(sym, q):
    if not q or not q.get("c"):
        return None
    pct = q.get("dp") or 0.0
    sign = "+" if pct >= 0 else ""
    return {
        "text": "%s %.2f %s%.1f%%" % (sym, q["c"], sign, pct),
        "color": GREEN if pct >= 0 else RED,
        "live": False,
    }


def format_espn_event(event):
    status = event["status"]["type"]
    if status["state"] == "pre":
        return None
    competitors = event["competitions"][0]["competitors"]
    home = next(c for c in competitors if c["homeAway"] == "home")
    away = next(c for c in competitors if c["homeAway"] == "away")
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
