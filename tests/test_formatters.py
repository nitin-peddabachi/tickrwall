from datetime import datetime, timedelta, timezone

from server import formatters


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def test_format_stock_up():
    item = formatters.format_stock("AAPL", {"c": 231.42, "dp": 1.23})
    assert item == {
        "text": "AAPL 231.42 +1.2%", "color": formatters.GREEN, "live": False, "symbol": "AAPL",
    }


def test_format_stock_down():
    item = formatters.format_stock("NVDA", {"c": 118.03, "dp": -2.1})
    assert item == {
        "text": "NVDA 118.03 -2.1%", "color": formatters.RED, "live": False, "symbol": "NVDA",
    }


def test_format_stock_bad_quote_returns_none():
    assert formatters.format_stock("XXXX", {"c": 0, "dp": None}) is None
    assert formatters.format_stock("XXXX", None) is None


def test_format_crypto_up():
    item = formatters.format_crypto("BTC", {"usd": 64161.0, "usd_24h_change": 2.34})
    assert item == {
        "text": "BTC 64161.00 +2.3%", "color": formatters.GREEN, "live": False, "symbol": "BTC",
    }


def test_format_crypto_down():
    item = formatters.format_crypto("LTC", {"usd": 44.52, "usd_24h_change": -1.9})
    assert item == {
        "text": "LTC 44.52 -1.9%", "color": formatters.RED, "live": False, "symbol": "LTC",
    }


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


def test_format_espn_recent_final_is_white():
    now = datetime.now(timezone.utc)
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "FT"}},
        "date": _iso(now - timedelta(hours=8)),
        "competitions": ESPN_EVENT_LIVE["competitions"],
    }
    item = formatters.format_espn_event(ev)
    assert item["color"] == formatters.WHITE
    assert item["live"] is False


def test_format_espn_final_just_after_utc_midnight_still_counts(monkeypatch):
    # Regression: comparing calendar dates instead of elapsed time would drop
    # this the instant UTC crosses midnight, even though the match ended
    # less than an hour ago. Anchored to the next UTC midnight from whenever
    # this test actually runs, not a fixed date.
    now = datetime.now(timezone.utc)
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    monkeypatch.setattr(formatters, "_now_utc", lambda: next_midnight + timedelta(minutes=45))
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "FT"}},
        "date": _iso(next_midnight - timedelta(minutes=10)),
        "competitions": ESPN_EVENT_LIVE["competitions"],
    }
    assert formatters.format_espn_event(ev) is not None


def test_format_espn_final_from_a_past_day_is_dropped():
    now = datetime.now(timezone.utc)
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "FT"}},
        "date": _iso(now - timedelta(days=130)),
        "competitions": ESPN_EVENT_LIVE["competitions"],
    }
    assert formatters.format_espn_event(ev) is None


def test_format_espn_favorite_team_bypasses_recency():
    now = datetime.now(timezone.utc)
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "Final"}},
        "date": _iso(now - timedelta(days=5)),  # a week-old NFL result
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "24", "team": {"abbreviation": "DAL"}},
                {"homeAway": "away", "score": "17", "team": {"abbreviation": "NYG"}},
            ]
        }],
    }
    assert formatters.format_espn_event(ev) is None  # not a favorite by default
    item = formatters.format_espn_event(ev, always_show=["DAL"])
    assert item is not None
    assert "DAL" in item["text"]


def test_format_espn_non_favorite_team_still_needs_recency():
    now = datetime.now(timezone.utc)
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "Final"}},
        "date": _iso(now - timedelta(days=5)),
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "24", "team": {"abbreviation": "PHI"}},
                {"homeAway": "away", "score": "17", "team": {"abbreviation": "NYG"}},
            ]
        }],
    }
    assert formatters.format_espn_event(ev, always_show=["DAL"]) is None


def _cricket_event_final():
    now = datetime.now(timezone.utc)
    return {
        "status": {"type": {"state": "post", "shortDetail": "Final"}},
        "date": _iso(now - timedelta(hours=6)),
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "161/5 (18/20 ov, target 156)",
                 "team": {"abbreviation": "RCB"}},
                {"homeAway": "away", "score": "155/8", "team": {"abbreviation": "GT"}},
            ]
        }],
    }


def test_format_cricket_final():
    item = formatters.format_cricket_event(_cricket_event_final())
    assert item == {
        "text": "GT 155/8 v RCB 161/5 (18/20 ov, target 156) Final",
        "color": formatters.WHITE,
        "live": False,
    }


def test_format_cricket_final_from_a_past_tournament_is_dropped():
    now = datetime.now(timezone.utc)
    stale = dict(_cricket_event_final(), date=_iso(now - timedelta(days=140)))
    assert formatters.format_cricket_event(stale) is None


def test_format_cricket_favorite_team_bypasses_recency():
    now = datetime.now(timezone.utc)
    ev = {
        "status": {"type": {"state": "post", "shortDetail": "Final"}},
        "date": _iso(now - timedelta(days=60)),
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "287/6 (50 ov)", "team": {"abbreviation": "IND"}},
                {"homeAway": "away", "score": "250 all out", "team": {"abbreviation": "AUS"}},
            ]
        }],
    }
    assert formatters.format_cricket_event(ev) is None  # not a favorite by default
    item = formatters.format_cricket_event(ev, always_show=["IND"])
    assert item is not None
    assert "IND" in item["text"]


def test_format_cricket_live_is_yellow():
    ev = {
        "status": {"type": {"state": "in", "shortDetail": "RCB need 2"}},
        "competitions": _cricket_event_final()["competitions"],
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
