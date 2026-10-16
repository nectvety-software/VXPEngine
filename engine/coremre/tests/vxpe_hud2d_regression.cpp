/*
 * Regression coverage for the HUD layer: plate geometry, gauge fill and damage
 * ghost arithmetic, icon rows, the boss plate state machine, minimap reveal
 * bookkeeping and the text helpers.
 *
 * Every assertion is an exact RGB565 value at an exact pixel, so a change in a
 * fill rule or a segment boundary fails here instead of showing up as a HUD
 * that "looks a bit off" on a handset. Nothing reads host timing.
 */
#include "action2d/VxpHud2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

#define FB_W 240
#define FB_H 320

/* A colour no widget produces, so any untouched pixel is obvious. */
static const uint16_t BG = 0x001Fu;

static uint16_t g_fb[FB_W * FB_H];
static uint16_t g_green_px[8 * 8];
static uint16_t g_red_px[8 * 8];

static void clear_fb(void) {
    int i;
    for (i = 0; i < FB_W * FB_H; ++i) g_fb[i] = BG;
}

static uint16_t at(int x, int y) { return g_fb[y * FB_W + x]; }

static int count_of(uint16_t color) {
    int i, n = 0;
    for (i = 0; i < FB_W * FB_H; ++i) if (g_fb[i] == color) ++n;
    return n;
}

/* Leftmost/rightmost ink and the number of ink pixels on any row, used by the
 * alignment tests. Ink is the default face's own ivory, so the black shadow is
 * not counted and the box is the glyph box. */
static void ink_span(int* out_left, int* out_right, int* out_count) {
    int x, y, left = FB_W, right = -1, n = 0;
    for (y = 0; y < FB_H; ++y) {
        for (x = 0; x < FB_W; ++x) {
            if (at(x, y) != 0xFFB8u) continue;
            ++n;
            if (x < left) left = x;
            if (x > right) right = x;
        }
    }
    *out_left = left;
    *out_right = right;
    *out_count = n;
}

static void make_icon(uint16_t* px, uint16_t color) {
    int i;
    for (i = 0; i < 8 * 8; ++i) px[i] = color;
}

/* ---- plates ------------------------------------------------------------- */

static void test_plate(void) {
    VxpeHudPlate2D plate;
    VxpeRectI r;
    vxpe_hud_plate_default(&plate);
    plate.border_px = 2;
    plate.bevel_px = 1;
    clear_fb();

    /* 20x14 at (5,7): the inner field starts two pixels in, so a probe there
     * must be the bevel or the fill and never the background. */
    r.x = 5; r.y = 7; r.w = 20; r.h = 14;
    vxpe_hud_plate_draw(g_fb, FB_W, FB_H, r, &plate);
    assert(at(5, 7) == plate.frame && at(6, 7) == plate.frame);
    assert(at(24, 13) == plate.frame);           /* bottom-right of the ring */
    assert(at(7, 9) == plate.bevel_hi);          /* bevel top-left corner */
    assert(at(15, 9) == plate.bevel_hi);         /* top edge of the bevel */
    assert(at(7, 13) == plate.bevel_hi);         /* left edge */
    assert(at(22, 18) == plate.bevel_lo);        /* bottom-right corner */
    assert(at(15, 18) == plate.bevel_lo);        /* bottom edge */
    assert(at(22, 13) == plate.bevel_lo);        /* right edge */
    assert(at(12, 13) == plate.inner);           /* field */

    /* inner 0 leaves the field alone, which is how a plate frames the world. */
    plate.inner = 0;
    clear_fb();
    vxpe_hud_plate_draw(g_fb, FB_W, FB_H, r, &plate);
    assert(at(12, 13) == BG);
    assert(at(5, 7) == plate.frame);

    /* Zero thicknesses draw only what they are told. */
    plate.border_px = 0;
    plate.bevel_px = 0;
    plate.inner = vxpe2d_rgb565(40, 44, 60);
    clear_fb();
    vxpe_hud_plate_draw(g_fb, FB_W, FB_H, r, &plate);
    assert(at(5, 7) == plate.inner && at(24, 20) == plate.inner);

    /* Degenerate and off-screen rectangles must not write outside the buffer. */
    r.w = 0;
    vxpe_hud_plate_draw(g_fb, FB_W, FB_H, r, &plate);
    r.x = (int16_t)(FB_W - 3); r.y = (int16_t)(FB_H - 3); r.w = 40; r.h = 40;
    vxpe_hud_plate_draw(g_fb, FB_W, FB_H, r, &plate);
    assert(at(0, 0) == BG);

    /* Portrait: art larger than the field is clipped to the inner box. */
    {
        static uint16_t big[16 * 16];
        VxpeSprite565 art;
        int i, painted = 0;
        for (i = 0; i < 16 * 16; ++i) big[i] = 0xF81Fu;
        art.pixels = big; art.mask = 0; art.width = 16; art.height = 16;
        art.stride = 16; art.opaque = 1;

        VxpeHudPlate2D p2;
        vxpe_hud_plate_default(&p2);
        clear_fb();
        r.x = 100; r.y = 100; r.w = 12; r.h = 12;
        vxpe_hud_portrait_draw(g_fb, FB_W, FB_H, r, &art, &p2, 0xFFFFu, 0);
        for (i = 0; i < FB_W * FB_H; ++i) if (g_fb[i] == 0xF81Fu) ++painted;
        /* Field is 12-2*(1+1) = 8 px square, centred, so exactly 64 pixels of
         * art survive the clip. */
        assert(painted == 64);
        assert(at(100, 100) == p2.frame);
        assert(at(106, 106) == 0xF81Fu);

        /* Neutral tint and full alpha leave the art colour untouched; a tint
         * multiplies it. Without a plate the clip is still the rect, so the
         * over-sized art is cut at its edge rather than spilling out. */
        clear_fb();
        vxpe_hud_portrait_draw(g_fb, FB_W, FB_H, r, &art, 0, 0xFFFFu, 0);
        assert(at(100, 100) == 0xF81Fu);
        assert(at(99, 99) == BG);
        assert(at(112, 112) == BG);
        clear_fb();
        vxpe_hud_portrait_draw(g_fb, FB_W, FB_H, r, &art, 0, 0x07E0u, 0);
        assert(at(100, 100) == vxpe2d_tint565(0xF81Fu, 0x07E0u));
        assert(at(111, 111) == vxpe2d_tint565(0xF81Fu, 0x07E0u));
    }
}

