# device/code.py — ticker renderer for MatrixPortal M4 or S3.
#
# Dumb by design: fetches feed.json and scrolls it. All formatting/decision
# logic lives server-side in server/app.py; this file only renders.
#
# WiFi setup is the only board-specific branch below:
#   - S3 (and any board with a native WiFi radio): `import wifi` succeeds,
#     and wifi.radio talks to the radio directly.
#   - M4: the SAMD51 main chip has no radio of its own; WiFi comes from a
#     separate onboard ESP32 co-processor over SPI, so `import wifi` raises
#     ImportError and we fall back to adafruit_esp32spi instead.
# adafruit_connection_manager then hands back a matching socketpool/ssl
# context for whichever radio object we ended up with, so everything past
# that point (requests, fetching, scrolling) is identical on both boards.
# The panel wiring itself (board.MTX_*) is already shared across the whole
# MatrixPortal family, so it needs no branching at all.
import os
import random
import time

import board
import displayio
import framebufferio
import rgbmatrix
import terminalio
from adafruit_display_text import label
import adafruit_requests
import adafruit_connection_manager

from logos import LOGOS, LOGO_SIZE

FEED_URL = os.getenv("FEED_URL")
WIFI_SSID = os.getenv("CIRCUITPY_WIFI_SSID")
WIFI_PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
REFRESH_SECONDS = 30
SCROLL_DELAY = 0.03  # seconds per pixel; lower = faster
SCALE = 2
DIM_FACTOR = 0.25
LOGO_GAP = 3  # native pixels between an icon and the text that follows it

INTRO_SECONDS = 10  # minimum rain time at boot; keeps running past this until data arrives
CYCLE_RAIN_SECONDS = 15  # rain interlude played between each full pass through the feed
INTRO_FRAME_DELAY = 0.03
INTRO_GREEN = "#00FF41"  # classic "Matrix" green


def parse_color(hex_str):
    return int(hex_str.lstrip("#"), 16)


def dim(color, factor):
    r = int(((color >> 16) & 0xFF) * factor)
    g = int(((color >> 8) & 0xFF) * factor)
    b = int((color & 0xFF) * factor)
    return (r << 16) | (g << 8) | b


# bit_depth=4 matches the value already confirmed working on the M4 panel
# (see docs/superpowers/plans/2026-07-12-tickrwall.md troubleshooting notes).
# If flicker appears while WiFi is fetching, drop this or raise REFRESH_SECONDS.
displayio.release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=64, height=32, bit_depth=4,
    rgb_pins=[board.MTX_R1, board.MTX_G1, board.MTX_B1,
              board.MTX_R2, board.MTX_G2, board.MTX_B2],
    addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD],
    clock_pin=board.MTX_CLK, latch_pin=board.MTX_LAT, output_enable_pin=board.MTX_OE,
)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)

# Pre-build each icon's Bitmap/Palette/TileGrid once at startup rather than
# per-scroll — the pixel data is static, only the color needs to change for
# night dimming, and Palette entries can be mutated cheaply in place.
LOGO_TILEGRIDS = {}
for _symbol, (_rows, _color_hex) in LOGOS.items():
    _palette = displayio.Palette(2)
    _palette[0] = 0x000000
    _palette[1] = parse_color(_color_hex)
    _bitmap = displayio.Bitmap(LOGO_SIZE, LOGO_SIZE, 2)
    for _y, _row in enumerate(_rows):
        for _x, _ch in enumerate(_row):
            _bitmap[_x, _y] = 1 if _ch == "1" else 0
    LOGO_TILEGRIDS[_symbol] = (
        displayio.TileGrid(_bitmap, pixel_shader=_palette),
        _palette,
        parse_color(_color_hex),
    )


# Small hand-drawn "digital glyph" pixel patterns (4 wide x 5 tall) used by
# the rain animation instead of loading a real font — abstract symbols, not
# actual characters, but they read as "falling code" rather than plain dots.
GLYPH_W = 4
GLYPH_H = 5
GLYPHS = [
    ["0110", "1001", "1001", "1001", "0110"],  # o
    ["0100", "0100", "1110", "0100", "0100"],  # +
    ["1010", "1010", "0000", "1010", "1010"],  # dots
    ["1111", "0010", "0100", "1000", "1111"],  # z
    ["0010", "0110", "1010", "0010", "0010"],  # check
    ["1001", "1001", "0110", "1001", "1001"],  # x
    ["1100", "1100", "0011", "0011", "1111"],  # blocky
    ["0001", "0011", "0101", "1001", "1111"],  # diagonal
]
COL_PITCH = GLYPH_W + 1
ROW_PITCH = GLYPH_H + 1


