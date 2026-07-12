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