/* ---- gauges ------------------------------------------------------------- */

static void test_gauge_continuous(void) {
    VxpeHudGauge2D g;
    clear_fb();
    vxpe_hud_gauge_init(&g, 20, 40, 40, 6, 100);
    /* Frame on means the content box is inset by one on every side. */
    const int cx = 21, cy = 41, cw = 38;

    vxpe_hud_gauge_set(&g, 100);
    assert(g.value == 100 && g.ghost == 100);
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(cx, cy) == g.color_full && at(cx + cw - 1, cy) == g.color_full);
    assert(at(20, 40) == g.color_frame);          /* ring */
    assert(at(20 + 40 - 1, 40 + 6 - 1) == g.color_frame);

    vxpe_hud_gauge_set(&g, 0);
    /* An empty bar is still ghost-filled until the drain catches up, which is
     * the whole point of the trail. */
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(count_of(g.color_full) == 0);
    assert(at(cx, cy) == g.color_ghost);
    vxpe_hud_gauge_update(&g, 60000);
    assert(g.ghost == 0);
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(cx, cy) == g.color_bg);

    /* value 50 of 100 over 38 px is exactly 19 px. */
    vxpe_hud_gauge_set(&g, 50);
    g.ghost = 50;
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(cx + 18, cy) == g.color_full);
    assert(at(cx + 19, cy) == g.color_bg);

    /* Over-value input clamps instead of painting past the frame. */
    vxpe_hud_gauge_set(&g, 5000);
    assert(g.value == 100);
    /* max_value 0 is refused at init, so a zeroed struct cannot divide by it. */
    VxpeHudGauge2D zero;
    vxpe_hud_gauge_init(&zero, 0, 0, 10, 4, 0);
    assert(zero.max_value == 1);
    vxpe_hud_gauge_set(&zero, 9);
    assert(zero.value == 1);

    /* Mirror fills from the right: same 19 px, opposite end. */
    vxpe_hud_gauge_set(&g, 50);
    g.ghost = 50;
    g.mirror = 1;
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(cx + 18, cy) == g.color_bg);
    assert(at(cx + 19, cy) == g.color_full);
    assert(at(cx + cw - 1, cy) == g.color_full);
    g.mirror = 0;
}

