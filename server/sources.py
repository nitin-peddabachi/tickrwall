import os
import time

import requests

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

_cache = {}


def _get_json(url, ttl):
    now = time.time()
    hit = _cache.get(url)
    if hit and now - hit[0] < ttl:
        return hit[1]
    data = requests.get(url, timeout=10).json()
    _cache[url] = (now, data)
    return data


def stock_quote(sym):
    return _get_json(
        "https://finnhub.io/api/v1/quote?symbol=%s&token=%s" % (sym, FINNHUB_KEY),
        ttl=60,
    )


def espn_scoreboard(sport, league):
    return _get_json(
        "https://site.api.espn.com/apis/site/v2/sports/%s/%s/scoreboard" % (sport, league),
        ttl=60,
    )


def crypto_prices(ids):
    if not ids:
        return {}
    return _get_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=%s&vs_currencies=usd&include_24hr_change=true" % ",".join(ids),
        ttl=60,
    )
