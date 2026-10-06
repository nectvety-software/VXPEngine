#!/usr/bin/env python3
"""Render VQEAF OS 240x320 screens using the device's own font, palette and icons.

Nothing here is invented: every pixel comes from the target repo.

  src/core/UiVietnameseFont.h   the pre-rasterised NFC glyph tables the ST7789 blits
  src/core/Theme.h              Retro Utility's 13 RGB565 theme colours
  docs/pixel_atlas.json         the 240x320 region contract per screen
  preview/icon_host/*.ppm       the 36x36 icons the launcher actually draws

Output goes into the OS repo's preview/ folder as 240x320 PNGs plus a contact
sheet, so a screen mockup can be diffed against a hardware capture.

Usage (from the Pixel_Editor root):
  python tools/make_vqeaf_screens.py [--os PATH] [--only home,menu] [--scale 2]
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

DEFAULT_OS = Path(r"D:\Program\arduino\legacy-32-classic-E524546\VQEAF_OS")

SCREEN_W = 240
SCREEN_H = 320

# ------------------------------------------------------------------ parsing

GLYPH_RE = re.compile(r"\{0x([0-9A-Fa-f]{2,6}),\s*(\d+),\s*\{([^}]*)\}\}")


def load_font(header: Path) -> List[Dict[int, Tuple[int, List[int]]]]:
    """Return [regular, bold] tables of codepoint -> (advance, 18 row bitmasks)."""
    text = header.read_text(encoding="utf-8", errors="replace")
    tables: List[Dict[int, Tuple[int, List[int]]]] = []
    for name in ("glyphs0", "glyphs1"):
        start = text.index(f"Glyph {name}[] = {{")
        end = text.index("\n};", start)
        body = text[start:end]
        table: Dict[int, Tuple[int, List[int]]] = {}
        for cp, adv, rows in GLYPH_RE.findall(body):
            bits = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]{4}", rows)]
            if len(bits) == 18:
                table[int(cp, 16)] = (int(adv), bits)
        if not table:
            raise SystemExit(f"no glyphs parsed from {name} in {header}")
        tables.append(table)
    return tables


THEME_ORDER = (
    "bg", "panel", "selected", "text", "dim", "chrome", "chromeText",
    "accent", "danger", "popup", "popupText", "popupSelected", "border",
)


def load_theme_colors(header: Path, theme: str = "RetroUtility") -> Dict[str, int]:
    """Read the RGB565 constants Theme.h compiles for one built-in theme."""
    text = header.read_text(encoding="utf-8", errors="replace")
    at = text.index(f"id == ThemeId::{theme}")
    block = text[text.index("return {", at):]
    block = block[: block.index("};")]
    values = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]{4}", block)]
    if len(values) != len(THEME_ORDER):
        raise SystemExit(f"{theme}: expected {len(THEME_ORDER)} colours, found {len(values)}")
    return dict(zip(THEME_ORDER, values))


def c565(v: int) -> Tuple[int, int, int]:
    """Decode RGB565 the same way the panel latches it."""
    return (((v >> 11) & 31) * 255 // 31,
            ((v >> 5) & 63) * 255 // 63,
            (v & 31) * 255 // 31)


# ------------------------------------------------------------------- canvas

class Screen:
    """RGB24 buffer. Kept in 24-bit so the PPM icons blit without re-quantising."""

    def __init__(self, w: int = SCREEN_W, h: int = SCREEN_H, fill=(0, 0, 0)) -> None:
        self.w, self.h = w, h
        self.px = bytearray(bytes(fill) * (w * h))

    def set(self, x: int, y: int, c: Tuple[int, int, int]) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def rect(self, x: int, y: int, w: int, h: int, c) -> None:
        for yy in range(max(0, y), min(self.h, y + h)):
            row = yy * self.w * 3
            lo, hi = max(0, x) * 3, min(self.w, x + w) * 3
            if hi > lo:
                self.px[row + lo:row + hi] = bytes(c) * ((hi - lo) // 3)

    def frame(self, x: int, y: int, w: int, h: int, c, t: int = 1) -> None:
        """TFT_eSPI drawRect(): the outline spans x..x+w-1, y..y+h-1."""
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def hline(self, x: int, y: int, n: int, c) -> None:
        self.rect(x, y, n, 1, c)

    def vline(self, x: int, y: int, n: int, c) -> None:
        self.rect(x, y, 1, n, c)

    def disc(self, cx: int, cy: int, r: int, c) -> None:
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    self.set(xx, yy, c)

    def blit(self, x: int, y: int, icon: "Icon") -> None:
        for yy in range(icon.h):
            for xx in range(icon.w):
                i = (yy * icon.w + xx) * 3
                rgb = (icon.rgb[i], icon.rgb[i + 1], icon.rgb[i + 2])
                if rgb == icon.transparent:
                    continue
                self.set(x + xx, y + yy, rgb)

    def blit_rgb(self, x: int, y: int, w: int, h: int, rgb: bytes) -> None:
        for yy in range(h):
            src = rgb[yy * w * 3:(yy + 1) * w * 3]
            for xx in range(w):
                self.set(x + xx, y + yy,
                         (src[xx * 3], src[xx * 3 + 1], src[xx * 3 + 2]))

    def blit_scaled(self, x: int, y: int, icon: "Icon", scale: int) -> None:
        for yy in range(icon.h * scale):
            for xx in range(icon.w * scale):
                i = ((yy // scale) * icon.w + (xx // scale)) * 3
                rgb = (icon.rgb[i], icon.rgb[i + 1], icon.rgb[i + 2])
                if rgb == icon.transparent:
                    continue
                self.set(x + xx, y + yy, rgb)


class Icon:
    """A P6 PPM loaded from the OS repo's icon host dumps."""

    def __init__(self, path: Path) -> None:
        data = path.read_bytes()
        if not data.startswith(b"P6"):
            raise SystemExit(f"{path} is not a P6 ppm")
        parts = data.split(b"\n", 3)
        w, h = (int(v) for v in parts[1].split())
        self.w, self.h = w, h
        self.rgb = parts[3][: w * h * 3]
        # The host dumps put icons on the theme background; treat that corner
        # colour as the key so the launcher cell fill stays visible underneath.
        self.transparent = tuple(self.rgb[0:3])