static void test_gauge_ghost(void) {
    VxpeHudGauge2D g;
    clear_fb();
    vxpe_hud_gauge_init(&g, 20, 40, 40, 6, 100);
    const int cx = 21, cy = 41;

    /* init starts full, so damage leaves the ghost behind at the old line. */
    vxpe_hud_gauge_set(&g, 30);
    assert(g.ghost == 100 && g.value == 30);

    /* A frame mid-drain: 11 px of health (38*30/100) and the ghost to 50. */
    g.ghost = 50;
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(cx + 10, cy) == g.color_full);
    assert(at(cx + 11, cy) == g.color_ghost);
    assert(at(cx + 18, cy) == g.color_ghost);
    assert(at(cx + 19, cy) == g.color_bg);

    /* 200 units/s at 33 ms is 6.6 units: 6 now, the rest carried. */
    g.ghost = 50;
    g.ghost_acc = 0;
    vxpe_hud_gauge_update(&g, 33);
    assert(g.ghost == 44 && g.ghost_acc == 153600);
    vxpe_hud_gauge_update(&g, 33);
    assert(g.ghost == 37 && g.ghost_acc == 51200);
    /* A stalled frame clamps at value instead of running past it. */
    vxpe_hud_gauge_update(&g, 60000);
    assert(g.ghost == g.value && g.ghost_acc == 0);

    /* The carry is why a rate below one unit per frame still moves: 1 unit/s
     * needs 31 frames of 33 ms before the first whole unit crosses. */
    g.ghost = 100;
    g.ghost_acc = 0;
    g.ghost_rate_q8 = 256;
    for (int i = 0; i < 30; ++i) vxpe_hud_gauge_update(&g, 33);
    assert(g.ghost == 100);
    vxpe_hud_gauge_update(&g, 33);
    assert(g.ghost == 99);
    g.ghost_rate_q8 = 200 << 8;

    /* Healing past the ghost drags it up instead of leaving a red scar. */
    g.ghost_rate_q8 = 0; /* snap */
    g.ghost = 12;
    vxpe_hud_gauge_set(&g, 80);
    assert(g.ghost == 80);
    vxpe_hud_gauge_update(&g, 16);
    assert(g.ghost == g.value);

    /* Damage keeps the trail above the new line; only the drain closes it. */
    vxpe_hud_gauge_set(&g, 70);
    assert(g.value == 70 && g.ghost == 80);
    g.ghost_rate_q8 = 200 << 8;
    vxpe_hud_gauge_update(&g, 500);
    assert(g.ghost == 70 && g.ghost_acc == 0);
    g.ghost = 60;
    vxpe_hud_gauge_set(&g, 55);
    assert(g.ghost == 60 && g.value == 55);
    vxpe_hud_gauge_update(&g, 500);
    assert(g.ghost == 55);
}

static void test_gauge_segments(void) {
    VxpeHudGauge2D g;
    clear_fb();
    vxpe_hud_gauge_init(&g, 100, 100, 42, 6, 100);
    g.segments = 4;
    g.gap_px = 2;
    /* content 40 px wide, 4 cells with 3 gaps -> 8 px cells at x 101, 111,
     * 121, 131. */
    vxpe_hud_gauge_set(&g, 60);
    g.ghost = 60;
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(101, 103) == g.color_full);
    assert(at(108, 103) == g.color_full);        /* cell 0 full */
    assert(at(109, 103) == g.color_bg);          /* gap */
    assert(at(110, 103) == g.color_bg);
    assert(at(121 + 2, 103) == g.color_full);    /* cell 2 partial: 8*10/25 = 3 */
    assert(at(121 + 3, 103) == g.color_bg);
    assert(at(131, 103) == g.color_bg);          /* cell 3 empty */

    /* An uneven max/segments split must still cover exactly the whole bar at
     * full: cells [0,3) [3,6) [6,10) for max 10, segments 3. Content is 30 px
     * wide, so the cells are 9 px at x 11, 21 and 31 with 1 px gaps. */
    vxpe_hud_gauge_init(&g, 10, 10, 32, 5, 10);
    g.segments = 3;
    g.gap_px = 1;
    vxpe_hud_gauge_set(&g, 10);
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(11, 12) == g.color_full && at(19, 12) == g.color_full);
    assert(at(21, 12) == g.color_full && at(29, 12) == g.color_full);
    assert(at(31, 12) == g.color_full && at(39, 12) == g.color_full);
    assert(at(20, 12) == g.color_bg && at(30, 12) == g.color_bg);
    /* value 6 fills the first two cells and leaves the third empty. */
    vxpe_hud_gauge_set(&g, 6);
    g.ghost = 6; /* the trail is the next test's subject, not this one's */
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(19, 12) == g.color_full);
    assert(at(29, 12) == g.color_full);
    assert(at(31, 12) == g.color_bg);
    /* value 4 lands inside cell 1: [3,6) covered 1 of 2 units -> 3 px. */
    vxpe_hud_gauge_set(&g, 4);
    g.ghost = 4;
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(21 + 2, 12) == g.color_full);
    assert(at(21 + 3, 12) == g.color_bg);
    assert(at(11, 12) == g.color_full);

    /* A bar too thin to hold its cells draws nothing rather than a divide by
     * zero or a negative width fill. */
    g.segments = 200;
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(count_of(g.color_full) == 0);
}

