# tickrwall

A wall/desk LED matrix ticker that scrolls a stock watchlist and live sports
scores (cricket, soccer, NFL). An [Adafruit MatrixPortal S3][mp] driving a
64×32 HUB75 panel fetches one compact JSON feed and scrolls it — all data
fetching and formatting happens server-side, so the display stays dumb and
reliable.

```
  AAPL 231.42 +1.2%    NVDA 118.03 -2.1%    IND 287/4 (42.3 ov)    KC 2-2 BAL Bot 6th
```

## Architecture

Two decoupled halves:

1. **Feed server** (`server/`) — a small Flask app that polls
   [Finnhub][fh] (stocks) and [ESPN][espn] (soccer, NFL, and cricket scores),
   formats each into a display-ready item, and serves them at `GET /feed.json`.
   Responses are cached per-URL with a TTL so a display polling every 30s never
   hammers the upstream APIs. Only stocks need an API key; all scores come from
   ESPN's public endpoints.
2. **Device renderer** (`device/`) — CircuitPython running on the MatrixPortal.
   It fetches `feed.json` and scrolls the items. It parses nothing else and
   makes no decisions; every formatting change lands server-side.

Feed contract (the only coupling between the two halves):

```json
{
  "items": [
    {"text": "AAPL 231.42 +1.2%", "color": "#00C853", "live": false},
    {"text": "KC 2-2 BAL Bot 6th", "color": "#FFD600", "live": true}
  ],
  "dim": false
}
```

## Running the feed server

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FINNHUB_KEY=your_finnhub_key      # required for stocks; scores need no key
python -m server.app                     # serves on http://0.0.0.0:8300
```

Then `curl localhost:8300/feed.json`. ESPN scores (soccer, NFL, cricket) need no
key. If any source is down or the Finnhub key is missing, that source is skipped
and the feed still serves whatever else is available — it never errors out.

Configure your watchlist, leagues, cricket tournaments, and dim hours in
`server/config.py`.

## Tests

```bash
pytest
```

## Keeping it running (macOS)

Copy `deploy/com.tickrwall.feed.plist.example` to
`~/Library/LaunchAgents/com.tickrwall.feed.plist`, replace the placeholder
paths and API key, then:

```bash
launchctl load ~/Library/LaunchAgents/com.tickrwall.feed.plist
```

The server now starts at login and restarts if it crashes.

## Roadmap

- Device renderer (`device/code.py`) — ships when hardware arrives
- Ambient/idle mode: clock, weather, or animations when markets are closed and
  no games are live
- Pixel-art logos beside ticker text
- 4-panel wall build
- Self-hosting the feed server on a home mini-PC for 24/7 fresh data

[mp]: https://www.adafruit.com/product/5778
[fh]: https://finnhub.io
[espn]: https://www.espn.com