def start_matrix_rain():
    """Set up the falling-character boot animation and show it immediately.

    Returns a state dict for advance_matrix_rain() to step frame-by-frame.
    Split from the stepping logic (rather than looping for a fixed duration
    here) so the caller can keep animating for as long as it takes to get
    on WiFi and fetch the first feed — see the combined loop below.

    Animates per character-cell (a grid of GLYPH_W x GLYPH_H blocks with a
    1px gap) rather than per-pixel-row, so each falling "drop" shows a
    column of small glyph symbols instead of a plain color gradient.
    """
    width, height = display.width, display.height
    n_cols = width // COL_PITCH
    n_rows = height // ROW_PITCH
    x_offset = (width - n_cols * COL_PITCH) // 2
    y_offset = (height - n_rows * ROW_PITCH) // 2
    shade_count = 8  # index 0 = off; 1..7 = dim -> bright green
    green = parse_color(INTRO_GREEN)

    palette = displayio.Palette(shade_count)
    palette[0] = 0x000000
    for i in range(1, shade_count):
        palette[i] = dim(green, i / (shade_count - 1))

    bitmap = displayio.Bitmap(width, height, shade_count)
    group = displayio.Group()
    group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    display.root_group = group

    state = {
        "bitmap": bitmap,
        "shade_count": shade_count,
        "n_cols": n_cols,
        "n_rows": n_rows,
        "x_offset": x_offset,
        "y_offset": y_offset,
        "heads": [random.uniform(-n_rows, 0) for _ in range(n_cols)],
        "speeds": [random.uniform(0.15, 0.35) for _ in range(n_cols)],
        "lengths": [random.randint(1, 3) for _ in range(n_cols)],
        "prev_int_head": [None] * n_cols,
        "glyph_at": [{} for _ in range(n_cols)],  # col -> {row: glyph index}
    }
    return state


def advance_matrix_rain(state):
    """Draw exactly one frame of the rain animation and sleep.

    Only redraws the small band of character-cells a column's trail
    actually occupies, plus clearing cells it just fell past, instead of
    recomputing every cell for every column on every frame — same reasoning
    as the earlier per-pixel version, just at character-cell granularity.
    """
    bitmap = state["bitmap"]
    shade_count = state["shade_count"]
    n_cols, n_rows = state["n_cols"], state["n_rows"]
    x_offset, y_offset = state["x_offset"], state["y_offset"]
    heads, speeds, lengths = state["heads"], state["speeds"], state["lengths"]
    prev_int_head, glyph_at = state["prev_int_head"], state["glyph_at"]

    def new_drop():
        return random.uniform(-3, 0), random.uniform(0.15, 0.35), random.randint(1, 3)

    def stamp(col, row, glyph_index, shade):
        gx = x_offset + col * COL_PITCH
        gy = y_offset + row * ROW_PITCH
        pattern = GLYPHS[glyph_index] if glyph_index is not None else None
        for dy in range(GLYPH_H):
            line = pattern[dy] if pattern else "0000"
            for dx in range(GLYPH_W):
                bitmap[gx + dx, gy + dy] = shade if line[dx] == "1" else 0

    def draw_band(col, head, length, prev_head):
        top = head - length
        for row in range(max(0, top), min(n_rows, head + 1)):
            if row not in glyph_at[col]:
                glyph_at[col][row] = random.randrange(len(GLYPHS))
            dist = head - row
            shade = (shade_count - 1) if dist == 0 else \
                max(1, (shade_count - 1) - round((dist / length) * (shade_count - 2)))
            stamp(col, row, glyph_at[col][row], shade)
        # Clear every cell the trail's top edge has advanced past since the
        # last draw — head can (and usually does) jump more than one row
        # per frame at these speeds, so a single-row clear would leave
        # bright cells stranded above the trail.
        if prev_head is not None:
            for row in range(max(0, prev_head - length), min(n_rows, top)):
                stamp(col, row, None, 0)
                glyph_at[col].pop(row, None)

    for col in range(n_cols):
        head = int(heads[col])
        if head != prev_int_head[col]:
            draw_band(col, head, lengths[col], prev_int_head[col])
            prev_int_head[col] = head
        heads[col] += speeds[col]
        if heads[col] - lengths[col] > n_rows:
            old_head, old_length = int(heads[col]), lengths[col]
            for row in range(max(0, old_head - old_length), min(n_rows, old_head + 1)):
                stamp(col, row, None, 0)
            glyph_at[col] = {}
            heads[col], speeds[col], lengths[col] = new_drop()
            prev_int_head[col] = None
    time.sleep(INTRO_FRAME_DELAY)