static void test_gauge_low_and_flash(void) {
    VxpeHudGauge2D g;
    clear_fb();
    vxpe_hud_gauge_init(&g, 10, 10, 40, 6, 100);
    g.low_at = 25;
    vxpe_hud_gauge_set(&g, 30);
    assert(!vxpe_hud_gauge_is_low(&g));
    vxpe_hud_gauge_set(&g, 25);
    assert(vxpe_hud_gauge_is_low(&g));           /* boundary is inclusive */
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(12, 13) == g.color_low);
    assert(count_of(g.color_full) == 0);

    vxpe_hud_gauge_flash(&g, 100);
    assert(g.flash_ms == 100);
    vxpe_hud_gauge_flash(&g, 40);                /* never shortened */
    assert(g.flash_ms == 100);
    vxpe_hud_gauge_update(&g, 50);
    assert(g.flash_ms == 50);
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(10, 10) == 0xFFFFu);
    vxpe_hud_gauge_update(&g, 50);
    assert(g.flash_ms == 0);
    clear_fb();
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &g);
    assert(at(10, 10) == g.color_frame);
}

/* ---- icon rows ---------------------------------------------------------- */

static void test_icon_row(void) {
    VxpeSprite565 full, empty;
    VxpeHudIconRow2D row;
    make_icon(g_green_px, 0x07E0u);
    make_icon(g_red_px, 0xF800u);
    full.pixels = g_green_px; full.mask = 0; full.width = 8; full.height = 8;
    full.stride = 8; full.opaque = 1;
    empty.pixels = g_red_px; empty.mask = 0; empty.width = 8; empty.height = 8;
    empty.stride = 8; empty.opaque = 1;

    clear_fb();
    vxpe_hud_icon_row_init(&row, &full, &empty, 30, 30, 5);
    vxpe_hud_icon_row_set(&row, 2);
    assert(vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row) == 5);
    assert(at(32, 32) == 0x07E0u);               /* icon 0 */
    assert(at(42, 32) == 0x07E0u);               /* icon 1 at +10 px pitch */
    assert(at(52, 32) == 0xF800u);               /* icon 2 empty */
    assert(at(72, 32) == 0xF800u);               /* icon 4 */
    assert(at(38, 32) == BG);                    /* the 2 px gap stays clear */

    /* value above max shows max; value 0 shows the whole empty row. */
    vxpe_hud_icon_row_set(&row, 999);
    clear_fb();
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row);
    assert(at(72, 32) == 0x07E0u);
    vxpe_hud_icon_row_set(&row, 0);
    clear_fb();
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row);
    assert(count_of(0x07E0u) == 0 && count_of(0xF800u) == 5 * 64);

    /* Wrapping: two per row, so icon 2 starts the second row. */
    row.per_row = 2;
    vxpe_hud_icon_row_set(&row, 5);
    clear_fb();
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row);
    assert(at(32, 32) == 0x07E0u && at(42, 32) == 0x07E0u);
    assert(at(52, 32) == BG);                    /* row 0 is full at two */
    assert(at(32, 40) == 0x07E0u);               /* pitch_y = 8 + 2 */
    assert(at(42, 40) == 0x07E0u);
    assert(at(32, 50) == 0x07E0u);               /* the fifth starts row 2 */
    assert(at(42, 50) == BG);

    /* grow keeps a right-hand HUD marching leftward from x. */
    row.per_row = 0;
    row.grow = 1;
    vxpe_hud_icon_row_set(&row, 1);
    clear_fb();
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row);
    assert(at(37, 32) == 0x07E0u);               /* col 0 stays anchored at x */
    assert(at(22, 32) == 0xF800u);               /* col 1 grows leftward */
    assert(at(2, 32) == 0xF800u);                /* col 3 lands exactly at x = 0 */

    /* No empty art: the slot is a tinted silhouette of the full sprite. */
    row.grow = 0;
    row.empty = 0;
    row.color_empty = vxpe2d_rgb565(52, 44, 68);
    vxpe_hud_icon_row_set(&row, 1);
    clear_fb();
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row);
    assert(at(32, 32) == 0x07E0u);
    assert(at(42, 32) == vxpe2d_tint565(0x07E0u, row.color_empty));

    /* Explicit pitch beats the sprite-size default. */
    row.empty = &empty;
    row.pitch_x = 12;
    row.pitch_y = 12;
    clear_fb();
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row);
    assert(at(32 + 12, 32) == 0xF800u);
    assert(at(32 + 24, 32) == 0xF800u);

    /* max 0 and a missing sprite draw nothing at all. */
    row.max = 0;
    assert(vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row) == 0);
    row.max = 3;
    row.full = 0;
    assert(vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &row) == 0);
}

/* ---- boss plate --------------------------------------------------------- */

