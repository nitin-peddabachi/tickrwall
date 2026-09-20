from server import app as app_module


def test_is_dim_window():
    assert app_module.is_dim(23) is True
    assert app_module.is_dim(2) is True
    assert app_module.is_dim(7) is False
    assert app_module.is_dim(12) is False


def test_feed_endpoint(monkeypatch):
    monkeypatch.setattr(app_module.sources, "stock_quote",
                        lambda sym: {"c": 100.0, "dp": 1.0})
    monkeypatch.setattr(app_module.sources, "espn_scoreboard",
                        lambda sport, league: {"events": []})
    monkeypatch.setattr(app_module.sources, "crypto_prices",
                        lambda ids: {i: {"usd": 5.0, "usd_24h_change": 1.0} for i in ids})

    client = app_module.app.test_client()
    data = client.get("/feed.json").get_json()

    n_stocks = len(app_module.config.WATCHLIST)
    n_crypto = len(app_module.config.CRYPTO)
    assert len(data["items"]) == n_stocks + n_crypto
    assert data["items"][0]["text"].startswith("AAPL 100.00")
    assert isinstance(data["dim"], bool)


def _live_event(home, away):
    return {
        "status": {"type": {"state": "in", "shortDetail": "45'"}},
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "1", "team": {"abbreviation": home}},
                {"homeAway": "away", "score": "0", "team": {"abbreviation": away}},
            ]
        }],
    }


def test_feed_caps_soccer_items_and_prioritizes_favorite(monkeypatch):
    events = [
        _live_event("ARS", "CHE"),
        _live_event("TOT", "AVL"),
        _live_event("EVE", "IPS"),
        _live_event("WHU", "MCI"),  # Man City, the configured favorite
        _live_event("NEW", "HUL"),
    ]

    def fake_scoreboard(sport, league):
        return {"events": events} if sport == "soccer" else {"events": []}

    monkeypatch.setattr(app_module.sources, "stock_quote", lambda sym: None)
    monkeypatch.setattr(app_module.sources, "crypto_prices", lambda ids: {})
    monkeypatch.setattr(app_module.sources, "espn_scoreboard", fake_scoreboard)

    client = app_module.app.test_client()
    data = client.get("/feed.json").get_json()

    assert len(data["items"]) == 3
    assert "MCI" in data["items"][0]["text"]


def _cricket_live_event(home, away):
    return {
        "status": {"type": {"state": "in", "shortDetail": "in progress"}},
        "competitions": [{
            "competitors": [
                {"homeAway": "home", "score": "150/3 (18 ov)", "team": {"abbreviation": home}},
                {"homeAway": "away", "score": "180/6 (20 ov)", "team": {"abbreviation": away}},
            ]
        }],
    }


def test_feed_cricket_is_india_only_for_national_tournaments_not_ipl(monkeypatch):
    def fake_scoreboard(sport, league):
        if sport != "cricket":
            return {"events": []}
        if league == "8048":  # IPL — franchise league, no "India" team, shows everything
            return {"events": [_cricket_live_event("MI", "CSK")]}
        if league == "8039":  # World Cup — national teams, restricted to India
            return {"events": [_cricket_live_event("IND", "AUS"), _cricket_live_event("ENG", "NZ")]}
        return {"events": []}

    monkeypatch.setattr(app_module.sources, "stock_quote", lambda sym: None)
    monkeypatch.setattr(app_module.sources, "crypto_prices", lambda ids: {})
    monkeypatch.setattr(app_module.sources, "espn_scoreboard", fake_scoreboard)

    client = app_module.app.test_client()
    data = client.get("/feed.json").get_json()

    texts = [i["text"] for i in data["items"]]
    assert any("MI" in t and "CSK" in t for t in texts)   # IPL match: shown
    assert any("IND" in t and "AUS" in t for t in texts)  # India's World Cup match: shown
    assert not any("ENG" in t for t in texts)              # non-India World Cup match: dropped


def test_feed_survives_source_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("api down")

    monkeypatch.setattr(app_module.sources, "stock_quote", boom)
    monkeypatch.setattr(app_module.sources, "espn_scoreboard", boom)
    monkeypatch.setattr(app_module.sources, "crypto_prices", boom)

    client = app_module.app.test_client()
    resp = client.get("/feed.json")

    assert resp.status_code == 200
    assert resp.get_json()["items"] == []