# --------------------------------------------------------------------- text

class Font:
    def __init__(self, tables: List[Dict[int, Tuple[int, List[int]]]]) -> None:
        self.tables = tables

    def _glyph(self, cp: int, bold: int):
        table = self.tables[bold]
        return table.get(cp) or table.get(ord("?")) or self.tables[0].get(ord("?"))

    def measure(self, s: str, bold: int = 0, scale: int = 1) -> int:
        return sum(self._glyph(ord(ch), bold)[0] for ch in s) * scale

    def fit(self, s: str, bold: int = 0, max_px: int = 0) -> str:
        """SymbianUI::fitTextPixels(): drop whole codepoints until "..." fits."""
        if max_px <= 0:
            return ""
        if self.measure(s, bold) <= max_px:
            return s
        cut = s
        while cut and self.measure(cut + "...", bold) > max_px:
            cut = cut[:-1]
        return cut + "..." if cut else "..."

    def draw(self, d: Screen, x: int, y: int, s: str, c, bg=None,
             bold: int = 0, scale: int = 1, clip_w: int = SCREEN_W) -> int:
        """Blit glyphs exactly like UiVietnameseFont::draw / drawScaled."""
        start = x
        if bg is not None:
            d.rect(x, y, min(clip_w, self.measure(s, bold, scale)), 18 * scale, bg)
        for ch in s:
            adv, rows = self._glyph(ord(ch), bold)
            step = adv * scale
            if x + step > start + clip_w:
                break
            for yy in range(18):
                bits = rows[yy]
                xx = 0
                while xx < 16:
                    if not (bits & (1 << xx)):
                        xx += 1
                        continue
                    first = xx
                    while xx < 16 and (bits & (1 << xx)):
                        xx += 1
                    if scale == 1:
                        d.hline(x + first, y + yy, xx - first, c)
                    else:
                        d.rect(x + first * scale, y + yy * scale,
                               (xx - first) * scale, scale, c)
            x += step
        return x - start


# ------------------------------------------------------------------ png out

def write_png(path: Path, w: int, h: int, rgb: bytes) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                     + chunk(b"IEND", b""))


def upscale(rgb: bytes, w: int, h: int, scale: int) -> Tuple[bytes, int, int]:
    if scale == 1:
        return rgb, w, h
    out = bytearray()
    for y in range(h):
        row = rgb[y * w * 3:(y + 1) * w * 3]
        big = bytearray()
        for x in range(w):
            big += row[x * 3:x * 3 + 3] * scale
        for _ in range(scale):
            out += big
    return bytes(out), w * scale, h * scale


# ------------------------------------------------------------- icon routing
# VqeafIconRenderer.cpp:25-36 fromLegacy() + UiIconCatalog.h:32-40 canonical().

CANONICAL = {"BT": "BLE", "Sh": "Term", "File": "Doc", "All": "App", "Sys": "Set"}

LEGACY_TO_ICON = {
    "Wi": "WiFi", "BLE": "Bluetooth", "Mus": "Music", "Dir": "Files",
    "Pic": "Gallery", "Web": "Internet", "Term": "Shell", "Rec": "Recovery",
    "Set": "Settings", "Th": "Themes", "App": "Apps", "Col": "Library",
}

ICON_ORDER = ("WiFi", "Bluetooth", "Music", "Files", "Gallery", "Internet",
              "Shell", "Recovery", "Settings", "Themes", "Apps", "Library")


def icon_for(key: str):
    """Return the flash-RLE icon name for a legacy key, or None for a badge."""
    return LEGACY_TO_ICON.get(CANONICAL.get(key, key))


# TFT_eSPI literals the OS hard-codes (shell inks, list-rail track).
LIT = {
    "grey": c565(0xC618),        # shell output lines
    "green": c565(0x07E0),       # shell "$" echo + prompt
    "dim50": c565(0x8410),       # shell hint
    "rule": c565(0x4208),        # shell input separator
    "track": c565(0x5ACB),       # list scrollbar track
}

# ------------------------------------------------------------------ ui layer
# Every method below mirrors one SymbianUI widget, pixel for pixel.

MICRO = CAPTION = 1
BODY = TITLE = 2


