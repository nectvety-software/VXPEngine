"""Theme palettes and the QSS template they are injected into.

One QSS (`resources/editor.qss`) written against `$tokens`, two palettes. Adding a
theme means adding a dict, not duplicating a stylesheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

RESOURCES = Path(__file__).parent / "resources"

DARK = {
    "name": "dark",
    "label": "Terra Dark",
    "bg": "#0d0f13",
    "container": "#14171d",
    "panel": "#191d25",
    "panel_alt": "#1f242e",
    "surface": "#252b37",
    "titlebar": "#111419",
    "border": "#262c38",
    "border_strong": "#343c4c",
    "text": "#e6eaf2",
    "text_muted": "#98a2b5",
    "text_faint": "#6a7385",
    "accent": "#4f8cff",
    "accent_hover": "#689cff",
    "accent_soft": "#22304d",
    "accent_text": "#0b1220",
    "success": "#37d39a",
    "warn": "#f5b457",
    "danger": "#ff5f6d",
    "danger_soft": "#3a1d24",
    "hover": "#222834",
    "pressed": "#2b3341",
    "selection": "#2c3a58",
    "input": "#11141a",
    "scrollbar": "#333b49",
    "scrollbar_hover": "#48536655",
    "canvas": "#0a0c10",
    "grid": "#2c3444",
    "shadow": "#000000",
    "checker_a": "#15181e",
    "checker_b": "#1a1e26",
}

LIGHT = {
    "name": "light",
    "label": "Terra Light",
    "bg": "#eef0f4",
    "container": "#ffffff",
    "panel": "#f6f7fa",
    "panel_alt": "#eceef3",
    "surface": "#e2e6ee",
    "titlebar": "#f2f4f8",
    "border": "#d7dbe4",
    "border_strong": "#bcc3d1",
    "text": "#1c2129",
    "text_muted": "#5c6678",
    "text_faint": "#8a93a5",
    "accent": "#2f6fed",
    "accent_hover": "#4a82f5",
    "accent_soft": "#dfe9ff",
    "accent_text": "#ffffff",
    "success": "#12996b",
    "warn": "#b7791f",
    "danger": "#d64550",
    "danger_soft": "#fbe4e6",
    "hover": "#e9edf5",
    "pressed": "#dbe1ec",
    "selection": "#cfe0ff",
    "input": "#ffffff",
    "scrollbar": "#c3cad7",
    "scrollbar_hover": "#a9b2c2",
    "canvas": "#f3f4f7",
    "grid": "#c8cfdb",
    "shadow": "#8a93a5",
    "checker_a": "#f2f3f6",
    "checker_b": "#e9ebef",
}

PALETTES = {DARK["name"]: DARK, LIGHT["name"]: LIGHT}


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    colors: dict

    def c(self, key: str) -> str:
        return self.colors[key]

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"

    def qss(self) -> str:
        return Template((RESOURCES / "editor.qss").read_text(encoding="utf-8")).safe_substitute(
            **self.colors)


def theme(named: str) -> Theme:
    pal = PALETTES.get(named, DARK)
    return Theme(pal["name"], pal["label"], dict(pal))


def apply(app, named: str) -> Theme:
    """Install the palette on the QApplication and expose it as a property."""
    current = theme(named)
    app.setStyleSheet(current.qss())
    app.setProperty("themeName", current.name)
    app.setProperty("themeColors", dict(current.colors))
    return current


def current(app) -> Theme:
    return theme(app.property("themeName") or "dark")


def colors(app) -> dict:
    while app is not None:
        palette = app.property("themeColors")
        if palette:
            return dict(palette)
        app = app.parent()
    return dict(DARK)