static void test_boss_plate(void) {
    static VxpeHudBossPlate2D p;
    clear_fb();
    vxpe_hud_boss_init(&p, FB_W, FB_H, 100);
    assert(p.state == 0);
    /* Hidden: a draw must leave the buffer exactly as it was. */
    int before = count_of(BG);
    vxpe_hud_boss_draw(g_fb, FB_W, FB_H, &p, 0);
    assert(count_of(BG) == before && p.state == 0);

    vxpe_hud_boss_show(&p, "BLOOD MOON", 80);
    assert(p.state == 1);
    assert(p.slide_y == p.plate_y - 40);
    /* 250 px/s: four 40 ms steps cover the 40 px of travel. */
    vxpe_hud_boss_update(&p, 40);
    assert(p.slide_y == p.plate_y - 30);
    vxpe_hud_boss_update(&p, 40);
    vxpe_hud_boss_update(&p, 40);
    vxpe_hud_boss_update(&p, 40);
    assert(p.slide_y == p.plate_y && p.state == 2);
    assert(p.hide_ms == p.show_ms);

    /* Layout is derived from the face: with the default 7 px tall glyphs the
     * bar starts nine pixels below plate_y. */
    clear_fb();
    vxpe_hud_boss_draw(g_fb, FB_W, FB_H, &p, 0);
    const int gy = p.plate_y + 9;
    const int cx = p.gauge.x + 1, cw = p.gauge.w - 2;
    const int filled = cw * 80 / 100;             /* hp 80 of max 100 */
    assert(at(cx + filled - 1, gy + 5) == p.gauge.color_full);
    /* show() set the health down from a full bar, so the trail is still there
     * and the plate drains it like any other gauge. */
    assert(at(cx + filled, gy + 5) == p.gauge.color_ghost);
    assert(at(p.gauge.x - 10, gy + 5) == BG);     /* left of the plate */
    assert(count_of(0xFFB8u) > 0);                /* the name is on the plate */

    /* A bigger face pushes the bar down instead of colliding with the name. */
    VxpeFontStyle display;
    vxpe_font_style_default(&display);
    display.font_id = VXPE_FONT_DISPLAY;
    display.scale = 2;
    const int dh = vxpe_font_height(&display);
    clear_fb();
    vxpe_hud_boss_draw(g_fb, FB_W, FB_H, &p, &display);
    assert(at(cx + filled - 1, p.plate_y - 3 + 2 + dh + 3 + 5)
           == p.gauge.color_full);

    /* Damage: bar moves, flash armed, hold timer restarted. */
    vxpe_hud_boss_update(&p, 1000);
    assert(p.hide_ms == p.show_ms - 1000);
    vxpe_hud_boss_set_hp(&p, 40);
    assert(p.gauge.value == 40 && p.gauge.ghost == 80);
    assert(p.gauge.flash_ms == 90);
    assert(p.hide_ms == p.show_ms);

    /* Idle out, fade, and stop drawing. */
    vxpe_hud_boss_update(&p, p.show_ms);
    assert(p.state == 3);
    vxpe_hud_boss_update(&p, 100);
    assert(p.alpha == 155);
    const uint16_t dimmed = vxpe2d_tint565(p.gauge.color_full,
                                           vxpe2d_rgb565(155, 155, 155));
    clear_fb();
    /* 40 of 100 over the bar's content width, right end of the fill. */
    vxpe_hud_boss_draw(g_fb, FB_W, FB_H, &p, 0);
    assert(count_of(dimmed) > 0);
    assert(count_of(p.gauge.color_full) == 0);   /* never drawn at full strength */
    vxpe_hud_boss_update(&p, 255);
    assert(p.alpha == 0 && p.state == 0);

    /* Damage while retreating pulls the plate back up. */
    vxpe_hud_boss_show(&p, 0, 60);
    for (int i = 0; i < 20 && p.state == 1; ++i) vxpe_hud_boss_update(&p, 40);
    assert(p.state == 2);
    vxpe_hud_boss_hide(&p);
    assert(p.state == 3);
    vxpe_hud_boss_update(&p, 50);
    vxpe_hud_boss_set_hp(&p, 30);
    assert(p.state == 2 && p.alpha == 255);
    /* The name survives a NULL show, and a hidden plate tracks hp silently. */
    vxpe_hud_boss_hide(&p);
    vxpe_hud_boss_update(&p, 4000);
    assert(p.state == 0);
    vxpe_hud_boss_set_hp(&p, 5);
    assert(p.gauge.value == 5 && p.gauge.flash_ms == 0);
    vxpe_hud_boss_show(&p, 0, 5);
    assert(strncmp(p.name, "BLOOD MOON", VXPE_BOSS_PLATE_NAME_MAX) == 0);

    /* An over-long name is truncated with a terminator, never past the array. */
    char long_name[64];
    memset(long_name, 'X', sizeof(long_name) - 1);
    long_name[sizeof(long_name) - 1] = 0;
    vxpe_hud_boss_show(&p, long_name, 5);
    assert(p.name[VXPE_BOSS_PLATE_NAME_MAX - 1] == 0);
    for (int i = 0; i < VXPE_BOSS_PLATE_NAME_MAX - 1; ++i) assert(p.name[i] == 'X');

    /* NULL and zero-size guards. */
    vxpe_hud_boss_show(0, "x", 1);
    vxpe_hud_boss_update(0, 33);
    clear_fb();
    before = count_of(BG);
    vxpe_hud_boss_draw(g_fb, FB_W, FB_H, 0, 0);
    assert(count_of(BG) == before);
}

