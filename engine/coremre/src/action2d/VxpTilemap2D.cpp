/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpTilemap2D implementation. Hot path is the visible tile window: cell and
 * flag rows advance by pointer, and an unmasked, untinted, opaque layer copies
 * whole tiles without touching the general blitter.
 */
#include "action2d/VxpTilemap2D.h"

#include <stddef.h>

namespace {

/* Floor division for a positive divisor: -1/16 must be -1, not 0, so that
 * tiles left of the origin stay addressable. */
inline int fdiv(int v, int d) {
    if (d <= 0) return 0;
    const int q = v / d;
    return (v < 0 && v % d) ? q - 1 : q;
}

inline int clamp_i(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/* log2 for the atlas column count, or -1 when it is not a power of two. A
 * 16-column atlas is the normal layout, and this turns the per-tile id split
 * into a shift and a mask instead of two divides. */
inline int pow2_shift(int v) {
    if (v <= 0 || (v & (v - 1))) return -1;
    int s = 0;
    while ((1 << s) < v) ++s;
    return s;
}

/* Row-wise tile copy honouring the layer clip. Word stores whenever both ends
 * are 4-byte aligned, which is the case for an even-width framebuffer, an even
 * atlas stride and an even tile column - i.e. every normal tilemap. */
void copy_tile(uint16_t* fb, int fb_w,
               int cx0, int cy0, int cx1, int cy1,
               int dx, int dy,
               const uint16_t* src, int stride, int tw, int th) {
    int x0 = dx > cx0 ? dx : cx0;
    int x1 = (dx + tw) < cx1 ? (dx + tw) : cx1;
    int y0 = dy > cy0 ? dy : cy0;
    int y1 = (dy + th) < cy1 ? (dy + th) : cy1;
    if (x1 <= x0 || y1 <= y0) return;

    const int n = x1 - x0;
    for (int y = y0; y < y1; ++y) {
        const uint16_t* s = src + (size_t)(y - dy) * stride + (size_t)(x0 - dx);
        uint16_t* d = fb + (size_t)y * (size_t)fb_w + (size_t)x0;
        if ((n & 1) == 0 && ((((size_t)s | (size_t)d) & 3u) == 0u)) {
            const uint32_t* s32 = (const uint32_t*)(const void*)s;
            uint32_t* d32 = (uint32_t*)(void*)d;
            for (int k = n >> 1; k > 0; --k) *d32++ = *s32++;
        } else {
            for (int k = 0; k < n; ++k) d[k] = s[k];
        }
    }
}

}  // namespace

extern "C" {

VxpeTileDraw2D* vxpe_tile_view(VxpeTileDraw2D* view, int origin_x, int origin_y) {
    if (view == nullptr) return nullptr;
    view->origin_x = (int16_t)origin_x;
    view->origin_y = (int16_t)origin_y;
    view->clip_x = 0;
    view->clip_y = 0;
    view->clip_w = 0;
    view->clip_h = 0;
    view->tint565 = 0;
    view->alpha = 0;
    view->blend = VXPE_BLEND_COPY;
    view->skip_blank = 1;
    return view;
}

int vxpe_tilemap_draw(
    uint16_t* fb, int fb_w, int fb_h,
    const VxpeTilemap2D* map, const VxpeTileDraw2D* view) {
    if (fb == nullptr || map == nullptr || view == nullptr ||
        map->cells == nullptr || map->atlas == nullptr ||
        map->atlas->pixels == nullptr || fb_w <= 0 || fb_h <= 0 ||
        map->width == 0 || map->height == 0 ||
        map->tile_w == 0 || map->tile_h == 0 || map->atlas_cols == 0) {
        return 0;
    }

    int cx0 = 0, cy0 = 0, cx1 = fb_w, cy1 = fb_h;
    if (view->clip_w && view->clip_h) {
        cx0 = clamp_i(view->clip_x, 0, fb_w);
        cy0 = clamp_i(view->clip_y, 0, fb_h);
        cx1 = clamp_i(view->clip_x + view->clip_w, 0, fb_w);
        cy1 = clamp_i(view->clip_y + view->clip_h, 0, fb_h);
        if (cx1 <= cx0 || cy1 <= cy0) return 0;
    }

    const int tw = map->tile_w;
    const int th = map->tile_h;
    const int tx0 = clamp_i(fdiv(cx0 - view->origin_x, tw), 0, map->width - 1);
    const int tx1 = clamp_i(fdiv(cx1 - 1 - view->origin_x, tw), 0, map->width - 1);
    const int ty0 = clamp_i(fdiv(cy0 - view->origin_y, th), 0, map->height - 1);
    const int ty1 = clamp_i(fdiv(cy1 - 1 - view->origin_y, th), 0, map->height - 1);
    if (tx1 < tx0 || ty1 < ty0) return 0;

    const VxpeSprite565* atlas = map->atlas;
    const int stride = atlas->stride ? atlas->stride : atlas->width;
    const uint16_t tint = view->tint565 ? view->tint565 : 0xFFFFu;
    const uint8_t alpha = view->alpha ? view->alpha : 255u;
    const uint8_t blend = view->blend;
    const int plain = (atlas->opaque || atlas->mask == nullptr) &&
                      tint == 0xFFFFu && alpha == 255u && blend == VXPE_BLEND_COPY;
    const int cols = map->atlas_cols;
    const int col_shift = pow2_shift(cols);
    const int max_id = (int)atlas->height / th * cols;

    int drawn = 0;
    for (int ty = ty0; ty <= ty1; ++ty) {
        const int dst_y = view->origin_y + ty * th;
        /* The tile window is clamped to the map, so an edge row can sit wholly
         * outside the clip rect. Reject it here: a game budgets its frame by the
         * return value, and a hidden tile is not one it pays for. */
        if (dst_y + th <= cy0 || dst_y >= cy1) continue;
        const uint16_t* cell_row = map->cells + (size_t)ty * map->width;
        const uint16_t* flag_row =
            map->flags ? map->flags + (size_t)ty * map->width : nullptr;
        for (int tx = tx0; tx <= tx1; ++tx) {
            const int dst_x = view->origin_x + tx * tw;
            if (dst_x + tw <= cx0 || dst_x >= cx1) continue;
            const int id = cell_row[tx];
            if (id == 0 && view->skip_blank) continue;
            if (max_id > 0 && id >= max_id) continue;

            int col, row;
            if (col_shift >= 0) {
                col = id & (cols - 1);
                row = id >> col_shift;
            } else {
                col = id % cols;
                row = id / cols;
            }
            const uint16_t flags = flag_row ? flag_row[tx] : 0u;
            const uint16_t* tile = atlas->pixels +
                (size_t)(row * th) * stride + (size_t)(col * tw);

            if (plain && !(flags & (VXPE_TF_FLIP_X | VXPE_TF_FLIP_Y))) {
                copy_tile(fb, fb_w, cx0, cy0, cx1, cy1,
                          dst_x, dst_y, tile, stride, tw, th);
                ++drawn;
                continue;
            }

            VxpeBlit565 op{};
            op.src.x = (int16_t)(col * tw);
            op.src.y = (int16_t)(row * th);
            op.src.w = (int16_t)tw;
            op.src.h = (int16_t)th;
            op.dst_x = (int16_t)dst_x;
            op.dst_y = (int16_t)dst_y;
            op.dst_w = (uint16_t)tw;
            op.dst_h = (uint16_t)th;
            op.tint565 = tint;
            op.alpha = alpha;
            op.blend = blend;
            op.flip_x = (uint8_t)((flags & VXPE_TF_FLIP_X) ? 1 : 0);
            op.flip_y = (uint8_t)((flags & VXPE_TF_FLIP_Y) ? 1 : 0);
            op.clip_x = (int16_t)cx0;
            op.clip_y = (int16_t)cy0;
            op.clip_w = (uint16_t)(cx1 - cx0);
            op.clip_h = (uint16_t)(cy1 - cy0);
            vxpe2d_blit(fb, fb_w, fb_h, atlas, &op);
            ++drawn;
        }
    }
    return drawn;
}

uint16_t vxpe_tilemap_cell(const VxpeTilemap2D* map, int tx, int ty) {
    if (map == nullptr || map->cells == nullptr ||
        tx < 0 || ty < 0 || tx >= map->width || ty >= map->height) {
        return 0;
    }
    return map->cells[(size_t)ty * map->width + (size_t)tx];
}

uint16_t vxpe_tilemap_flags(const VxpeTilemap2D* map, int tx, int ty) {
    if (map == nullptr) return 0;
    if (tx < 0 || ty < 0 || tx >= map->width || ty >= map->height) {
        return map->oob_blocks ? (uint16_t)VXPE_TF_SOLID : (uint16_t)0;
    }
    if (map->flags == nullptr) return 0;
    return map->flags[(size_t)ty * map->width + (size_t)tx];
}

uint16_t vxpe_tilemap_flags_at_px(const VxpeTilemap2D* map, int wx, int wy) {
    if (map == nullptr) return 0;
    return vxpe_tilemap_flags(map, fdiv(wx, map->tile_w), fdiv(wy, map->tile_h));
}

int vxpe_tilemap_blocks_at_px(const VxpeTilemap2D* map, int wx, int wy, uint16_t mask) {
    const uint16_t f = vxpe_tilemap_flags_at_px(map, wx, wy);
    if (mask == 0) mask = VXPE_TF_SOLID;
    return (f & mask) ? 1 : 0;
}

uint16_t vxpe_tilemap_rect_flags(const VxpeTilemap2D* map,
                                 int x0, int y0, int x1, int y1) {
    if (map == nullptr || x1 <= x0 || y1 <= y0) return 0;
    const int tx0 = fdiv(x0, map->tile_w);
    const int tx1 = fdiv(x1 - 1, map->tile_w);
    const int ty0 = fdiv(y0, map->tile_h);
    const int ty1 = fdiv(y1 - 1, map->tile_h);
    uint16_t acc = 0;
    for (int ty = ty0; ty <= ty1; ++ty) {
        for (int tx = tx0; tx <= tx1; ++tx) acc |= vxpe_tilemap_flags(map, tx, ty);
    }
    return acc;
}

int vxpe_tilemap_floor_y(const VxpeTilemap2D* map, int tx, int ty, int local_x) {
    if (map == nullptr) return 0;
    const int bottom = (ty + 1) * map->tile_h;
    const uint16_t flags = vxpe_tilemap_flags(map, tx, ty);
    if (flags & VXPE_TF_SLOPE_UP_R) {
        int lx = local_x;
        if (lx < 0) lx = 0;
        if (lx >= map->tile_w) lx = map->tile_w - 1;
        return bottom - (lx * map->tile_h) / map->tile_w;
    }
    if (flags & VXPE_TF_SLOPE_UP_L) {
        int lx = map->tile_w - 1 - local_x;
        if (lx < 0) lx = 0;
        if (lx >= map->tile_w) lx = map->tile_w - 1;
        return bottom - (lx * map->tile_h) / map->tile_w;
    }
    return bottom;
}

}  /* extern "C" */
