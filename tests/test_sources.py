from server import sources


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_get_json_caches_within_ttl(monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return FakeResponse({"ok": True})

    monkeypatch.setattr(sources.requests, "get", fake_get)
    sources._cache.clear()

    first = sources._get_json("http://example/x", ttl=60)
    second = sources._get_json("http://example/x", ttl=60)

    assert first == second == {"ok": True}
    assert len(calls) == 1


def test_get_json_refetches_after_ttl(monkeypatch):
    calls = []
    monkeypatch.setattr(sources.requests, "get",
                        lambda url, timeout: calls.append(url) or FakeResponse({}))
    sources._cache.clear()

    sources._get_json("http://example/y", ttl=0)
    sources._get_json("http://example/y", ttl=0)

    assert len(calls) == 2


def test_cricket_without_key_returns_empty(monkeypatch):
    monkeypatch.setattr(sources, "CRICAPI_KEY", "")
    assert sources.cricket_matches() == {"data": []}
