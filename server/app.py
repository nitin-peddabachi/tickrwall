from datetime import datetime

from flask import Flask, jsonify

from server import config, formatters, sources

app = Flask(__name__)


def is_dim(hour):
    return hour >= config.DIM_START or hour < config.DIM_END


def _collect():
    items = []

    try:
        for sym in config.WATCHLIST:
            item = formatters.format_stock(sym, sources.stock_quote(sym))
            if item:
                items.append(item)
    except Exception as exc:
        app.logger.warning("stocks failed: %s", exc)

    try:
        leagues = [("soccer", lg) for lg in config.SOCCER_LEAGUES]
        if config.NFL:
            leagues.append(("football", "nfl"))
        for sport, league in leagues:
            for event in sources.espn_scoreboard(sport, league).get("events", []):
                item = formatters.format_espn_event(event)
                if item:
                    items.append(item)
    except Exception as exc:
        app.logger.warning("scores failed: %s", exc)

    try:
        for match in sources.cricket_matches().get("data", []):
            item = formatters.format_cricket_match(match)
            if item:
                items.append(item)
    except Exception as exc:
        app.logger.warning("cricket failed: %s", exc)

    return items


@app.get("/feed.json")
def feed():
    return jsonify({"items": _collect(), "dim": is_dim(datetime.now().hour)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8300)