/* ---- minimap ------------------------------------------------------------ */

static void test_minimap(void) {
    /* 4x3 rooms; (0,0) is void so a marked void cell must stay bg. */
    static const uint8_t rooms[12] = { 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1 };
    static const uint8_t tags[12] = { 0, 0, VXPE_MM_BOSS, 0, VXPE_MM_SAVE, 0,
                                      0, 0, 0, VXPE_MM_SHOP, 0, 0 };
    VxpeHudMinimap2D mm;
    clear_fb();
    vxpe_hud_minimap_init(&mm, rooms, tags, 4, 3, 4, 200, 4);
    /* 16x12 of bg with a 1 px frame ring just outside it. */
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, -1, -1);
    assert(at(202, 6) == mm.color_bg);
    assert(at(199, 3) == mm.color_edge);
    assert(at(216, 16) == mm.color_edge);
    assert(vxpe_hud_minimap_seen(&mm, 1, 1) == 0);

    vxpe_hud_minimap_mark(&mm, 1, 1);
    vxpe_hud_minimap_mark(&mm, 2, 0);   /* boss */
    vxpe_hud_minimap_mark(&mm, 4, 0);   /* out of range */
    vxpe_hud_minimap_mark(&mm, -1, 0);
    assert(vxpe_hud_minimap_seen(&mm, 2, 0) == 1);
    assert(vxpe_hud_minimap_seen(&mm, 4, 0) == 0);
    clear_fb();
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, -1, -1);
    /* Room (1,1) is id 1 at x 200+4, y 4+4, inset 1 -> filled. */
    assert(at(205, 9) == mm.color_room);
    /* Boss cell (2,0) shows the room fill with a 1 px mark at its centre. */
    assert(at(210, 6) == mm.color_boss);
    assert(at(209, 5) == mm.color_room);
    /* The pip is 1 px inside a 4 px cell, centred, and sits on top. */
    clear_fb();
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, 1, 1);
    assert(at(205, 9) == mm.color_here);
    assert(at(206, 10) == mm.color_room);
    /* An id-0 room never lights up even when marked. */
    vxpe_hud_minimap_mark(&mm, 0, 0);
    clear_fb();
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, -1, -1);
    assert(at(202, 6) == mm.color_bg);

    /* Save and shop marks use their own colours. Tags index the same array as
     * rooms, so in this 4-wide table idx 4 is (0,1) = SAVE and idx 9 is
     * (1,2) = SHOP. */
    vxpe_hud_minimap_mark(&mm, 0, 1);
    clear_fb();
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, -1, -1);
    assert(at(202, 10) == mm.color_save);         /* cell (0,1) centre */
    assert(at(201, 9) == mm.color_room);
    vxpe_hud_minimap_mark(&mm, 1, 2);
    clear_fb();
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, -1, -1);
    assert(at(206, 14) == mm.color_shop);         /* cell (1,2) centre */

    /* tags NULL is legal; so is an oversized map, which zeroes instead of
     * overflowing the visited bitset. */
    vxpe_hud_minimap_init(&mm, rooms, 0, 4, 3, 4, 0, 0);
    vxpe_hud_minimap_mark(&mm, 1, 1);
    clear_fb();
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, 1, 1);
    assert(at(6, 6) == mm.color_room);           /* id 1 at cell (1,1), 4 px */
    assert(at(5, 5) == mm.color_here);           /* pip in the same cell */

    VxpeHudMinimap2D huge;
    vxpe_hud_minimap_init(&huge, rooms, 0, VXPE_MINIMAP_W_MAX + 1, 1, 4, 0, 0);
    assert(huge.width == 0 && huge.rooms == 0);
    vxpe_hud_minimap_mark(&huge, 0, 0);          /* must not touch memory */
    clear_fb();
    int before = count_of(BG);
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &huge, 0, 0);
    assert(count_of(BG) == before);
    assert(!vxpe_hud_minimap_seen(&huge, 0, 0));

    /* cell clamps to 2..8 so a 40-wide map still fits 240 px. */
    vxpe_hud_minimap_init(&mm, rooms, 0, 4, 3, 100, 0, 0);
    assert(mm.cell == 8);
    vxpe_hud_minimap_init(&mm, rooms, 0, 4, 3, 1, 0, 0);
    assert(mm.cell == 2);
}