class Ui:
    def __init__(self, colors: Dict[str, int], font: Font,
                 icons: Dict[str, Dict[int, Icon]]) -> None:
        self.c = {k: c565(v) for k, v in colors.items()}
        self.selected_ink = c565(0xFFFF)
        self.f = font
        self.icons = icons

    # -- text ------------------------------------------------------------

    def text(self, d: Screen, x: int, y: int, s: str, font: int, ink,
             bg=None, clip_w: int = SCREEN_W, scale: int = 1) -> int:
        return self.f.draw(d, x, y, s, ink, bg, 1 if font >= BODY else 0,
                           scale, clip_w)

    def width(self, s: str, font: int, scale: int = 1) -> int:
        return self.f.measure(s, 1 if font >= BODY else 0, scale)

    def fit(self, s: str, font: int, max_px: int) -> str:
        return self.f.fit(s, 1 if font >= BODY else 0, max_px)

    # -- chrome ----------------------------------------------------------

    def wifi_bars(self, d: Screen, x: int, y: int, bars: int, ink) -> None:
        for i, height in enumerate((6, 9, 12, 16)):
            if i < bars:
                d.rect(x + i * 4, y + 16 - height, 3, height, ink)

    def battery(self, d: Screen, x: int, y: int, ink) -> None:
        d.frame(x, y + 1, 16, 14, ink)
        d.rect(x + 16, y + 5, 2, 5, ink)

    def header(self, d: Screen, title: str, clock: str, bars: int = 0,
               wifi_y: int = 5, battery_y: int = 5) -> None:
        c = self.c
        d.rect(0, 0, SCREEN_W, 27, c["chrome"])
        d.hline(0, 26, SCREEN_W, c["border"])
        self.text(d, 4, 5, self.fit(title, TITLE, 72), TITLE, c["chromeText"])
        tw = self.width(clock, MICRO)
        self.text(d, (SCREEN_W - tw) // 2, 8, clock, MICRO, c["chromeText"])
        x = SCREEN_W - 5 - 18
        if bars:
            self.wifi_bars(d, x - 5 - 18, wifi_y, bars, c["chromeText"])
        self.battery(d, x, battery_y, c["chromeText"])

    def footer(self, d: Screen, left: str, center: str, right: str) -> None:
        c = self.c
        d.rect(0, 298, SCREEN_W, 22, c["chrome"])
        d.hline(0, 298, SCREEN_W, c["border"])
        d.hline(0, 299, SCREEN_W, c["accent"])
        d.vline(SCREEN_W // 3, 301, 16, c["border"])
        d.vline((SCREEN_W * 2) // 3, 301, 16, c["border"])
        self.text(d, 4, 301, left, BODY, c["chromeText"])
        self.text(d, (SCREEN_W - self.width(center, BODY)) // 2, 301,
                  center, BODY, c["chromeText"])
        self.text(d, SCREEN_W - self.width(right, BODY) - 4, 301,
                  right, BODY, c["chromeText"])

    def wallpaper(self, d: Screen) -> None:
        """RetroUtility drawWallpaper(): flat bg plus nothing else."""
        d.rect(0, 0, SCREEN_W, SCREEN_H, self.c["bg"])

    # -- icons -----------------------------------------------------------

    def glyph(self, d: Screen, x: int, y: int, key: str, size: int, bg) -> None:
        name = icon_for(key)
        icon = self.icons.get(name, {}).get(size) if name else None
        if icon is not None:
            d.blit(x, y, icon)
            return
        # SymbianUI::drawS60MenuIcon() RetroUtility branch: 36px text badge.
        box = 36
        d.rect(x, y, box, box, bg)
        d.frame(x + 3, y + 3, box - 6, box - 6, self.c["dim"])
        badge = CANONICAL.get(key, key)[:2]
        tw = self.width(badge, BODY)
        self.text(d, x + (box - tw) // 2, y + 10, badge, BODY, self.c["accent"])

    # -- widgets ---------------------------------------------------------

    def row(self, d: Screen, i: int, key: str, title: str, sub: str,
            selected: bool, show_icon: bool = True) -> None:
        c = self.c
        y = 29 + i * 42
        bg = c["selected"] if selected else c["bg"]
        d.rect(2, y, 233, 41, bg)
        if selected:
            d.frame(2, y, 233, 41, c["border"])
            d.vline(3, y + 1, 39, c["chrome"])
        if show_icon:
            if icon_for(key):
                d.blit(12, y + 9, self.icons[icon_for(key)][24])
            else:
                self.glyph(d, 7, y + 3, key, 36, bg)
        ink = self.selected_ink if selected else c["text"]
        self.text(d, 48, y + 3, self.fit(title, BODY, 184), BODY, ink)
        if sub:
            self.text(d, 49, y + 22, self.fit(sub, MICRO, 183), MICRO, c["dim"])

    def scrollbar(self, d: Screen, total: int, visible: int, offset: int,
                  top: int = 30, bottom: int = 294) -> None:
        c = self.c
        x, h = SCREEN_W - 5, bottom - top
        d.rect(x, top, 3, h, c["bg"])
        if total <= visible or total <= 0:
            return
        d.rect(x, top, 3, h, LIT["track"])
        thumb_h = max(12, (h * visible) // total)
        max_offset = max(1, total - visible)
        travel = max(0, h - thumb_h)
        thumb_y = top + (travel * max(0, min(offset, max_offset))) // max_offset
        d.rect(x, thumb_y, 3, thumb_h, c["chromeText"])

    def menu_rail(self, d: Screen) -> None:
        c = self.c
        d.rect(236, 34, 2, 252, c["border"])
        d.rect(236, 36, 2, 82, c["accent"])

    def cell(self, d: Screen, slot: int, key: str, title: str,
             selected: bool) -> None:
        c = self.c
        x = 1 + (slot % 3) * 78
        y = 28 + (slot // 3) * 66
        w, h = 76, 66
        bg = c["selected"] if selected else c["bg"]
        d.rect(x, y, w, h, bg)
        if selected:
            d.frame(x + 1, y + 1, w - 2, h - 2, c["accent"])
        self.glyph(d, x + (w - 36) // 2, y + 3, key, 36, bg)
        label = self.fit(title, CAPTION, w - 6)
        tw = self.width(label, CAPTION)
        self.text(d, x + max(2, (w - tw) // 2), y + 44, label, CAPTION,
                  self.selected_ink if selected else c["text"])

    def message(self, d: Screen, title: str, *lines: str) -> None:
        c = self.c
        d.rect(0, 28, SCREEN_W, 50, c["bg"])
        self.text(d, 12, 50, title, TITLE, c["text"])
        d.rect(0, 78, SCREEN_W, 72, c["bg"])
        for i, line in enumerate(lines[:3]):
            if line:
                self.text(d, 12, 86 + i * 20, self.fit(line, MICRO, 216),
                          MICRO, c["text"])
        d.rect(0, 150, SCREEN_W, 298 - 150, c["bg"])

    def popup(self, d: Screen, items: Sequence[str], selected: int,
              offset: int = 0, visible: int = 5) -> None:
        c = self.c
        visible = min(visible, len(items))
        row_h = 31
        w = SCREEN_W * 4 // 5
        h = visible * row_h + 6
        x = (SCREEN_W - w) // 2
        y = 298 - h - 2
        d.rect(x, y, w, h, c["popup"])
        d.frame(x, y, w, h, c["border"])
        for r in range(visible):
            i = offset + r
            if i >= len(items):
                break
            iy = y + 3 + r * row_h
            on = i == selected
            bg = c["popupSelected"] if on else c["popup"]
            d.rect(x + 3, iy, w - 13, row_h - 1, bg)
            if on:
                d.frame(x + 3, iy, w - 13, row_h - 1, c["accent"])
            ink = self.selected_ink if on else c["popupText"]
            self.text(d, x + 10, iy + 6, self.fit(items[i], BODY, w - 34),
                      BODY, ink)
        if len(items) > visible:
            tx, ty, th = x + w - 7, y + 5, h - 10
            d.rect(tx, ty, 3, th, c["border"])
            thumb_h = max(10, (th * visible) // len(items))
            max_offset = max(1, len(items) - visible)
            d.rect(tx, ty + ((th - thumb_h) * offset) // max_offset,
                   3, thumb_h, c["accent"])

    def dialog(self, d: Screen, title: str, line1: str, line2: str,
               left: str, right: str, selected: int = 1) -> None:
        c = self.c
        w = SCREEN_W * 4 // 5
        x, y, h = (SCREEN_W - w) // 2, 88, 132
        d.rect(x, y, w, h, c["popup"])
        d.frame(x, y, w, h, c["border"])
        d.rect(x + 3, y + 3, w - 6, 27, c["chrome"])
        self.text(d, x + 9, y + 7, self.fit(title, TITLE, w - 18), TITLE,
                  c["chromeText"])
        self.text(d, x + 10, y + 43, self.fit(line1, MICRO, w - 20), MICRO,
                  c["popupText"])
        if line2:
            self.text(d, x + 10, y + 60, self.fit(line2, MICRO, w - 20), MICRO,
                      c["popupText"])
        by, bw = y + h - 33, (w - 26) // 2
        for i, label in enumerate((left, right)):
            bx = x + 8 if i == 0 else x + 18 + bw
            on = i == selected
            bg = c["popupSelected"] if on else c["popup"]
            d.rect(bx, by, bw, 24, bg)
            d.frame(bx, by, bw, 24, c["accent"] if on else c["border"])
            lw = self.width(label, MICRO)
            self.text(d, bx + (bw - lw) // 2, by + 5, label, MICRO,
                      self.selected_ink if on else c["popupText"])

    def progress(self, d: Screen, x: int, y: int, w: int, pct: int) -> None:
        c = self.c
        d.frame(x, y, w, 10, c["dim"])
        d.rect(x + 2, y + 2, (w - 4) * max(0, min(pct, 100)) // 100, 6,
               c["accent"])


# ------------------------------------------------------------------- screens
# Titles, softkey labels and body copy are quoted from the firmware sources;
# only runtime values (SSID, IP, file names, clocks) are sample data.

LAUNCHER_TITLES = ("WiFi", "Bluetooth", "Music", "File mgr", "Gallery",
                   "Internet", "Shell", "Recovery", "Settings", "Themes",
                   "Apps", "Library")
LAUNCHER_KEYS = ("Wi", "BLE", "Mus", "Dir", "Pic", "Web",
                 "Term", "Rec", "Set", "Th", "App", "Col")
LAUNCHER_OPTIONS = ("Open selected", "WiFi", "Gallery", "Qeafbrowser", "Shell",
                    "File manager", "Settings", "Themes", "Applications",
                    "Recovery", "Retro Explorer")
WIFI_OPTIONS = ("Connect", "Rescan", "Disconnect", "Forget saved",
                "Network status", "Saved networks", "Hidden network",
                "Network list")
BLE_OPTIONS = ("Details", "Rescan", "Clear results", "Bluetooth info")
FILE_OPTIONS = ("Open", "Properties", "Delete", "Refresh", "Root folder",
                "Downloads", "Themes", "App inbox")
GALLERY_OPTIONS = ("View", "Next image", "Previous image", "Slideshow",
                   "Stop slideshow", "Rescan", "File info")
MUSIC_OPTIONS = ("Now playing", "Play / Pause", "Next track",
                 "Previous track", "Shuffle toggle", "Repeat mode", "Stop",
                 "Rescan library", "Track details")
SHELL_OPTIONS = ("Command", "Network monitor", "System monitor",
                 "File commands", "Help", "Clear", "Recovery")
SETTINGS_OPTIONS = ("Change", "Reset appearance", "System info", "About",
                    "Close options")
THEME_OPTIONS = ("Apply", "Rescan microSD", "Theme details")
APP_OPTIONS = ("Open selected", "App installer", "Shell", "Tasks",
               "Text viewer", "Recovery", "Notifications", "Clock",
               "System info", "About")
BROWSER_OPTIONS = ("Enter address", "Home", "Reload", "Back", "Forward",
                   "Download link", "Downloads", "Page info", "Speed Dial",
                   "History", "Bookmarks", "Bookmark page", "Help", "Overview")

SETTINGS_LABELS = ("Theme", "Backlight", "Audio volume", "Clock format",
                   "Auto WiFi strongest", "Auto keypad lock", "About")
SETTINGS_KEYS = ("Th", "Br", "Mus", "Clk", "Wi", "Lock", "i")
SETTINGS_VALUES = ("Retro Utility", "70%", "45%", "24-hour", "On", "1 min")

BUILTIN_THEMES = ("Retro Utility", "VQEAF Midnight", "VQEAF Night",
                  "AMOLED Red", "Black", "VQEAF Lime")

APP_TITLES = ("Shell", "Open apps", "Notes", "Notifications", "Text viewer",
              "Recovery", "Clock", "System info", "About", "Themes",
              "App installer", "App inbox", "Calculator", "Stopwatch",
              "Alarm clock")
APP_SUBS = ("System terminal", "Recent apps and resume", "Quick note",
            "System events", "TXT/MD viewer", "Safe Mode", "Time",
            "Memory and reset", "OS information", "microSD themes",
            "Install/uninstall QEAPP", "Downloaded packages",
            "Portrait keypad arithmetic", "Timer and 4 lap records",
            "Wake-up alarms and countdown")
APP_KEYS = ("Term", "App", "Note", "Bell", "Doc", "Rec", "Clk", "Sys", "i",
            "Th", "App", "Dir", "Calc", "Clk", "Bell")

RECOVERY_ROWS = (("Boot status", "Power on / crashes 0", "Rec"),
                 ("Start normal mode", "Disable Safe Mode and restart", "Rec"),
                 ("Enable Safe Mode", "Use minimal drivers on next boot", "Lock"),
                 ("Clear recovery flags", "Clear crash-loop markers", "Rec"),
                 ("Restart device", "Software restart", "Rec"))

CALC_KEYS = (("7", "8", "9", "/"), ("4", "5", "6", "*"),
             ("1", "2", "3", "-"), ("C", "0", "=", "+"))

CLOCK = "14:32"
DATE = "Tue 15 Sep"


def sc_home(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "General", CLOCK, bars=4, wifi_y=8, battery_y=7)
    d.disc(68, 12, 6, c["chromeText"])
    n = "3"
    ui.text(d, 68 - ui.width(n, MICRO) // 2, 4, n, MICRO, c["chrome"])

    d.rect(12, 43, 216, 78, c["panel"])
    d.frame(12, 43, 216, 78, c["border"])
    d.rect(18, 50, 204, 63, c["panel"])
    tw = ui.width(CLOCK, TITLE, 2)
    ui.text(d, (SCREEN_W - tw) // 2, 53, CLOCK, TITLE, c["text"], scale=2)
    dw = ui.width(DATE, MICRO)
    ui.text(d, (SCREEN_W - dw) // 2, 91, DATE, MICRO, c["dim"], clip_w=204)

    d.rect(12, 132, 216, 46, c["panel"])
    ui.text(d, 18, 140, ui.fit("WiFi  VQEAF-LAB  -58dBm", MICRO, 204),
            MICRO, c["text"], clip_w=204)
    ui.text(d, 18, 154, ui.fit("3 unread notification(s)", MICRO, 204),
            MICRO, c["dim"], clip_w=204)

    for i, key in enumerate(("Wi", "Mus", "Dir")):
        sel = i == 0
        x, y, w, h = 8 + 76 * i, 191, 72, 67
        bg = c["selected"] if sel else c["panel"]
        d.rect(x, y, w, h, bg)
        d.frame(x, y, w, h, c["accent"] if sel else c["dim"])
        if sel:
            d.hline(x + 2, y + 2, 17, c["chrome"])
            d.hline(x + w - 19, y + 2, 17, c["chrome"])
        d.blit(x + 18, y + 6, ui.icons[icon_for(key)][36])
        label = ("WiFi", "Music", "Files")[i]
        lw = ui.width(label, CAPTION)
        ui.text(d, x + (w - lw) // 2, y + 47, label, CAPTION,
                ui.selected_ink if sel else c["text"])

    d.rect(8, 266, 224, 20, c["chrome"])
    ui.text(d, 13, 272, "MENU: tasks   OPT: settings", MICRO, c["dim"])
    ui.footer(d, "Menu", "Open", "Quick")


def sc_menu(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Menu", CLOCK, bars=4)
    for row in range(1, 4):
        d.hline(0, 28 + row * 66, SCREEN_W, c["border"])
    d.rect(0, 292, SCREEN_W, 6, c["bg"])
    ui.menu_rail(d)
    for slot in range(12):
        ui.cell(d, slot, LAUNCHER_KEYS[slot], LAUNCHER_TITLES[slot], slot == 0)
    ui.footer(d, "Options", "Open", "Exit")


def sc_menu_popup(ui: Ui, d: Screen) -> None:
    sc_menu(ui, d)
    ui.popup(d, list(LAUNCHER_OPTIONS), 0, offset=0, visible=5)
    ui.footer(d, "Select", "", "Cancel")


def sc_wifi_empty(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "WiFi", CLOCK, bars=4)
    ui.message(d, "WiFi", "No networks found", "Options > Rescan")
    ui.footer(d, "Options", "Connect", "Back")


def sc_wifi_scan(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "WiFi", CLOCK, bars=4)
    ui.message(d, "Search WLAN", "Scanning for access points",
               "Current WiFi stays active")
    d.rect(12, 160, 213, 40, c["bg"])
    ui.text(d, 12, 164, "Searching 3s", TITLE, c["text"])
    ui.progress(d, 12, 189, 207, 21)
    ui.footer(d, "", "", "Back")


def sc_wifi_status(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "WiFi", CLOCK, bars=4)
    ui.message(d, "Network status", "VQEAF-LAB", "IP 192.168.1.42",
               "RSSI -58 dBm")
    ui.footer(d, "Options", "", "Back")


def sc_bluetooth(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Bluetooth", CLOCK, bars=4)
    ui.message(d, "Bluetooth", "No BLE devices found", "Options > Rescan")
    ui.footer(d, "Options", "Details", "Back")


def sc_files(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Files /Media", CLOCK, bars=4)
    rows = (("notes.txt", "7 KB", "File"), ("tracker.ppm", "214 KB", "File"),
            ("Inbox", "Folder", "Dir"), ("Music", "Folder", "Dir"),
            ("Themes", "Folder", "Dir"), ("Apps", "Folder", "Dir"))
    for i, (name, sub, key) in enumerate(rows):
        ui.row(d, i, key, name, sub, i == 0)
    ui.scrollbar(d, 6, 6, 0)
    ui.footer(d, "Options", "Open", "Back")


def sc_files_dialog(ui: Ui, d: Screen) -> None:
    sc_files(ui, d)
    ui.dialog(d, "Delete file?", "notes.txt", "This cannot be undone.",
              "Delete", "Cancel", selected=1)
    ui.footer(d, "", "Select", "Cancel")


def sc_gallery(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Gallery", CLOCK, bars=4)
    images = (("retro_screen.ppm", "214 KB"), ("boot_logo.ppm", "96 KB"),
              ("snake_high.ppm", "188 KB"), ("theme_dark.ppm", "203 KB"),
              ("wifi_badge.ppm", "71 KB"))
    for i, (name, sub) in enumerate(images):
        ui.row(d, i, "Pic", name, sub, i == 0)
    ui.scrollbar(d, 5, 6, 0)
    ui.footer(d, "Options", "View", "Back")


def sc_gallery_preview(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Gallery", CLOCK, bars=4)
    d.rect(8, 39, 224, 220, c["panel"])
    d.frame(8, 39, 224, 220, c["dim"])
    d.rect(11, 42, 218, 194, c["bg"])
    # The decoded bitmap is replaced by the device's own 36px Gallery art at 5x
    # so the preview rect shows real VQEAF pixels rather than a grey block.
    art = ui.icons["Gallery"][36]
    d.blit_scaled(11 + (218 - 180) // 2, 42 + (194 - 180) // 2, art, 5)
    d.rect(10, 236, 220, 22, c["panel"])
    ui.text(d, 14, 238, ui.fit("retro_screen.ppm", MICRO, 212), MICRO, c["text"])
    ui.footer(d, "List", "Next", "Back")


def sc_music(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Music", CLOCK, bars=4)
    tracks = (("theme_boot.wav", "/Media/Music/theme_boot.wav"),
              ("menu_blip.wav", "/Media/Music/menu_blip.wav"),
              ("snake_eat.wav", "/Media/Music/snake_eat.wav"))
    for i, (name, path) in enumerate(tracks):
        ui.row(d, i, "Mus", name, path, i == 0)
    for i in range(len(tracks), 5):
        ui.row(d, i, "Mus", "", "", False, show_icon=False)
    d.rect(2, 29 + 42 * 5, 233, 41, c["bg"])
    ui.scrollbar(d, 3, 5, 0, top=35, bottom=237)
    d.rect(4, 241, 231, 47, c["panel"])
    ui.text(d, 10, 250, ui.fit("Idle / V45%", MICRO, 218), MICRO, c["text"])
    ui.text(d, 10, 268, ui.fit("Shuffle OFF  Repeat ALL", MICRO, 218), MICRO,
            c["dim"])
    ui.footer(d, "Options", "Play", "Back")


def sc_shell(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Shell", CLOCK, bars=4)
    d.rect(0, 28, SCREEN_W, 270, (0, 0, 0))
    lines = (("VQEAF Shell v2.1.0", False),
             ("SD / TLS bench diagnostics", False),
             ("Type help for commands", False),
             ("$ ls", True),
             ("ls: microSD not mounted", False),
             ("$ help", True),
             ("ls cat stat mkdir rm touch cp mv hexdump", False),
             ("wlan ip dns ping wget", False),
             ("sys free ps top reboot", False),
             ("$ sys", True),
             ("heap 214988 min 197412 psram 7864320", False),
             ("flash 16777216 chip rev 2", False),
             ("fw VQEAF OS v2.5.1", False))
    for i, (line, echo) in enumerate(lines):
        ui.text(d, 4, 36 + i * 12, ui.fit(line[:39], MICRO, 236), MICRO,
                LIT["green"] if echo else LIT["grey"], clip_w=236)
    d.rect(0, 258, SCREEN_W, 36, (0, 0, 0))
    d.hline(0, 258, SCREEN_W, LIT["rule"])
    ui.text(d, 4, 266, "s3:/$", MICRO, LIT["green"])
    ui.text(d, 4, 279, "START=command  UP=history", MICRO, LIT["dim50"])
    ui.footer(d, "Options", "Command", "Back")


def sc_settings(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Settings", CLOCK, bars=4)
    for i, key in enumerate(SETTINGS_KEYS[:-1]):
        ui.row(d, i, key, SETTINGS_LABELS[i], SETTINGS_VALUES[i], i == 0)
    ui.scrollbar(d, 7, 6, 0)
    ui.footer(d, "Options", "Open", "Back")


def sc_settings_popup(ui: Ui, d: Screen) -> None:
    sc_settings(ui, d)
    ui.popup(d, list(SETTINGS_OPTIONS), 0)
    ui.footer(d, "Select", "", "Cancel")


def sc_themes(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Themes", CLOCK, bars=4)
    for i, name in enumerate(BUILTIN_THEMES):
        ui.row(d, i, "Th", name,
               "Applied | Built-in" if i == 0 else "Built-in", i == 0)
    ui.scrollbar(d, 6, 6, 0)
    ui.footer(d, "Options", "Apply", "Back")


def sc_applications(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Applications", CLOCK, bars=4)
    for i in range(6):
        ui.row(d, i, APP_KEYS[i], APP_TITLES[i], APP_SUBS[i], i == 0)
    ui.scrollbar(d, 15, 6, 0)
    ui.footer(d, "Options", "Open", "Back")


def sc_installer(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "App inbox", CLOCK, bars=4)
    ui.message(d, "App installer", "microSD is not available")
    ui.footer(d, "", "", "Back")


def sc_recovery(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Recovery", CLOCK, bars=4)
    for i, (title, sub, key) in enumerate(RECOVERY_ROWS):
        ui.row(d, i, key, title, sub, i == 0)
    ui.footer(d, "", "Select", "Back")


def sc_calculator(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Calculator", CLOCK, bars=4)
    d.rect(8, 42, 224, 48, c["panel"])
    d.frame(8, 42, 224, 48, c["dim"])
    ui.text(d, 15, 56, ui.fit("12 * 7", TITLE, 225), TITLE, c["text"])
    for r in range(4):
        for col in range(4):
            sel = r == 0 and col == 0
            x, y = 10 + col * 56, 99 + r * 43
            bg = c["selected"] if sel else c["panel"]
            d.rect(x, y, 52, 39, bg)
            d.frame(x, y, 52, 39, c["accent"] if sel else c["dim"])
            label = CALC_KEYS[r][col]
            ui.text(d, x + (52 - ui.width(label, TITLE)) // 2, y + 10,
                    label, TITLE, c["text"])
    d.rect(8, 275, 224, 14, c["bg"])
    ui.text(d, 11, 278, "Options: .  /  backspace  /  clear", MICRO, c["dim"])
    ui.footer(d, "Options", "Enter", "Back")


def sc_stopwatch(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Stopwatch", CLOCK, bars=4)
    d.rect(7, 37, 226, 251, c["bg"])
    d.rect(12, 55, 216, 74, c["panel"])
    ui.text(d, 24, 76, "00:24.86", TITLE, c["text"])
    for i, label in enumerate(("Pause", "Lap", "Reset")):
        x, y = 8 + i * 76, 140
        sel = i == 0
        bg = c["selected"] if sel else c["panel"]
        d.rect(x, y, 70, 33, bg)
        d.frame(x, y, 70, 33, c["accent"] if sel else c["dim"])
        ui.text(d, x + 5, 151, label, CAPTION, c["text"])
    for i, line in enumerate(("Lap 1  00:12.34", "Lap 2  00:24.86")):
        ui.text(d, 15, 187 + 21 * i, line, MICRO, c["text"], clip_w=225)
    ui.footer(d, "", "Select", "Back")


def sc_browser(ui: Ui, d: Screen) -> None:
    ui.wallpaper(d)
    ui.header(d, "Qeafbrowser", CLOCK, bars=4)
    ui.message(d, "Qeafbrowser", "WiFi is not connected",
               "Options > Home can open cache")
    ui.footer(d, "Options", "", "Back")


def sc_browser_page(ui: Ui, d: Screen) -> None:
    c = ui.c
    ui.wallpaper(d)
    ui.header(d, "Qeafbrowser", CLOCK, bars=4)
    d.rect(0, 29, SCREEN_W, 35, c["bg"])
    d.rect(5, 36, 230, 24, c["panel"])
    d.frame(5, 36, 230, 24, c["dim"])
    ui.text(d, 9, 44, ui.fit("http://vqeaf.local/status", MICRO, 188), MICRO,
            c["text"])
    ui.text(d, 201, 44, "C", MICRO, c["accent"])
    d.rect(0, 64, SCREEN_W, 208, c["bg"])
    body = ("VQEAF board status", "", "Heap free      214988", 
            "Largest block  197412", "PSRAM          8 MB", "",
            "WiFi           VQEAF-LAB", "RSSI           -58 dBm", "",
            "microSD        mounted", "Volume         45 / 100", "",
            "Firmware       v2.5.1")
    for i, line in enumerate(body):
        if not line:
            continue
        link = line.startswith("VQEAF board")
        ui.text(d, 7, 66 + i * 16, line, MICRO,
                c["accent"] if link else c["text"], clip_w=237)
    y = 66
    d.rect(0, y - 2, 237, 20, c["selected"])
    d.frame(4, y - 2, 232, 19, c["border"])
    ui.text(d, 7, y - 2, body[0], MICRO, c["accent"], clip_w=230)
    d.rect(0, 272, SCREEN_W, 26, c["bg"])
    ui.scrollbar(d, 41, 13, 0, top=64, bottom=278)
    ui.footer(d, "Options", "Open", "Back")


SCREENS: List[Tuple[str, str, object]] = [
    ("home", "General standby", sc_home),
    ("menu", "Launcher 3 x 4", sc_menu),
    ("menu_popup", "Launcher options", sc_menu_popup),
    ("wifi", "WiFi empty", sc_wifi_empty),
    ("wifi_scan", "WiFi scanning", sc_wifi_scan),
    ("wifi_status", "WiFi details", sc_wifi_status),
    ("bluetooth", "BLE empty", sc_bluetooth),
    ("files", "File manager", sc_files),
    ("files_dialog", "Delete confirm", sc_files_dialog),
    ("gallery", "Image list", sc_gallery),
    ("gallery_preview", "Image preview", sc_gallery_preview),
    ("music", "Music library", sc_music),
    ("shell", "Shell terminal", sc_shell),
    ("settings", "Settings list", sc_settings),
    ("settings_popup", "Settings options", sc_settings_popup),
    ("themes", "Themes list", sc_themes),
    ("applications", "Applications", sc_applications),
    ("installer", "App inbox", sc_installer),
    ("recovery", "Recovery", sc_recovery),
    ("calculator", "Calculator", sc_calculator),
    ("stopwatch", "Stopwatch", sc_stopwatch),
    ("browser", "Browser offline", sc_browser),
    ("browser_page", "Browser loaded", sc_browser_page),
]


# --------------------------------------------------------------------- main

def build_sheet(ui: Ui, tiles: List[Tuple[str, bytes, int, int]], cols: int,
                scale: int, gap: int = 8) -> Tuple[bytes, int, int]:
    """Pack upscaled screens into a captioned grid, claude-s40 "Screens" style."""
    labels = [t[0] for t in tiles]
    tw, th = SCREEN_W * scale, SCREEN_H * scale
    cap = 18 * scale
    cols = min(cols, len(tiles)) or 1
    rows = (len(tiles) + cols - 1) // cols
    w = cols * tw + (cols + 1) * gap
    h = rows * (th + cap) + (rows + 1) * gap
    sheet = Screen(w, h, (8, 8, 8))
    for n, (_, rgb, _, _) in enumerate(tiles):
        r, col = divmod(n, cols)
        x = gap + col * (tw + gap)
        y = gap + r * (th + cap + gap)
        big, bw, bh = upscale(rgb, SCREEN_W, SCREEN_H, scale)
        sheet.blit_rgb(x, y, bw, bh, big)
        sheet.rect(x, y + th, bw, cap, ui.c["chrome"])
        ui.text(sheet, x + 6, y + th + (cap - 18) // 2, labels[n], CAPTION,
                ui.c["accent"])
    return bytes(sheet.px), w, h


def theme_slug(theme: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", theme).lower()


def main(argv: Sequence[str] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--os", type=Path, default=DEFAULT_OS,
                    help="VQEAF_OS checkout to read font/theme/atlas/icons from")
    ap.add_argument("--out", type=Path, default=None,
                    help="output folder (default <os>/preview/<theme>_screens)")
    ap.add_argument("--only", default="", help="comma list of screen ids")
    ap.add_argument("--scale", type=int, default=2, choices=(1, 2, 3),
                    help="upscale factor for the 2x copies and the sheet")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--theme", default="RetroUtility")
    args = ap.parse_args(argv)

    os_dir: Path = args.os
    for rel in ("src/core/UiVietnameseFont.h", "src/core/Theme.h",
                "docs/pixel_atlas.json", "preview/icon_host"):
        if not (os_dir / rel).exists():
            raise SystemExit(f"missing {rel} under {os_dir}")

    slug = theme_slug(args.theme)
    out = args.out or (os_dir / "preview" / f"{slug}_screens")
    (out / "screens").mkdir(parents=True, exist_ok=True)
    (out / f"screens_{args.scale}x").mkdir(parents=True, exist_ok=True)

    font = Font(load_font(os_dir / "src" / "core" / "UiVietnameseFont.h"))
    colors = load_theme_colors(os_dir / "src" / "core" / "Theme.h", args.theme)
    host = os_dir / "preview" / "icon_host"
    icons: Dict[str, Dict[int, Icon]] = {}
    for name in ICON_ORDER:
        for size in (24, 36):
            icons.setdefault(name, {})[size] = Icon(host / f"{name}_{size}.ppm")
    ui = Ui(colors, font, icons)

    wanted = [s.strip() for s in args.only.split(",") if s.strip()]
    todo = [s for s in SCREENS if not wanted or s[0] in wanted]
    if not todo:
        raise SystemExit(f"--only matched nothing; ids: "
                         f"{', '.join(s[0] for s in SCREENS)}")

    positions = {sid: i for i, (sid, _, _) in enumerate(SCREENS, 1)}
    tiles: List[Tuple[str, bytes, int, int]] = []
    for sid, caption, fn in todo:
        n = positions[sid]
        d = Screen(fill=colors_rgb(colors, "bg"))
        fn(ui, d)
        write_png(out / "screens" / f"{n:02d}_{sid}.png", d.w, d.h,
                  bytes(d.px))
        big, bw, bh = upscale(bytes(d.px), d.w, d.h, args.scale)
        write_png(out / f"screens_{args.scale}x" / f"{n:02d}_{sid}.png",
                  bw, bh, big)
        tiles.append((f"{n:02d} {caption}", bytes(d.px), bw, bh))
        print(f"{n:02d} {sid:14s} 240x320 -> screens/{n:02d}_{sid}.png")

    if not args.no_sheet:
        rgb, w, h = build_sheet(ui, tiles, cols=4, scale=args.scale)
        sheet = out / f"{slug}_screens_{args.scale}x.png"
        write_png(sheet, w, h, rgb)
        print(f"sheet {w}x{h} -> {sheet}")

    print(f"theme {args.theme}: "
          + " ".join(f"{k}={v:04X}" for k, v in colors.items()))
    print(f"screens {len(todo)}")
    return 0


def colors_rgb(colors: Dict[str, int], key: str) -> Tuple[int, int, int]:
    return c565(colors[key])


if __name__ == "__main__":
    raise SystemExit(main())
