#pragma once
#include <stdint.h>
#include "graphics/VxpRender2D.h"
#ifdef __cplusplus
extern "C" {
#endif
#define VXPE_FONT_UI 0
#define VXPE_FONT_DISPLAY 1
#define VXPE_FONT_DIGITS 2
#define VXPE_FONT_SHADOW 1
#define VXPE_FONT_OUTLINE 2
#define VXPE_FONT_BEVEL 4
#define VXPE_FONT_TEXT_MAX 512
typedef struct VxpeFontStyle {
    uint8_t font_id,scale,spacing,effects;
    uint16_t color565,shadow565,outline565,highlight565;
} VxpeFontStyle;
/* Defaults: Vale UI, 1x, 1px spacing, dark shadow, ivory ink. */
void vxpe_font_style_default(VxpeFontStyle* style);
/* Logical width excludes outline/shadow. Newlines return widest line.
 * Printable ASCII; each unsupported byte becomes '?'. Limits text to 512 bytes.
 * Scale clamps 1..4, spacing 0..4, unknown face uses Vale UI. */
int vxpe_font_measure(const char* text,const VxpeFontStyle* style);
int vxpe_font_height(const VxpeFontStyle* style);
/* Pixel-exact RGB565, clipped effects, no heap, no TTF or OS dependencies.
 * Clip rectangle uses framebuffer coordinates. Newline advances height+3px. */
void vxpe_font_draw(uint16_t* fb,int w,int h,int x,int y,const char* text,
    const VxpeFontStyle* style,VxpeRectI clip);
#ifdef __cplusplus
}
#endif
