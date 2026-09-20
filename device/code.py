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

INTRO_SECONDS = 10
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


def matrix_rain_intro():
    """Boot flourish: falling-green-column effect, ~5-6s, then returns.

    Only redraws the small band of rows a column's trail actually occupies,
    plus clearing whatever rows it just fell past, instead of recomputing
    all `height` rows for every column on every frame. On the M4's CPU, a
    full 64x32 recompute per frame was slow enough that the intended frame
    rate never happened in practice, making the animation look sluggish —
    this keeps per-frame work close to O(trail length) instead of O(height).
    """
    width, height = display.width, display.height
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

    def new_drop():
        return random.uniform(-10, 0), random.uniform(1.2, 2.8), random.randint(4, 10)

    heads = [0.0] * width
    speeds = [0.0] * width
    lengths = [0] * width
    prev_int_head = [None] * width
    for x in range(width):
        heads[x] = random.uniform(-height, 0)
        speeds[x] = random.uniform(1.2, 2.8)
        lengths[x] = random.randint(4, 10)

    def draw_band(x, head, length, prev_head):
        top = head - length
        for y in range(max(0, top), min(height, head + 1)):
            dist = head - y
            if dist == 0:
                bitmap[x, y] = shade_count - 1
            else:
                bitmap[x, y] = max(1, (shade_count - 1) - round((dist / length) * (shade_count - 2)))
        # Clear every row the trail's top edge has advanced past since the
        # last draw — head can (and usually does) jump more than one row
        # per frame at these speeds, so a single-row clear would leave
        # bright pixels stranded above the trail.
        if prev_head is not None:
            for y in range(max(0, prev_head - length), min(height, top)):
                bitmap[x, y] = 0

    start = time.monotonic()
    while time.monotonic() - start < INTRO_SECONDS:
        for x in range(width):
            head = int(heads[x])
            if head != prev_int_head[x]:
                draw_band(x, head, lengths[x], prev_int_head[x])
                prev_int_head[x] = head
            heads[x] += speeds[x]
            if heads[x] - lengths[x] > height:
                old_head, old_length = int(heads[x]), lengths[x]
                for y in range(max(0, old_head - old_length), min(height, old_head + 1)):
                    bitmap[x, y] = 0
                heads[x], speeds[x], lengths[x] = new_drop()
                prev_int_head[x] = None
        time.sleep(INTRO_FRAME_DELAY)


matrix_rain_intro()

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


def fetch_feed():
    try:
        with requests.get(FEED_URL) as resp:
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
display.root_group = outer_group


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


feed = None
last_fetch = 0.0

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
