from server import formatters


def test_format_stock_up():
    item = formatters.format_stock("AAPL", {"c": 231.42, "dp": 1.23})
    assert item == {"text": "AAPL 231.42 +1.2%", "color": formatters.GREEN, "live": False}


def test_format_stock_down():
    item = formatters.format_stock("NVDA", {"c": 118.03, "dp": -2.1})
    assert item == {"text": "NVDA 118.03 -2.1%", "color": formatters.RED, "live": False}


def test_format_stock_bad_quote_returns_none():
    assert formatters.format_stock("XXXX", {"c": 0, "dp": None}) is None
    assert formatters.format_stock("XXXX", None) is None


def test_format_crypto_up():
    item = formatters.format_crypto("BTC", {"usd": 64161.0, "usd_24h_change": 2.34})
    assert item == {"text": "BTC 64161.00 +2.3%", "color": formatters.GREEN, "live": False}


def test_format_crypto_down():
    item = formatters.format_crypto("LTC", {"usd": 44.52, "usd_24h_change": -1.9})
    assert item == {"text": "LTC 44.52 -1.9%", "color": formatters.RED, "live": False}


def test_format_crypto_missing_returns_none():
    assert formatters.format_crypto("ETH", None) is None
    assert formatters.format_crypto("ETH", {"usd": None}) is None


ESPN_EVENT_LIVE = {
    "status": {"type": {"state": "in", "shortDetail": "78'"}},
    "competitions": [{
        "competitors": [
            {"homeAway": "home", "score": "2", "team": {"abbreviation": "ARS"}},
            {"homeAway": "away", "score": "1", "team": {"abbreviation": "CHE"}},
        ]
    }],
}


def test_format_espn_live_game():
    item = formatters.format_espn_event(ESPN_EVENT_LIVE)
    assert item == {"text": "CHE 1-2 ARS 78'", "color": formatters.YELLOW, "live": True}


def test_format_espn_pregame_returns_none():
    ev = {"status": {"type": {"state": "pre"}}, "competitions": []}
    assert formatters.format_espn_event(ev) is None


def test_format_espn_final_is_white():
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "FT"}},
        "competitions": ESPN_EVENT_LIVE["competitions"],
    }
    item = formatters.format_espn_event(ev)
    assert item["color"] == formatters.WHITE
    assert item["live"] is False


CRICKET_EVENT_FINAL = {
    "status": {"type": {"state": "post", "shortDetail": "Final"}},
    "competitions": [{
        "competitors": [
            {"homeAway": "home", "score": "161/5 (18/20 ov, target 156)",
             "team": {"abbreviation": "RCB"}},
            {"homeAway": "away", "score": "155/8", "team": {"abbreviation": "GT"}},
        ]
    }],
}


def test_format_cricket_final():
    item = formatters.format_cricket_event(CRICKET_EVENT_FINAL)
    assert item == {
        "text": "GT 155/8 v RCB 161/5 (18/20 ov, target 156) Final",
        "color": formatters.WHITE,
        "live": False,
    }


def test_format_cricket_live_is_yellow():
    ev = {
        "status": {"type": {"state": "in", "shortDetail": "RCB need 2"}},
        "competitions": CRICKET_EVENT_FINAL["competitions"],
    }
    item = formatters.format_cricket_event(ev)
    assert item["color"] == formatters.YELLOW
    assert item["live"] is True


def test_format_cricket_pregame_returns_none():
    ev = {"status": {"type": {"state": "pre"}}, "competitions": []}
    assert formatters.format_cricket_event(ev) is None


def test_format_cricket_no_scores_returns_none():
    ev = {
        "status": {"type": {"state": "in", "shortDetail": "Delayed"}},
        "competitions": [{"competitors": [
            {"homeAway": "home", "score": "", "team": {"abbreviation": "RCB"}},
            {"homeAway": "away", "score": "", "team": {"abbreviation": "GT"}},
        ]}],
    }
    assert formatters.format_cricket_event(ev) is None