/* ---- text --------------------------------------------------------------- */

static void test_format_int(void) {
    char buf[16];
    assert(vxpe_hud_format_int(buf, sizeof(buf), 7, 3) == 3);
    assert(strcmp(buf, "007") == 0);
    assert(vxpe_hud_format_int(buf, sizeof(buf), 1234, 1) == 4);
    assert(strcmp(buf, "1234") == 0);
    assert(vxpe_hud_format_int(buf, sizeof(buf), 0, 2) == 2);
    assert(strcmp(buf, "00") == 0);
    assert(vxpe_hud_format_int(buf, sizeof(buf), -45, 3) == 4);
    assert(strcmp(buf, "-045") == 0);
    assert(vxpe_hud_format_int(buf, sizeof(buf), -2147483647 - 1, 1) == 11);
    assert(strcmp(buf, "-2147483648") == 0);
    /* A too-small buffer keeps the terminator and reports what it wrote. */
    assert(vxpe_hud_format_int(buf, 4, 12345, 1) == 3);
    assert(strcmp(buf, "123") == 0);
    assert(vxpe_hud_format_int(buf, 1, 999, 1) == 0);
    assert(buf[0] == 0);
    assert(vxpe_hud_format_int(0, 8, 1, 1) == 0);
    assert(vxpe_hud_format_int(buf, 0, 1, 1) == 0);
}

static void test_text_alignment(void) {
    VxpeFontStyle style;
    vxpe_font_style_default(&style);
    const char* text = "HEARTS 12";
    const int w = vxpe_font_measure(text, &style);
    assert(w > 0);

    clear_fb();
    vxpe_hud_text_center(g_fb, FB_W, FB_H, 120, 100, text, &style);
    int left, right, count;
    ink_span(&left, &right, &count);
    assert(count > 0);
    /* The ivory ink box is the glyph box, so its centre is the anchor within a
     * pixel of rounding, and its width is the measured logical width. */
    assert((left + right) / 2 == 120);
    assert(right - left + 1 == w);

    clear_fb();
    vxpe_hud_text_right(g_fb, FB_W, FB_H, 200, 120, text, &style);
    ink_span(&left, &right, &count);
    assert(count > 0);
    assert(right == 199);
    assert(right - left + 1 == w);

    /* Empty and NULL text draw nothing. */
    clear_fb();
    vxpe_hud_text_center(g_fb, FB_W, FB_H, 10, 10, "", &style);
    vxpe_hud_text_right(g_fb, FB_W, FB_H, 10, 10, 0, &style);
    assert(count_of(BG) == FB_W * FB_H);
}

static void test_widget_null_safety(void) {
    VxpeHudGauge2D g;
    VxpeHudIconRow2D row;
    VxpeHudPlate2D plate;
    VxpeRectI r;
    r.x = 0; r.y = 0; r.w = 4; r.h = 4;
    vxpe_hud_plate_default(&plate);
    vxpe_hud_gauge_init(&g, 0, 0, 4, 4, 10);
    vxpe_hud_icon_row_init(&row, 0, 0, 0, 0, 3);
    clear_fb();
    vxpe_hud_plate_draw(0, FB_W, FB_H, r, &plate);
    vxpe_hud_plate_draw(g_fb, FB_W, FB_H, r, 0);
    vxpe_hud_gauge_draw(0, FB_W, FB_H, &g);
    vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, 0);
    vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, 0);
    vxpe_hud_gauge_set(0, 5);
    vxpe_hud_gauge_update(0, 33);
    vxpe_hud_gauge_flash(0, 10);
    vxpe_hud_icon_row_set(0, 2);
    vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, 0, 0, 0);
    vxpe_hud_minimap_mark(0, 0, 0);
    vxpe_hud_portrait_draw(g_fb, FB_W, FB_H, r, 0, &plate, 0xFFFFu, 0);
    assert(count_of(BG) == FB_W * FB_H);
    assert(!vxpe_hud_gauge_is_low(0));
    assert(!vxpe_hud_minimap_seen(0, 0, 0));
}

/* One composed HUD, as the game frame will draw it: plate + portrait + hearts +
 * two gauges + minimap + boss plate. Proves the pieces coexist in one frame
 * without overwriting each other or the buffer bounds. */
