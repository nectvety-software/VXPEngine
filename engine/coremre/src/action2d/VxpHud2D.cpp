/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpHud2D implementation. The only arithmetic hazard worth engineering around
 * here is the divide: a segmented bar has to split max_value into N cells and
 * scale each cell to pixels, which naively costs two divides per segment per
 * frame. Segment bounds therefore come from an accumulating remainder
 * (Bresenham), and a divide survives only in the one partially filled cell.
 */
#include "action2d/VxpHud2D.h"

#include <stddef.h>
#include <string.h>

namespace {

inline int clamp_i(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

inline uint16_t dec_ms8(uint8_t v, uint16_t dt) {
    return v > dt ? (uint8_t)(v - dt) : 0;
}

/* The frame colour while a gauge flashes: pure ivory reads as "you were hit"
 * over any fill colour and needs no blending. */
const uint16_t kFlashColor = 0xFFFFu;

/* Fills the ring of `rect` that lies between its edge and `thick` px inward. */
void draw_ring(uint16_t* fb, int fb_w, int fb_h, VxpeRectI r, int thick, uint16_t color) {
    if (thick <= 0 || r.w <= 0 || r.h <= 0) return;
    const int t = clamp_i(thick, 1, r.w < r.h ? r.w : r.h);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x, r.y, r.w, t, color);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x, r.y + r.h - t, r.w, t, color);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x, r.y + t, t, r.h - 2 * t, color);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x + r.w - t, r.y + t, t, r.h - 2 * t, color);
}

/* Two-sided bevel: light along the top and left, dark along the bottom and
 * right. That asymmetry is what makes a flat panel read as carved. */
void draw_bevel(uint16_t* fb, int fb_w, int fb_h, VxpeRectI r, int thick,
                uint16_t hi, uint16_t lo) {
    if (thick <= 0 || r.w <= 0 || r.h <= 0) return;
    const int t = clamp_i(thick, 1, r.w < r.h ? r.w : r.h);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x, r.y, r.w, t, hi);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x, r.y, t, r.h, hi);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x, r.y + r.h - t, r.w, t, lo);
    vxpe2d_fill_rect(fb, fb_w, fb_h, r.x + r.w - t, r.y, t, r.h, lo);
}

/* A bar fill for one cell: how many of `cell_w` pixels `units` of [lo,hi)
 * covers. Full and empty cells answer without touching a divide. Only the
 * partial cell divides, and it divides in 32 bits: cell_w is a screen width
 * (<= 32767) and the span a value range (<= 65535), so the product provably
 * fits uint32_t and never drags in the 64-bit helper on ARMv5TE. */
inline int cell_fill_px(int cell_w, uint16_t lo, uint16_t hi, uint16_t units) {
    if (units <= lo || hi <= lo) return 0;
    if (units >= hi) return cell_w;
    return (int)((uint32_t)cell_w * (uint32_t)(units - lo) / (uint32_t)(hi - lo));
}

}  // namespace

