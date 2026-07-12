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