static void test_composed_hud(void) {
    VxpeSprite565 full, empty, portrait;
    static uint16_t face_px[24 * 24];
    VxpeHudGauge2D hp, mp;
    VxpeHudIconRow2D hearts;
    VxpeHudMinimap2D mm;
    static VxpeHudBossPlate2D boss;
    static const uint8_t rooms[6] = { 1, 1, 1, 1, 0, 1 };
    int i;

    make_icon(g_green_px, 0x07E0u);
    make_icon(g_red_px, 0xF800u);
    full.pixels = g_green_px; full.mask = 0; full.width = 8; full.height = 8;
    full.stride = 8; full.opaque = 1;
    empty.pixels = g_red_px; empty.mask = 0; empty.width = 8; empty.height = 8;
    empty.stride = 8; empty.opaque = 1;
    for (i = 0; i < 24 * 24; ++i) face_px[i] = 0b11111'101010'00000u;
    portrait.pixels = face_px; portrait.mask = 0;
    portrait.width = 24; portrait.height = 24; portrait.stride = 24; portrait.opaque = 1;

    clear_fb();
    VxpeHudPlate2D plate;
    vxpe_hud_plate_default(&plate);
    VxpeRectI pr;
    pr.x = 4; pr.y = 4; pr.w = 28; pr.h = 28;
    vxpe_hud_portrait_draw(g_fb, FB_W, FB_H, pr, &portrait, &plate, 0xFFFFu, 0);
    assert(at(18, 18) == 0b11111'101010'00000u);

    vxpe_hud_gauge_init(&hp, 36, 8, 120, 8, 100);
    vxpe_hud_gauge_set(&hp, 55);
    hp.ghost = 100;
    /* A slow bleed so the ghost is still mid-drain when the frame loop ends. */
    hp.ghost_rate_q8 = 2560; /* 10 units/s */
    vxpe_hud_gauge_init(&mp, 36, 20, 90, 6, 100);
    mp.color_full = vxpe2d_rgb565(48, 96, 200);
    mp.ghost_rate_q8 = 0;
    vxpe_hud_gauge_set(&mp, 40);
    vxpe_hud_gauge_update(&mp, 33);
    assert(mp.ghost == 40);

    vxpe_hud_icon_row_init(&hearts, &full, &empty, 36, 28, 20);
    hearts.per_row = 10; /* two rows so the row stays inside 240 px */
    vxpe_hud_icon_row_set(&hearts, 14);

    vxpe_hud_minimap_init(&mm, rooms, 0, 3, 2, 6, 200, 240);
    vxpe_hud_minimap_mark(&mm, 0, 0);
    vxpe_hud_minimap_mark(&mm, 2, 1);

    vxpe_hud_boss_init(&boss, FB_W, FB_H, 200);
    vxpe_hud_boss_show(&boss, "COUNTRESS", 200);

    for (int frame = 0; frame < 30; ++frame) {
        vxpe_hud_gauge_update(&hp, 33);
        vxpe_hud_boss_update(&boss, 33);
        clear_fb();
        vxpe_hud_portrait_draw(g_fb, FB_W, FB_H, pr, &portrait, &plate, 0xFFFFu, 0);
        vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &hp);
        vxpe_hud_gauge_draw(g_fb, FB_W, FB_H, &mp);
        vxpe_hud_icon_row_draw(g_fb, FB_W, FB_H, &hearts);
        vxpe_hud_minimap_draw(g_fb, FB_W, FB_H, &mm, 2, 1);
        vxpe_hud_boss_draw(g_fb, FB_W, FB_H, &boss, 0);
        VxpeFontStyle s;
        vxpe_font_style_default(&s);
        vxpe_hud_text_right(g_fb, FB_W, FB_H, 198, 8, "MP", &s);
    }
    /* The ghost bled 9 of its 45 units: 10/s over 30 frames of 33 ms. */
    assert(hp.ghost == 91 && hp.ghost_acc == 230400);
    assert(at(36 + 1 + 117, 9) == hp.color_bg);
    /* 14 hearts of 20 in two rows of ten: slot 14 starts the second row. */
    assert(at(36 + 4 * 10 + 4, 28 + 10 + 2) == 0xF800u);
    assert(at(36 + 4, 28 + 2) == 0x07E0u);
    assert(at(36 + 9 * 10 + 4, 28 + 2) == 0x07E0u);   /* the tenth full heart */
    assert(at(36 + 9 * 10 + 4, 38 + 2) == 0xF800u);   /* slot 19 empty */
    /* Minimap bottom-right room revealed and occupied. */
    assert(at(200 + 2 * 6 + 3, 240 + 6 + 3) == mm.color_here);
    printf("hud: composed frame ink %d px, ghost hp=%u/%u\n",
           FB_W * FB_H - count_of(BG), hp.value, hp.ghost);
}

int main(void) {
    test_widget_null_safety();
    test_plate();
    test_gauge_continuous();
    test_gauge_ghost();
    test_gauge_segments();
    test_gauge_low_and_flash();
    test_icon_row();
    test_boss_plate();
    test_minimap();
    test_format_int();
    test_text_alignment();
    test_composed_hud();
    printf("vxpe_hud2d_regression: all assertions passed\n");
    return 0;
}
