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
