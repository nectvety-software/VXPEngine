/* gfx.c - software blitter for RGB565 layer buffer + 1-bit sprite masks */
#include "vmgraph.h"
#include "vmchset.h"
#include <string.h>

#include "gfx.h"
#include "game.h"

#define HDR 8 /* .raw header size */

static VMUINT16* fb;
static int fbw, fbh;

void gfx_set_fb(VMUINT8* buf, int w, int h) { fb = (VMUINT16*)buf; fbw = w; fbh = h; }

void gfx_clear(VMUINT16 c) {
    int n = fbw * fbh, i;
    for (i = 0; i < n; i++) fb[i] = c;
}

void gfx_px(int x, int y, VMUINT16 c) {
    x += g_ox; y += g_oy;
    if (x < 0 || y < 0 || x >= fbw || y >= fbh) return;
    fb[y * fbw + x] = c;
}

void gfx_fill(int x, int y, int w, int h, VMUINT16 c) {
    int x0, y0, x1, y1, i, j;
    x += g_ox; y += g_oy;
    x0 = x < 0 ? 0 : x; y0 = y < 0 ? 0 : y;
    x1 = x + w > fbw ? fbw : x + w; y1 = y + h > fbh ? fbh : y + h;
    for (j = y0; j < y1; j++) {
        VMUINT16* row = fb + j * fbw;
        for (i = x0; i < x1; i++) row[i] = c;
    }
}

void gfx_frame(int x, int y, int w, int h, VMUINT16 c) {
    gfx_fill(x, y, w, 1, c); gfx_fill(x, y + h - 1, w, 1, c);
    gfx_fill(x, y, 1, h, c); gfx_fill(x + w - 1, y, 1, h, c);
}

void gfx_blit_op(int id, int x, int y) {
    sprite_t* s = spr(id);
    VMUINT16* px = (VMUINT16*)(s->data + HDR);
    int x0, y0, x1, y1, i, j;
    x += g_ox; y += g_oy;
    x0 = x < 0 ? -x : 0; y0 = y < 0 ? -y : 0;
    x1 = (x + s->w > fbw) ? fbw - x : s->w;
    y1 = (y + s->h > fbh) ? fbh - y : s->h;
    if (x0 >= x1 || y0 >= y1) return;
    for (j = y0; j < y1; j++) {
        VMUINT16* dst = fb + (j + y) * fbw + x;
        VMUINT16* src = px + j * s->w;
        for (i = x0; i < x1; i++) dst[i] = src[i];
    }
}

void gfx_blit(int id, int x, int y, int flip) {
    sprite_t* s = spr(id);
    VMUINT16* px = (VMUINT16*)(s->data + HDR);
    VMUINT8* mask = s->data + HDR + s->w * s->h * 2;
    int x0, y0, x1, y1, i, j;
    x += g_ox; y += g_oy;
    x0 = x < 0 ? -x : 0; y0 = y < 0 ? -y : 0;
    x1 = (x + s->w > fbw) ? fbw - x : s->w;
    y1 = (y + s->h > fbh) ? fbh - y : s->h;
    if (x0 >= x1 || y0 >= y1) return;
    for (j = y0; j < y1; j++) {
        VMUINT16* dst = fb + (j + y) * fbw;
        VMUINT16* src = px + j * s->w;
        VMUINT8* mrow = mask + (j * s->w) / 8;
        for (i = x0; i < x1; i++) {
            int o = j * s->w + i;
            if (mrow[o >> 3] & (0x80 >> (o & 7)))
                dst[i + x] = src[flip ? (s->w - 1 - i) : i];
        }
    }
}

void gfx_blit_bright(int id, int x, int y, int flip, int boost) {
    /* blit with per-channel brightness boost — keeps dark sprites readable
       on the dark dungeon backdrop (player, ground, ladder) */
    sprite_t* s = spr(id);
    VMUINT16* px = (VMUINT16*)(s->data + HDR);
    VMUINT8* mask = s->data + HDR + s->w * s->h * 2;
    int x0, y0, x1, y1, i, j;
    x += g_ox; y += g_oy;
    x0 = x < 0 ? -x : 0; y0 = y < 0 ? -y : 0;
    x1 = (x + s->w > fbw) ? fbw - x : s->w;
    y1 = (y + s->h > fbh) ? fbh - y : s->h;
    if (x0 >= x1 || y0 >= y1) return;
    for (j = y0; j < y1; j++) {
        VMUINT16* dst = fb + (j + y) * fbw;
        VMUINT16* src = px + j * s->w;
        for (i = x0; i < x1; i++) {
            int o = j * s->w + i, r, g, b;
            if (!(mask[o >> 3] & (0x80 >> (o & 7)))) continue;
            r = ((src[o] >> 11) & 31) + boost; if (r > 31) r = 31;
            g = ((src[o] >> 5) & 63) + boost * 2; if (g > 63) g = 63;
            b = (src[o] & 31) + boost; if (b > 31) b = 31;
            dst[i + x] = (VMUINT16)((r << 11) | (g << 5) | b);
        }
    }
}