rain_state = start_matrix_rain()
intro_start = time.monotonic()

try:
    import wifi  # only importable on boards with a native WiFi radio (e.g. S3)

    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    radio = wifi.radio
except ImportError:
    # No native radio (e.g. M4) — use the onboard ESP32 co-processor instead.
    from digitalio import DigitalInOut
    from adafruit_esp32spi import adafruit_esp32spi

    esp32_cs = DigitalInOut(board.ESP_CS)
    esp32_ready = DigitalInOut(board.ESP_BUSY)
    esp32_reset = DigitalInOut(board.ESP_RESET)
    radio = adafruit_esp32spi.ESP_SPIcontrol(board.SPI(), esp32_cs, esp32_ready, esp32_reset)
    while not radio.is_connected:
        try:
            radio.connect_AP(WIFI_SSID, WIFI_PASSWORD)
        except OSError as exc:
            print("wifi connect retry:", exc)

pool = adafruit_connection_manager.get_radio_socketpool(radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(radio)
requests = adafruit_requests.Session(pool, ssl_context)


FETCH_TIMEOUT = 5  # seconds; a hung connection should just mean "retry next second",
                    # not a multi-second freeze of the rain animation while waiting on it.


def fetch_feed():
    try:
        with requests.get(FEED_URL, timeout=FETCH_TIMEOUT) as resp:
            return resp.json()
    except Exception as exc:
        print("feed fetch failed:", exc)
        return None


# Built once and mutated in place for every item, rather than creating new
# Group/TileGrid wrappers per scroll_item call — displayio only allows a
# TileGrid to belong to one parent Group at a time, so re-wrapping a shared,
# pre-built icon TileGrid (see LOGO_TILEGRIDS above) in a fresh Group each
# call crashes the moment that symbol scrolls a second time, with "layer
# already in a group". Mutating a fixed tree sidesteps that entirely.
text_label = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=0)
text_label.y = 16 // SCALE
text_group = displayio.Group(scale=SCALE)
text_group.append(text_label)

icon_group = displayio.Group()  # holds at most one logo TileGrid at a time

outer_group = displayio.Group()
outer_group.append(icon_group)
outer_group.append(text_group)
# Not shown yet — the rain animation (started above) keeps running as the
# root_group until the combined wait-loop below actually has feed data.


def scroll_item(item, night):
    color = parse_color(item.get("color", "#FFFFFF"))
    if night:
        color = dim(color, DIM_FACTOR)
    text_label.text = item["text"]
    text_label.color = color

    while len(icon_group) > 0:
        icon_group.pop()

    logo = LOGO_TILEGRIDS.get(item.get("symbol"))
    icon_width = 0
    if logo is not None:
        tile, palette, base_color = logo
        palette[1] = dim(base_color, DIM_FACTOR) if night else base_color
        icon_group.y = (display.height - LOGO_SIZE) // 2
        icon_group.append(tile)
        icon_width = LOGO_SIZE + LOGO_GAP
    text_group.x = icon_width

    total_width = icon_width + text_label.bounding_box[2] * SCALE
    for x in range(display.width, -total_width - 1, -1):
        outer_group.x = x
        time.sleep(SCROLL_DELAY)


# Keep the rain animating — not a fixed pause — until BOTH the minimum
# INTRO_SECONDS has elapsed AND the first feed fetch has actually succeeded.
# A slow WiFi connect or a slow/failing first fetch just means more rain,
# never a frozen frame or a "no data" placeholder before we've even tried.
feed = None
last_attempt = 0.0
while feed is None or time.monotonic() - intro_start < INTRO_SECONDS:
    advance_matrix_rain(rain_state)
    now = time.monotonic()
    if feed is None and now - last_attempt >= 1.0:
        feed = fetch_feed()
        last_attempt = now

display.root_group = outer_group
last_fetch = time.monotonic()

while True:
    if feed is None or time.monotonic() - last_fetch > REFRESH_SECONDS:
        fresh = fetch_feed()
        if fresh is not None:
            feed = fresh
            last_fetch = time.monotonic()

    if not feed or not feed.get("items"):
        scroll_item({"text": "no data", "color": "#333333"}, False)
        time.sleep(5)
        continue

    for entry in feed["items"]:
        scroll_item(entry, feed.get("dim", False))

    # Rain interlude between full passes through the ticker.
    cycle_rain = start_matrix_rain()
    cycle_rain_start = time.monotonic()
    while time.monotonic() - cycle_rain_start < CYCLE_RAIN_SECONDS:
        advance_matrix_rain(cycle_rain)
    display.root_group = outer_group
