"""Classic PixlCreate 16-color palette (RGB565 values from the Lua editor)."""

from __future__ import annotations

from typing import List, Tuple

from .vpe import c565_to_rgb

# Exact RGB565 values from VXP_Pixel_Editor src/70_editor.lua
PALETTE_565: List[int] = [
    0x0000, 0x4208, 0x8410, 0xC618, 0xFFFF, 0xF800, 0xFBE0, 0xFFE0,
    0x07E0, 0x0400, 0x07FF, 0x067F, 0x001F, 0x781F, 0xF81F, 0xFC18,
]

PALETTE_NAMES: List[str] = [
    "BLK", "DGY", "GRY", "LGY", "WHT", "RED", "ORG", "YEL",
    "GRN", "DGR", "CYN", "SKY", "BLU", "VIO", "MAG", "PNK",
]


def palette_rgb() -> List[Tuple[int, int, int]]:
    return [c565_to_rgb(c) for c in PALETTE_565]


def palette_hex() -> List[str]:
    return [f"#{r:02X}{g:02X}{b:02X}" for r, g, b in palette_rgb()]


def name_for_index(idx: int) -> str:
    if 0 <= idx < len(PALETTE_NAMES):
        return PALETTE_NAMES[idx]
    return "CUS"