extern "C" {

/* ---- plates ------------------------------------------------------------- */

void vxpe_hud_plate_default(VxpeHudPlate2D* plate) {
    if (plate == nullptr) return;
    plate->frame = vxpe2d_rgb565(20, 22, 34);
    plate->bevel_hi = vxpe2d_rgb565(96, 102, 126);
    plate->bevel_lo = vxpe2d_rgb565(8, 8, 16);
    plate->inner = vxpe2d_rgb565(28, 30, 46);
    plate->border_px = 1;
    plate->bevel_px = 1;
}

void vxpe_hud_plate_draw(uint16_t* fb, int fb_w, int fb_h,
                         VxpeRectI rect, const VxpeHudPlate2D* plate) {
    if (fb == nullptr || plate == nullptr || rect.w <= 0 || rect.h <= 0) return;

    const int b = clamp_i(plate->border_px, 0, 4);
    if (plate->inner != 0) {
        vxpe2d_fill_rect(fb, fb_w, fb_h, rect.x, rect.y, rect.w, rect.h, plate->inner);
    }
    if (b > 0) draw_ring(fb, fb_w, fb_h, rect, b, plate->frame);

    const int v = clamp_i(plate->bevel_px, 0, 4);
    if (v > 0 && rect.w > 2 * b && rect.h > 2 * b) {
        VxpeRectI inner;
        inner.x = (int16_t)(rect.x + b);
        inner.y = (int16_t)(rect.y + b);
        inner.w = (int16_t)(rect.w - 2 * b);
        inner.h = (int16_t)(rect.h - 2 * b);
        draw_bevel(fb, fb_w, fb_h, inner, v, plate->bevel_hi, plate->bevel_lo);
    }
}

void vxpe_hud_portrait_draw(uint16_t* fb, int fb_w, int fb_h,
                            VxpeRectI rect, const VxpeSprite565* art,
                            const VxpeHudPlate2D* plate,
                            uint16_t tint, uint8_t alpha) {
    if (fb == nullptr || art == nullptr || art->pixels == nullptr) return;
    if (rect.w <= 0 || rect.h <= 0) return;

    if (plate != nullptr) vxpe_hud_plate_draw(fb, fb_w, fb_h, rect, plate);

    const int b = plate != nullptr ? clamp_i(plate->border_px, 0, 4) : 0;
    const int v = plate != nullptr ? clamp_i(plate->bevel_px, 0, 4) : 0;
    const int inset = b + v;
    VxpeRectI field;
    field.x = (int16_t)(rect.x + inset);
    field.y = (int16_t)(rect.y + inset);
    field.w = (int16_t)(rect.w - 2 * inset);
    field.h = (int16_t)(rect.h - 2 * inset);
    if (field.w <= 0 || field.h <= 0) return;

    VxpeBlit565 op;
    memset(&op, 0, sizeof(op));
    op.src.x = 0;
    op.src.y = 0;
    op.src.w = (int16_t)art->width;
    op.src.h = (int16_t)art->height;
    op.dst_x = (int16_t)(field.x + (field.w - (int)art->width) / 2);
    op.dst_y = (int16_t)(field.y + (field.h - (int)art->height) / 2);
    op.dst_w = art->width;
    op.dst_h = art->height;
    op.tint565 = tint == 0 ? 0xFFFFu : tint;
    op.alpha = alpha == 0 ? 255 : alpha;
    /* COPY at full strength keeps the identity fast path reachable in
     * vxpe2d_blit; ALPHA only when the portrait is actually translucent. */
    op.blend = op.alpha >= 255 ? VXPE_BLEND_COPY : VXPE_BLEND_ALPHA;
    op.clip_x = field.x;
    op.clip_y = field.y;
    op.clip_w = (uint16_t)field.w;
    op.clip_h = (uint16_t)field.h;
    vxpe2d_blit(fb, fb_w, fb_h, art, &op);
}

/* ---- gauges ------------------------------------------------------------- */

void vxpe_hud_gauge_init(VxpeHudGauge2D* g, int x, int y, int w, int h,
                         uint16_t max_value) {
    if (g == nullptr) return;
    memset(g, 0, sizeof(*g));
    g->x = (int16_t)x;
    g->y = (int16_t)y;
    g->w = (int16_t)(w < 0 ? 0 : w);
    g->h = (int16_t)(h < 0 ? 0 : h);
    g->max_value = max_value == 0 ? 1 : max_value;
    g->value = g->max_value;
    g->ghost = g->max_value;
    g->color_full = vxpe2d_rgb565(184, 44, 52);
    g->color_low = vxpe2d_rgb565(216, 148, 40);
    g->color_ghost = vxpe2d_rgb565(96, 22, 30);
    g->color_bg = vxpe2d_rgb565(16, 16, 26);
    g->color_frame = vxpe2d_rgb565(110, 116, 140);
    g->ghost_rate_q8 = 200 << 8; /* 200 gauge units per second */
    g->segments = 0;
    g->gap_px = 2;
    g->low_at = 25;
    g->mirror = 0;
}

void vxpe_hud_gauge_set(VxpeHudGauge2D* g, uint16_t value) {
    if (g == nullptr) return;
    const uint16_t max = g->max_value == 0 ? 1 : g->max_value;
    g->value = value > max ? max : value;
    /* Healing (or a refill) has to pull the ghost up too, otherwise a bar that
     * dropped and recovered keeps a permanent red trail. */
    if (g->ghost < g->value) g->ghost = g->value;
}

void vxpe_hud_gauge_flash(VxpeHudGauge2D* g, uint8_t ms) {
    if (g == nullptr) return;
    if (ms > g->flash_ms) g->flash_ms = ms;
}

void vxpe_hud_gauge_update(VxpeHudGauge2D* g, uint16_t dt_ms) {
    if (g == nullptr) return;
    g->flash_ms = dec_ms8(g->flash_ms, dt_ms);

    if (g->ghost <= g->value || g->ghost_rate_q8 <= 0) {
        g->ghost = g->value;
        g->ghost_acc = 0;
        return;
    }
    /* rate is Q8 units/s and dt is ms, so one whole unit costs 256 * 1000 of
     * this accumulator. Carrying the remainder across frames, rather than
     * truncating rate*dt/1000 every frame, is what lets a drain slower than one
     * unit per frame move at all. */
    const int64_t total =
        (int64_t)g->ghost_acc + (int64_t)g->ghost_rate_q8 * (int64_t)dt_ms;
    const int64_t units = total / 256000;
    if (units <= 0) {
        g->ghost_acc = (uint32_t)total;
        return;
    }
    const int64_t span = (int64_t)g->ghost - g->value;
    if (units >= span) {
        g->ghost = g->value;
        g->ghost_acc = 0;
        return;
    }
    g->ghost = (uint16_t)(g->ghost - units);
    g->ghost_acc = (uint32_t)(total - units * 256000);
}

int vxpe_hud_gauge_is_low(const VxpeHudGauge2D* g) {
    if (g == nullptr || g->max_value == 0) return 0;
    /* percent compare without a divide: value*100 <= low_at*max. */
    return (int)((int32_t)g->value * 100) <= (int)((int32_t)g->low_at * g->max_value);
}

void vxpe_hud_gauge_draw(uint16_t* fb, int fb_w, int fb_h, const VxpeHudGauge2D* g) {
    if (fb == nullptr || g == nullptr || g->w <= 0 || g->h <= 0) return;
    const uint16_t max = g->max_value == 0 ? 1 : g->max_value;

    vxpe2d_fill_rect(fb, fb_w, fb_h, g->x, g->y, g->w, g->h, g->color_bg);

    /* Content box leaves room for the frame when there is one. */
    const int pad = g->color_frame != 0 ? 1 : 0;
    const int cx = g->x + pad, cy = g->y + pad;
    const int cw = g->w - 2 * pad, ch = g->h - 2 * pad;
    if (cw <= 0 || ch <= 0) return;

    const int seg = g->segments >= 2 ? g->segments : 1;
    const int gap = seg > 1 ? clamp_i(g->gap_px, 0, 4) : 0;
    const int cell_w = (cw - (seg - 1) * gap) / seg;
    if (cell_w <= 0) return;

    const uint16_t fill_units = g->value;
    const uint16_t trail_units = g->ghost > fill_units ? g->ghost : fill_units;
    const uint16_t ink = vxpe_hud_gauge_is_low(g) ? g->color_low : g->color_full;

    /* Bresenham bounds: cell i covers [floor(i*max/seg), floor((i+1)*max/seg)),
     * and both come from a step plus an accumulating remainder, so no divide
     * per cell. */
    const uint16_t step = (uint16_t)(max / seg);
    uint32_t rem = max % seg;
    uint32_t carry = 0;
    uint16_t lo = 0;

    for (int i = 0; i < seg; ++i) {
        carry += rem;
        uint32_t extra = 0;
        while (carry >= (uint32_t)seg) {
            carry -= (uint32_t)seg;
            ++extra;
        }
        const uint16_t hi = (uint16_t)((i + 1) * step + extra);

        const int trail = cell_fill_px(cell_w, lo, hi, trail_units);
        const int fill = cell_fill_px(cell_w, lo, hi, fill_units);
        const int at = g->mirror ? cx + cw - (i * (cell_w + gap)) - cell_w
                                  : cx + i * (cell_w + gap);
        if (g->mirror) {
            if (trail > 0) {
                vxpe2d_fill_rect(fb, fb_w, fb_h, at + cell_w - trail, cy, trail, ch,
                                 g->color_ghost);
            }
            if (fill > 0) {
                vxpe2d_fill_rect(fb, fb_w, fb_h, at + cell_w - fill, cy, fill, ch, ink);
            }
        } else {
            if (trail > 0) {
                vxpe2d_fill_rect(fb, fb_w, fb_h, at, cy, trail, ch, g->color_ghost);
            }
            if (fill > 0) {
                vxpe2d_fill_rect(fb, fb_w, fb_h, at, cy, fill, ch, ink);
            }
        }
        lo = hi;
    }

    if (g->color_frame != 0) {
        VxpeRectI r;
        r.x = g->x;
        r.y = g->y;
        r.w = g->w;
        r.h = g->h;
        draw_ring(fb, fb_w, fb_h, r, 1, g->flash_ms ? kFlashColor : g->color_frame);
    }
}

/* ---- icon rows ---------------------------------------------------------- */

void vxpe_hud_icon_row_init(VxpeHudIconRow2D* row, const VxpeSprite565* full,
                            const VxpeSprite565* empty, int x, int y,
                            uint16_t max) {
    if (row == nullptr) return;
    memset(row, 0, sizeof(*row));
    row->full = full;
    row->empty = empty;
    row->x = (int16_t)x;
    row->y = (int16_t)y;
    row->max = max;
    row->color_empty = vxpe2d_rgb565(52, 44, 68);
    row->per_row = 0;
    row->pitch_x = 0;
    row->pitch_y = 0;
}

void vxpe_hud_icon_row_set(VxpeHudIconRow2D* row, uint16_t value) {
    if (row != nullptr) row->value = value;
}

int vxpe_hud_icon_row_draw(uint16_t* fb, int fb_w, int fb_h,
                           const VxpeHudIconRow2D* row) {
    if (fb == nullptr || row == nullptr || row->full == nullptr ||
        row->full->pixels == nullptr || row->max == 0) {
        return 0;
    }
    const uint16_t shown = row->value > row->max ? row->max : row->value;
    const int iw = row->full->width;
    const int ih = row->full->height;
    const int pitch_x = row->pitch_x > 0 ? row->pitch_x : iw + 2;
    const int pitch_y = row->pitch_y > 0 ? row->pitch_y : ih + 2;
    const int per = row->per_row > 0 ? row->per_row : row->max;

    int col = 0, r = 0, drawn = 0;
    for (uint16_t i = 0; i < row->max; ++i) {
        const int x = row->grow ? row->x - col * pitch_x : row->x + col * pitch_x;
        const int y = row->y + r * pitch_y;
        if (i < shown) {
            vxpe2d_blit_simple(fb, fb_w, fb_h, row->full, x, y);
        } else if (row->empty != nullptr && row->empty->pixels != nullptr) {
            vxpe2d_blit_simple(fb, fb_w, fb_h, row->empty, x, y);
        } else {
            /* No empty-frame art: darken the full sprite instead, which keeps
             * the silhouette (and therefore the count) readable. */
            VxpeBlit565 op;
            memset(&op, 0, sizeof(op));
            op.src.w = (int16_t)iw;
            op.src.h = (int16_t)ih;
            op.dst_x = (int16_t)x;
            op.dst_y = (int16_t)y;
            op.dst_w = (uint16_t)iw;
            op.dst_h = (uint16_t)ih;
            op.tint565 = row->color_empty;
            op.alpha = 255;
            op.blend = VXPE_BLEND_COPY;
            vxpe2d_blit(fb, fb_w, fb_h, row->full, &op);
        }
        ++drawn;
        ++col;
        if (col >= per) {
            col = 0;
            ++r;
        }
    }
    return drawn;
}

/* ---- boss name plate ---------------------------------------------------- */

void vxpe_hud_boss_init(VxpeHudBossPlate2D* p, int fb_w, int fb_h, uint16_t max_hp) {
    if (p == nullptr) return;
    memset(p, 0, sizeof(*p));
    const int w = clamp_i(fb_w - 48, 40, 240);
    const int x = (fb_w - w) / 2;
    const int h = 10;
    /* The plate rests near the bottom, which is where the eye already is when
     * the player watches a large enemy. gauge.y is only a template: draw time
     * re-derives it from the name font's height so a display face cannot
     * overlap the bar. */
    p->plate_y = (int16_t)(fb_h - 32 - h);
    vxpe_hud_gauge_init(&p->gauge, x, (int16_t)(p->plate_y + 12), w, h, max_hp);
    p->gauge.color_full = vxpe2d_rgb565(176, 36, 44);
    p->gauge.ghost_rate_q8 = 120 << 8;
    p->slide_y = p->plate_y;
    p->alpha = 255;
    p->state = 0;
    p->hide_ms = 0;
    p->show_ms = 2500;
    p->name[0] = 0;
}

void vxpe_hud_boss_show(VxpeHudBossPlate2D* p, const char* name, uint16_t hp) {
    if (p == nullptr) return;
    if (name != nullptr) {
        int i = 0;
        for (; name[i] != 0 && i < VXPE_BOSS_PLATE_NAME_MAX - 1; ++i) p->name[i] = name[i];
        p->name[i] = 0;
    }
    vxpe_hud_gauge_set(&p->gauge, hp);
    p->hide_ms = p->show_ms;
    if (p->state == 0 || p->state == 3) {
        p->state = 1;
        /* Start a plate's own height above its resting spot so it slides in
         * from off-screen in about 160 ms at 250 px/s. */
        p->slide_y = (int16_t)(p->plate_y - 40);
        p->alpha = 255;
    }
}

void vxpe_hud_boss_set_hp(VxpeHudBossPlate2D* p, uint16_t hp) {
    if (p == nullptr) return;
    vxpe_hud_gauge_set(&p->gauge, hp);
    if (p->state == 0) return; /* hidden: track the number, no feedback to show */
    vxpe_hud_gauge_flash(&p->gauge, 90);
    p->hide_ms = p->show_ms;
    if (p->state == 3) {
        /* Damage that lands mid-retreat pulls the plate back up instead of
         * letting the fight go unreported. */
        p->state = 2;
        p->alpha = 255;
    }
}

void vxpe_hud_boss_hide(VxpeHudBossPlate2D* p) {
    if (p != nullptr && p->state != 0) p->state = 3;
}

void vxpe_hud_boss_update(VxpeHudBossPlate2D* p, uint16_t dt_ms) {
    if (p == nullptr) return;
    vxpe_hud_gauge_update(&p->gauge, dt_ms);

    if (p->state == 1) {
        /* 250 px/s linear rise, clamped so a stalled frame cannot overshoot
         * past the resting position and bounce. */
        int step = dt_ms >> 2;
        if (step < 1) step = 1;
        p->slide_y = (int16_t)(p->slide_y + step);
        if (p->slide_y >= p->plate_y) {
            p->slide_y = p->plate_y;
            p->state = 2;
            p->hide_ms = p->show_ms;
        }
        return;
    }
    if (p->state == 2) {
        const uint32_t left = (uint32_t)p->hide_ms;
        p->hide_ms = left > dt_ms ? (uint16_t)(left - dt_ms) : 0;
        if (p->hide_ms == 0) p->state = 3;
        return;
    }
    if (p->state == 3) {
        /* Fade over a quarter of a second, then stop drawing entirely so a long
         * idle costs nothing. */
        p->alpha = p->alpha > dt_ms ? (uint8_t)(p->alpha - dt_ms) : 0;
        if (p->alpha == 0) p->state = 0;
    }
}

void vxpe_hud_boss_draw(uint16_t* fb, int fb_w, int fb_h,
                        const VxpeHudBossPlate2D* p, const VxpeFontStyle* name_style) {
    if (fb == nullptr || p == nullptr || p->state == 0) return;

    VxpeFontStyle style;
    vxpe_font_style_default(&style);
    if (name_style != nullptr) style = *name_style;
    const int name_h = vxpe_font_height(&style);
    const int pad = 3;
    const int dy = p->slide_y - p->plate_y;

    /* Fading scales the colours the plate owns instead of blending toward the
     * world behind it, because that world is not in a buffer this module can
     * read; over a dark scene the two read the same. The tint is built from the
     * 8-bit level through rgb565 so each 565 field is scaled by its own range,
     * and 255 lands exactly on the neutral 0xFFFF. */
    const uint16_t dim = vxpe2d_rgb565(p->alpha, p->alpha, p->alpha);

    VxpeHudPlate2D plate;
    vxpe_hud_plate_default(&plate);
    plate.inner = 0; /* the bar and the name fill it; keep the world visible */
    plate.frame = vxpe2d_tint565(plate.frame, dim);
    plate.bevel_hi = vxpe2d_tint565(plate.bevel_hi, dim);
    plate.bevel_lo = vxpe2d_tint565(plate.bevel_lo, dim);

    /* Layout is derived here, not stored, so whatever face the caller passes
     * fits: name line, gap, bar. */
    const int top = p->plate_y - pad + dy;
    const int gy = top + 2 + name_h + 3;
    VxpeRectI r;
    r.x = (int16_t)(p->gauge.x - 4);
    r.y = (int16_t)top;
    r.w = (int16_t)(p->gauge.w + 8);
    r.h = (int16_t)(gy + p->gauge.h + pad - top);
    vxpe_hud_plate_draw(fb, fb_w, fb_h, r, &plate);

    if (p->name[0] != 0) {
        VxpeFontStyle faded = style;
        faded.color565 = vxpe2d_tint565(style.color565, dim);
        faded.shadow565 = vxpe2d_tint565(style.shadow565, dim);
        faded.outline565 = vxpe2d_tint565(style.outline565, dim);
        faded.highlight565 = vxpe2d_tint565(style.highlight565, dim);
        VxpeRectI clip;
        clip.x = 0;
        clip.y = 0;
        clip.w = (int16_t)fb_w;
        clip.h = (int16_t)fb_h;
        vxpe_font_draw(fb, fb_w, fb_h, r.x + 4, top + 2, p->name, &faded, clip);
    }

    VxpeHudGauge2D g = p->gauge;
    g.y = (int16_t)gy;
    g.color_full = vxpe2d_tint565(g.color_full, dim);
    g.color_low = vxpe2d_tint565(g.color_low, dim);
    g.color_ghost = vxpe2d_tint565(g.color_ghost, dim);
    g.color_bg = vxpe2d_tint565(g.color_bg, dim);
    g.color_frame = vxpe2d_tint565(g.color_frame, dim);
    vxpe_hud_gauge_draw(fb, fb_w, fb_h, &g);
}

/* ---- corner minimap ----------------------------------------------------- */

void vxpe_hud_minimap_init(VxpeHudMinimap2D* mm, const uint8_t* rooms,
                           const uint8_t* tags, int width, int height,
                           int cell_px, int x, int y) {
    if (mm == nullptr) return;
    memset(mm, 0, sizeof(*mm));
    if (width < 0 || height < 0 || width > VXPE_MINIMAP_W_MAX ||
        height > VXPE_MINIMAP_H_MAX) {
        return; /* zeroed map: nothing draws, nothing overflows */
    }
    mm->rooms = rooms;
    mm->tags = tags;
    mm->width = (uint8_t)width;
    mm->height = (uint8_t)height;
    mm->cell = (uint8_t)clamp_i(cell_px, 2, 8);
    mm->x = (int16_t)x;
    mm->y = (int16_t)y;
    mm->color_bg = vxpe2d_rgb565(10, 10, 18);
    mm->color_room = vxpe2d_rgb565(74, 82, 108);
    mm->color_edge = vxpe2d_rgb565(126, 132, 156);
    mm->color_here = vxpe2d_rgb565(232, 208, 96);
    mm->color_boss = vxpe2d_rgb565(188, 40, 48);
    mm->color_save = vxpe2d_rgb565(72, 178, 122);
    mm->color_shop = vxpe2d_rgb565(196, 128, 44);
}

void vxpe_hud_minimap_mark(VxpeHudMinimap2D* mm, int rx, int ry) {
    if (mm == nullptr || rx < 0 || ry < 0 || rx >= mm->width || ry >= mm->height) return;
    const int idx = ry * mm->width + rx;
    mm->visited[idx >> 3] = (uint8_t)(mm->visited[idx >> 3] | (1u << (idx & 7)));
}

int vxpe_hud_minimap_seen(const VxpeHudMinimap2D* mm, int rx, int ry) {
    if (mm == nullptr || rx < 0 || ry < 0 || rx >= mm->width || ry >= mm->height) return 0;
    const int idx = ry * mm->width + rx;
    return (mm->visited[idx >> 3] >> (idx & 7)) & 1;
}

void vxpe_hud_minimap_draw(uint16_t* fb, int fb_w, int fb_h,
                           const VxpeHudMinimap2D* mm, int cur_rx, int cur_ry) {
    if (fb == nullptr || mm == nullptr || mm->rooms == nullptr ||
        mm->width == 0 || mm->height == 0) {
        return;
    }
    const int cell = mm->cell;
    const int w = mm->width * cell;
    const int h = mm->height * cell;
    vxpe2d_fill_rect(fb, fb_w, fb_h, mm->x, mm->y, w, h, mm->color_bg);

    for (int ry = 0; ry < mm->height; ++ry) {
        for (int rx = 0; rx < mm->width; ++rx) {
            const int idx = ry * mm->width + rx;
            if (!(mm->visited[idx >> 3] & (1u << (idx & 7)))) continue;
            const uint8_t id = mm->rooms[idx];
            if (id == 0) continue;
            const int x = mm->x + rx * cell;
            const int y = mm->y + ry * cell;
            /* One inset pixel of bg between cells is the room border: cheaper
             * than a ring pass per cell and it reads the same at this size. */
            const int inset = cell > 2 ? 1 : 0;
            vxpe2d_fill_rect(fb, fb_w, fb_h, x + inset, y + inset,
                             cell - 2 * inset, cell - 2 * inset, mm->color_room);

            uint16_t tag = 0;
            if (mm->tags != nullptr) tag = mm->tags[idx];
            uint16_t mark = 0;
            if (tag & VXPE_MM_BOSS) mark = mm->color_boss;
            else if (tag & VXPE_MM_SAVE) mark = mm->color_save;
            else if (tag & VXPE_MM_SHOP) mark = mm->color_shop;
            if (mark != 0 && cell >= 3) {
                vxpe2d_fill_rect(fb, fb_w, fb_h, x + cell / 2, y + cell / 2, 1, 1, mark);
            }
        }
    }

    if (cur_rx >= 0 && cur_ry >= 0 && cur_rx < mm->width && cur_ry < mm->height) {
        const int x = mm->x + cur_rx * cell;
        const int y = mm->y + cur_ry * cell;
        /* A 3 px pip in a 4 px cell would eat the room it sits in, so the mark
         * only grows once the cell has room for it. */
        const int s = cell >= 6 ? 3 : 1;
        vxpe2d_fill_rect(fb, fb_w, fb_h, x + (cell - s) / 2, y + (cell - s) / 2, s, s,
                         mm->color_here);
    }

    VxpeRectI frame;
    frame.x = (int16_t)(mm->x - 1);
    frame.y = (int16_t)(mm->y - 1);
    frame.w = (int16_t)(w + 2);
    frame.h = (int16_t)(h + 2);
    draw_ring(fb, fb_w, fb_h, frame, 1, mm->color_edge);
}

/* ---- text helpers ------------------------------------------------------- */

void vxpe_hud_text_center(uint16_t* fb, int fb_w, int fb_h, int cx, int y,
                          const char* text, const VxpeFontStyle* style) {
    if (text == nullptr || text[0] == 0) return;
    VxpeRectI clip;
    clip.x = 0;
    clip.y = 0;
    clip.w = (int16_t)fb_w;
    clip.h = (int16_t)fb_h;
    vxpe_font_draw(fb, fb_w, fb_h, cx - vxpe_font_measure(text, style) / 2, y,
                   text, style, clip);
}

void vxpe_hud_text_right(uint16_t* fb, int fb_w, int fb_h, int right, int y,
                         const char* text, const VxpeFontStyle* style) {
    if (text == nullptr || text[0] == 0) return;
    VxpeRectI clip;
    clip.x = 0;
    clip.y = 0;
    clip.w = (int16_t)fb_w;
    clip.h = (int16_t)fb_h;
    vxpe_font_draw(fb, fb_w, fb_h, right - vxpe_font_measure(text, style), y,
                   text, style, clip);
}

int vxpe_hud_format_int(char* buf, int cap, int32_t value, int min_digits) {
    if (buf == nullptr || cap <= 0) return 0;
    char digits[12];
    int n = 0;
    const int neg = value < 0;
    /* -(int32_t)INT32_MIN overflows, so widen first. */
    uint32_t mag = neg ? (uint32_t)(-(int64_t)value) : (uint32_t)value;
    do {
        digits[n++] = (char)('0' + (int)(mag % 10u));
        mag /= 10u;
    } while (mag != 0 && n < (int)sizeof(digits));

    /* min_digits sizes the digit field only; the sign is extra. */
    const int sign_w = neg ? 1 : 0;
    int field = n > min_digits ? n : min_digits;
    if (field + sign_w >= cap) field = cap - 1 - sign_w;
    if (field < 0) field = 0;

    int out = 0;
    if (neg && field + sign_w <= cap - 1) buf[out++] = '-';
    for (int i = field - n; i > 0 && out < cap - 1; --i) buf[out++] = '0';
    /* A clamped field keeps the most significant digits: a truncated "123" of
     * 12345 is a visibly wrong number, which is what the caller asked for by
     * passing too small a buffer, not a silently different one. */
    for (int i = n - 1; i >= 0 && out < cap - 1; --i) buf[out++] = digits[i];
    buf[out] = 0;
    return out;
}

} /* extern "C" */
