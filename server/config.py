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
    "cricket": ["IND"],    # India
}

# Cap on how many items a sport contributes to the feed, favorite team's game
# (if eligible) always kept first. Omit a sport here for no cap.
MAX_ITEMS_PER_SPORT = {
    "soccer": 3,  # full EPL slate would otherwise dominate the ticker
}

# ESPN cricket tournament IDs (keyless, same source as soccer/NFL):
#   8048 = IPL, 8039 = World Cup, 8044 = Big Bash, 19430 = ICC World Test Championship
CRICKET_LEAGUES = ["8048", "8039", "8044", "19430"]

# Leagues restricted to FAVORITE_TEAMS["cricket"] only (national-team
# tournaments where India is a real competitor). IPL and Big Bash are
# franchise leagues with no "India" team, so they're left out here and show
# everything that passes the normal live-or-recent filter, same as before —
# that alone means IPL naturally only appears during IPL season.
CRICKET_FAVORITE_ONLY_LEAGUES = ["8039", "19430"]  # World Cup, ICC WTC

# Local hours during which the display dims (23:00–07:00)
DIM_START = 23
DIM_END = 7
