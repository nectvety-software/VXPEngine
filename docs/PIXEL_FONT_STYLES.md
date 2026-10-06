# Original pixel fonts and styles

`graphics/VxpPixelFont.h` provides a C-compatible, allocation-free RGB565
bitmap text renderer. No operating-system font or TTF/FreeType dependency.
The old `vxpe_story_text` remains compatible for existing applications.

## Families

| Face | Shape | Use |
|---|---|---|
| Vale UI | 5×7, variable glyph widths, upper/lowercase | Menu, instructions, body labels |
| Prism Display | 7×9, angular double stems, caps-style lowercase | Titles and result headings |
| Duel Digits | 5×7, fixed 5-pixel advances | HP, mana, clocks, cooldown numbers |

Each family contains 95 printable ASCII glyphs. Source masks are authored in
`engine/coremre/fonts/vaelora.json`; `tools/generate_pixel_fonts.py` emits the
core tables and identical `app/pixel_font_data.py` preview data. The SDK package
includes the source JSON and generator. Font pixels are code-native original
bitmap patterns, not imported franchise fonts.

## Style API

`VxpeFontStyle` selects face, integer scale (1..4), spacing (0..4), RGB565 ink,
shadow, outline and bevel highlight. Effects use separate passes so nearby
glyph outlines cannot overwrite foreground ink. All paint, including effects,
obeys the supplied clip rectangle and framebuffer bounds.

`vxpe_font_measure` returns logical advance width, excluding paint effects;
multiline strings return the widest line. `vxpe_font_height` returns glyph
height times scale. Newlines advance by glyph height plus 3 pixels, scaled.
Text is bounded to 512 bytes; invalid face uses Vale UI, invalid scale/spacing
clamps to supported limits. Unsupported bytes render as `?`; this version
does not include Vietnamese diacritics or Unicode shaping.

```c
VxpeFontStyle style;
vxpe_font_style_default(&style);
style.font_id = VXPE_FONT_DISPLAY;
style.effects = VXPE_FONT_SHADOW | VXPE_FONT_BEVEL;
style.color565 = 0xEDEB;
int x = (240 - vxpe_font_measure("VAELORA DUEL", &style)) / 2;
VxpeRectI clip = {0, 0, 240, 320};
vxpe_font_draw(framebuffer, 240, 320, x, 13, "VAELORA DUEL", &style, clip);
```

## Editor Assets → Font Styles

Five roles: title, body, numbers, hero, accent. Choose face, scale, spacing,
shadow/outline/bevel and RGB565 colors. Four presets: Royal Gold, Frost Cyan,
Rune Violet, Clean Ivory. Preview paints the same pixel masks as the C renderer.
Save writes project `assets/ui/font_styles.json` and
`src/font_styles_generated.h`. Vaelora Duel already uses these roles; Build
applies saved header changes. Other projects can include this header and pass
its `vaelora_font_*` style objects to the API. A family/scale change may need
layout adjustments; the native Vaelora defaults use 1x body and 2x result titles.
Semantic team/enemy colors override neutral ink on battlefield labels.

Core regression checks metrics, ASCII fallback, fixed digits, clipping,
limits and framebuffer guards. Editor regression compares all 76,800 pixels
against a C-rendered 240×320 reference covering faces, scale and effects.
