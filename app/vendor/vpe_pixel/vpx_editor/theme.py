"""Theme tokens + QSS loading for Light / Dark enterprise chrome."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional


def _style_dir() -> Path:
    """Locate style/ for both source tree and PyInstaller bundle."""
    candidates = []
    # PyInstaller one-folder: datas unpacked under _MEIPASS or _internal
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "style")
        candidates.append(Path(meipass) / "_internal" / "style")
    # Source tree
    candidates.append(Path(__file__).resolve().parent.parent / "style")
    # Next to frozen exe
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "style")
        candidates.append(Path(sys.executable).resolve().parent / "_internal" / "style")
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


STYLE_DIR = _style_dir()

# Design tokens — Enterprise creative-tool chrome.
DARK: Dict[str, str] = {
    "name": "dark",
    "bg": "#0B0E14",
    "surface": "#121722",
    "surface2": "#1A2130",
    "surface3": "#243044",
    "border": "#2A3448",
    "border_soft": "#1E2738",
    "text": "#E8EEF8",
    "muted": "#8A97AD",
    "faint": "#5B6A82",
    "accent": "#4C8DFF",
    "accent_hover": "#6AA0FF",
    "accent_down": "#3A74E0",
    "accent2": "#7B61FF",
    "on_accent": "#FFFFFF",
    "ok": "#2DD4A0",
    "warn": "#F5A524",
    "danger": "#FF5C7A",
    "canvas_bg": "#1E2430",
    "canvas_border": "#3A4860",
    "grid": "#3A4860",
    "shadow": "rgba(0, 0, 0, 0.45)",
    "glow": "rgba(76, 141, 255, 0.35)",
    "tool_idle": "#1A2130",
    "tool_hover": "#243044",
    "tool_active": "#2E4A78",
    "status": "#0E131C",
    "menu": "#121722",
    "input": "#0F141E",
    "check_a": "#1A2130",
    "check_b": "#222B3C",
}

LIGHT: Dict[str, str] = {
    "name": "light",
    "bg": "#EEF1F6",
    "surface": "#FFFFFF",
    "surface2": "#F4F6FA",
    "surface3": "#E4EAF3",
    "border": "#D0D8E6",
    "border_soft": "#E2E8F2",
    "text": "#1A2233",
    "muted": "#5B6A82",
    "faint": "#8A97AD",
    "accent": "#2F6FED",
    "accent_hover": "#4B84F5",
    "accent_down": "#1F58C8",
    "accent2": "#6B4FE8",
    "on_accent": "#FFFFFF",
    "ok": "#0F9F6E",
    "warn": "#C47A00",
    "danger": "#D93B5C",
    "canvas_bg": "#E8EDF5",
    "canvas_border": "#B8C4D8",
    "grid": "#B8C4D8",
    "shadow": "rgba(20, 30, 50, 0.12)",
    "glow": "rgba(47, 111, 237, 0.22)",
    "tool_idle": "#F4F6FA",
    "tool_hover": "#E4EAF3",
    "tool_active": "#D6E4FF",
    "status": "#F7F9FC",
    "menu": "#FFFFFF",
    "input": "#FFFFFF",
    "check_a": "#E8EDF5",
    "check_b": "#DDE5F0",
}

THEMES = {"dark": DARK, "light": LIGHT}


class Theme:
    def __init__(self, name: str = "dark") -> None:
        self._name = name if name in THEMES else "dark"
        self._tokens = THEMES[self._name]
        self._listeners = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def tokens(self) -> Dict[str, str]:
        return self._tokens

    def token(self, key: str, default: str = "#000000") -> str:
        return self._tokens.get(key, default)

    def is_dark(self) -> bool:
        return self._name == "dark"

    def set_theme(self, name: str) -> None:
        if name not in THEMES or name == self._name:
            return
        self._name = name
        self._tokens = THEMES[name]
        for cb in list(self._listeners):
            try:
                cb(name)
            except Exception:
                pass

    def toggle(self) -> str:
        self.set_theme("light" if self.is_dark() else "dark")
        return self._name

    def on_change(self, callback) -> None:
        self._listeners.append(callback)

    def qss(self) -> str:
        path = STYLE_DIR / f"{self._name}.qss"
        if not path.exists():
            return _fallback_qss(self._tokens)
        text = path.read_text(encoding="utf-8")
        return _fill_tokens(text, self._tokens)

    def apply_to_app(self, app) -> None:
        """Apply QSS + palette so Fusion does not keep light chrome."""
        from PySide6.QtGui import QColor, QPalette
        t = self._tokens
        app.setStyleSheet(self.qss())
        pal = QPalette()
        roles = {
            QPalette.ColorRole.Window: t["bg"],
            QPalette.ColorRole.WindowText: t["text"],
            QPalette.ColorRole.Base: t["surface"],
            QPalette.ColorRole.AlternateBase: t["surface2"],
            QPalette.ColorRole.Text: t["text"],
            QPalette.ColorRole.Button: t["surface2"],
            QPalette.ColorRole.ButtonText: t["text"],
            QPalette.ColorRole.ToolTipBase: t["surface3"],
            QPalette.ColorRole.ToolTipText: t["text"],
            QPalette.ColorRole.Highlight: t["accent"],
            QPalette.ColorRole.HighlightedText: "#FFFFFF",
            QPalette.ColorRole.PlaceholderText: t["muted"],
            QPalette.ColorRole.Mid: t["border"],
            QPalette.ColorRole.Dark: t["border_soft"],
            QPalette.ColorRole.Light: t["surface3"],
        }
        for role, color in roles.items():
            pal.setColor(role, QColor(color))
        app.setPalette(pal)


def _fill_tokens(text: str, tokens: Dict[str, str]) -> str:
    # Longest keys first so @surface2 is not clobbered by @surface.
    for key in sorted(tokens.keys(), key=len, reverse=True):
        text = text.replace(f"@{key}", tokens[key])
    return text


def _fallback_qss(t: Dict[str, str]) -> str:
    return f"""
    QWidget {{ background: {t['bg']}; color: {t['text']}; font-size: 13px; }}
    QMainWindow {{ background: {t['bg']}; }}
    QMenuBar {{ background: {t['menu']}; color: {t['text']}; border-bottom: 1px solid {t['border']}; }}
    QMenuBar::item:selected {{ background: {t['tool_hover']}; }}
    QMenu {{ background: {t['surface']}; border: 1px solid {t['border']}; }}
    QMenu::item:selected {{ background: {t['accent']}; color: white; }}
    QToolBar {{ background: {t['surface']}; border: none; spacing: 4px; padding: 4px; }}
    QStatusBar {{ background: {t['status']}; color: {t['muted']}; border-top: 1px solid {t['border']}; }}
    QPushButton {{
        background: {t['surface2']}; color: {t['text']};
        border: 1px solid {t['border']}; border-radius: 6px; padding: 6px 12px;
    }}
    QPushButton:hover {{ background: {t['tool_hover']}; border-color: {t['accent']}; }}
    QPushButton:pressed {{ background: {t['accent_down']}; }}
    QToolButton {{
        background: {t['tool_idle']}; color: {t['text']};
        border: 1px solid {t['border']}; border-radius: 8px; padding: 8px;
    }}
    QToolButton:checked {{ background: {t['tool_active']}; border-color: {t['accent']}; }}
    QFrame#Panel {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; }}
    QLabel#Heading {{ font-size: 12px; font-weight: 600; color: {t['muted']}; letter-spacing: 0.06em; }}
    QComboBox, QSpinBox, QLineEdit {{
        background: {t['input']}; border: 1px solid {t['border']}; border-radius: 6px;
        padding: 4px 8px; color: {t['text']};
    }}
    QToolTip {{ background: {t['surface3']}; color: {t['text']}; border: 1px solid {t['border']}; }}
    """


_global_theme: Optional[Theme] = None


def get_theme() -> Theme:
    global _global_theme
    if _global_theme is None:
        _global_theme = Theme("dark")
    return _global_theme
