WATCHLIST = ["AAPL", "NVDA", "NFLX", "GOOGL"]

# CoinGecko coin id -> ticker symbol shown on the display (keyless source)
CRYPTO = {"bitcoin": "BTC", "ethereum": "ETH", "litecoin": "LTC"}

SOCCER_LEAGUES = ["eng.1"]  # ESPN league slugs; eng.1 = Premier League
NFL = True

# Teams (ESPN abbreviation) to always show the latest live/finished game for,
# even if it's older than the usual 24h recency window — this matters most
# for NFL, where teams only play weekly and would otherwise be hidden most
# days. Other teams' games still follow the normal live-or-last-24h rule.
FAVORITE_TEAMS = {
    "football": ["DAL"],   # Dallas Cowboys
    "soccer": ["MCI"],     # Manchester City
}

# ESPN cricket tournament IDs (keyless, same source as soccer/NFL):
#   8048 = IPL, 8039 = World Cup, 8044 = Big Bash, 19430 = ICC World Test Championship
CRICKET_LEAGUES = ["8048", "8039", "8044", "19430"]

# Local hours during which the display dims (23:00–07:00)
DIM_START = 23
DIM_END = 7