void gfx_blit_scaled(int id, int x, int y, int w, int h, int flip) {
    sprite_t* s = spr(id);
    VMUINT16* px = (VMUINT16*)(s->data + HDR);
    VMUINT8* mask = s->data + HDR + s->w * s->h * 2;
    int i, j;
    for (j = 0; j < h; j++) {
        int sy = j * s->h / h;
        for (i = 0; i < w; i++) {
            int sx = i * s->w / w, o = sy * s->w + sx;
            if (s->opaque || (mask[o >> 3] & (0x80 >> (o & 7)))) {
                int dx = flip ? (x + w - 1 - i) : (x + i);
                gfx_px(dx, y + j, px[o]);
            }
        }
    }
}

void gfx_blit_scaled_bright(int id, int x, int y, int w, int h, int flip, int boost) {
    sprite_t* s = spr(id);
    VMUINT16* px = (VMUINT16*)(s->data + HDR);
    VMUINT8* mask = s->data + HDR + s->w * s->h * 2;
    int i, j;
    for (j = 0; j < h; j++) {
        int sy = j * s->h / h;
        for (i = 0; i < w; i++) {
            int sx = i * s->w / w, o = sy * s->w + sx, r, g, b;
            if (!(s->opaque || (mask[o >> 3] & (0x80 >> (o & 7))))) continue;
            r = ((px[o] >> 11) & 31) + boost; if (r > 31) r = 31;
            g = ((px[o] >> 5) & 63) + boost * 2; if (g > 63) g = 63;
            b = (px[o] & 31) + boost; if (b > 31) b = 31;
            gfx_px(flip ? (x + w - 1 - i) : (x + i), y + j, (VMUINT16)((r << 11) | (g << 5) | b));
        }
    }
}

void gfx_tint(int id, int x, int y, int flip, VMUINT16 tint) {
    sprite_t* s = spr(id);
    VMUINT8* mask = s->data + HDR + s->w * s->h * 2;
    int i, j;
    for (j = 0; j < s->h; j++)
        for (i = 0; i < s->w; i++) {
            int o = j * s->w + i;
            if (mask[o >> 3] & (0x80 >> (o & 7)))
                gfx_px(flip ? (x + s->w - 1 - i) : (x + i), y + j, tint);
        }
}

static VMWCHAR wtmp[128];
void gfx_text(int x, int y, const char* s, VMUINT16 c) {
    int n = strlen(s);
    if (n <= 0) return;
    if (n > 120) n = 120;
    vm_ascii_to_ucs2(wtmp, sizeof(wtmp), (VMSTR)s);
    vm_graphic_textout((VMUINT8*)fb, x + g_ox, y + g_oy, wtmp, n, c);
}

int gfx_text_w(const char* s) {
    int n = strlen(s);
    vm_ascii_to_ucs2(wtmp, sizeof(wtmp), (VMSTR)s);
    return vm_graphic_get_string_width(wtmp);
}

void gfx_text_c(int cx, int y, const char* s, VMUINT16 c) {
    gfx_text(cx - gfx_text_w(s) / 2, y, s, c);
}

void gfx_bar(int x, int y, int w, int h, int ratio, VMUINT16 fill, VMUINT16 back) {
    int fw;
    if (ratio < 0) ratio = 0;
    if (ratio > 100) ratio = 100;
    fw = (w - 2) * ratio / 100;
    gfx_fill(x, y, w, h, C_BLACK);
    gfx_fill(x + 1, y + 1, w - 2, h - 2, back);
    if (fw > 0) gfx_fill(x + 1, y + 1, fw, h - 2, fill);
    gfx_frame(x, y, w, h, RGB(200, 200, 210));
}
