/* TacticsVanguard2D - 240x320 turn-based tactics sample for VXPEngine/coremre.
 *
 * The reference is a Fire-Emblem-style 16-px tactical map: yellow-green grass,
 * tan roads, clumpy pines, faceted mountains with snow peaks, a river with a
 * dithered sand shore, golden keeps and 16x26 cel-outlined knights that overflow
 * their tile upward. Selecting a unit paints its move range as a hatched field
 * with a chunky ivory path arrow, confirming the move opens a parchment action
 * card, and attacking slides in a skewed cut-in band before damage numbers and
 * HP bars resolve. 240/16 is exact, so the map needs no scaling and every tile
 * edge lands on a pixel boundary.
 *
 * The clip has no title or menu, so the splash and menu screens reuse the map's
 * own language: the battlefield stays live behind a scrim, the army crest is the
 * emblem, and parchment plus gold mark anything the player can act on.
 *
 * Keys: 2/4/6/8 or arrows move the cursor, 5/OK confirms, 7 backs out one level,
 * 9 or * ends the phase, CLEAR returns to the menu, right softkey exits.
 * Pen: tap a tile to aim the cursor (a second tap on the same tile confirms),
 * tap the action card's rows.
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpPixelFont.h"
#include "assets_gen.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320
#define MW 15
#define MH 17
#define TS 16
#define MAP_Y 24
#define MAP_H (MH * TS)
#define MAXU 14

enum { TR_GRASS = 0, TR_ROAD, TR_SAND, TR_WATER, TR_SHORE, TR_FOREST, TR_MOUNT,
       TR_PEAK, TR_HOUSE, TR_KEEP, TR_TENT, TR_RUBBLE, TR_BRIDGE, TR_KINDS };

/* cost 0 is impassable. Hoofed units are additionally barred from cliffs and
 * peaks, which is the one terrain rule that changes the map's routes. */
static const uint8_t TR_COST[TR_KINDS]  = { 1, 1, 2, 0, 2, 2, 3, 4, 0, 2, 1, 2, 1 };
static const uint8_t TR_DEF[TR_KINDS]   = { 0, 0, 0, 0, 0, 20, 30, 40, 0, 30, 20, 10, 0 };
static const uint8_t TR_AVOID[TR_KINDS] = { 0, 0, 5, 0, 5, 15, 20, 25, 0, 10, 5, 15, 0 };
static const uint8_t TR_HOOF[TR_KINDS]  = { 1, 1, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1 };
static const char* const TR_NAME[TR_KINDS] = {
    "PLAIN", "ROAD", "SAND", "SEA", "SHORE", "WOOD", "CLIFF", "PEAK",
    "HOUSE", "KEEP", "CAMP", "RUIN", "BRIDGE" };

enum { CLS_SWORD = 0, CLS_AXE, CLS_LANCE, CLS_BOW, CLS_MAGE, CLS_CAV, CLS_FOX,
       CLS_N };

typedef struct ClassDef {
    uint8_t hp, mt, mov, rmin, rmax, spd, dfn, str, hoof;
} ClassDef;

static const ClassDef CLS[CLS_N] = {
    { 28, 6, 5, 1, 1, 7, 6, 7, 0 },   /* sword: the commander */
    { 32, 9, 5, 1, 1, 4, 5, 9, 0 },   /* axe: slow, hits hardest */
    { 30, 7, 6, 1, 1, 5, 5, 8, 0 },   /* lance: the fast foot unit */
    { 24, 5, 4, 2, 3, 6, 3, 6, 0 },   /* bow: shoots, never counters at range */
    { 22, 7, 4, 2, 3, 5, 3, 5, 0 },   /* mage: same but harder */
    { 34, 8, 8, 1, 1, 4, 4, 8, 1 },   /* knight: 8 tiles, no ridges */
    { 18, 3, 7, 1, 1, 9, 2, 4, 0 },   /* fox: the reference's companion animal */
};
static const char* const CLS_TAG[CLS_N] = {
    "SWORD", "AXE", "LANCE", "BOW", "MAGE", "KNIGHT", "FOX" };

typedef struct Unit {
    int16_t x, y;
    int16_t ax, ay;          /* in-tile walk offset, Q8.8 */
    uint8_t side, cls, hp, done, alive, flash, pose;
    int8_t face;             /* -1 -> the sprite is mirrored */
    const char* name;
} Unit;

/* The player's vanguard holds the south camp, the enemy lines the north keep. */
typedef struct Rec { uint8_t side, cls, x, y; const char* name; } Rec;
static const Rec ROSTER[] = {
    { 0, CLS_SWORD,  7, 14, "CAEDRIC" },
    { 0, CLS_AXE,    5, 15, "BROMWICH" },
    { 0, CLS_LANCE,  9, 15, "AISLING" },
    { 0, CLS_BOW,    3, 16, "ROWAN" },
    { 0, CLS_MAGE,  11, 16, "YRKA" },
    { 0, CLS_CAV,    7, 16, "DERRIC" },
    { 0, CLS_FOX,    6, 15, "VIXEN" },
    { 1, CLS_SWORD,  7,  3, "VORNE" },
    { 1, CLS_AXE,    3,  4, "HRAGNAR" },
    { 1, CLS_LANCE, 11,  4, "SELENE" },
    { 1, CLS_BOW,   10,  5, "MERRIC" },
    { 1, CLS_MAGE,   4,  5, "OSKA" },
    { 1, CLS_CAV,    7,  5, "TARNHILD" },
};
#define NROSTER ((int)(sizeof(ROSTER) / sizeof(ROSTER[0])))

enum { SCR_SPLASH = 0, SCR_MENU, SCR_HELP, SCR_BATTLE };
enum { BP_SELECT = 0, BP_RANGE, BP_WALK, BP_ACTION, BP_TARGET, BP_CUTIN,
       BP_HIT, BP_ENEMY, BP_RESULT };

static VMINT g_layer = -1, g_timer = -1;
static int g_screen = SCR_SPLASH, g_phase = BP_SELECT, g_menu_i = 0;
static int g_splash_t = 0, g_p1_side = 0;
static int g_cur_x = 7, g_cur_y = 14, g_sel = -1, g_row_sel = 0;
static int g_round = 1, g_active_side = 0, g_result = 0;
static int g_tick = 0, g_water_f = 0, g_frame_ms = 0;
static int g_band_a = 0, g_band_d = 0, g_band_t = 0, g_beat = 0, g_beat_t = 0;
static int g_ai_i = 0, g_ai_target = -1;
static uint32_t g_rng = 0x5AC7F19Du;

static uint8_t g_map[MH][MW];
static uint8_t g_flip[MH][MW];
static uint8_t g_dist[MH][MW];
static int8_t g_prev[MH][MW][2];
static uint8_t g_atk[MH][MW];
static uint8_t g_seen[MH][MW];
static Unit g_u[MAXU];
static int g_nu = 0;

typedef struct Blow { int valid, dmg, hit, crit; } Blow;
static Blow g_blow[2];

typedef struct Pop { int live, x, y, val, t, crit; } Pop;
typedef struct Spark { int live, x, y, t; } Spark;
static Pop g_pop[6];
static Spark g_spk[6];

static int g_walk_n = 0, g_walk_i = 0;
static int8_t g_walkx[24], g_walky[24];

#define UI_INK    vxpe2d_rgb565(8, 9, 14)
#define UI_NAVY   vxpe2d_rgb565(18, 22, 38)
#define UI_PARCH  vxpe2d_rgb565(236, 228, 196)
#define UI_PARCH2 vxpe2d_rgb565(204, 188, 146)
#define UI_GOLD   vxpe2d_rgb565(228, 182, 60)
#define UI_IVORY  vxpe2d_rgb565(240, 236, 214)
#define UI_TEAL   vxpe2d_rgb565(96, 190, 220)
#define UI_RED    vxpe2d_rgb565(214, 74, 66)
#define UI_GREEN  vxpe2d_rgb565(96, 196, 92)
#define UI_DIM    vxpe2d_rgb565(150, 148, 132)
#define RNG_BLUE  vxpe2d_rgb565(64, 132, 224)
#define RNG_RED   vxpe2d_rgb565(212, 60, 56)

#define CARD_X 118
#define CARD_Y 198
#define CARD_W 120
#define CARD_H 78
#define ROW_Y0 224
#define ROW_STEP 22
enum { ACT_ATTACK = 0, ACT_WAIT, ACT_N };
static const char* const ACT[ACT_N] = { "ATTACK", "WAIT" };

/* ---- small helpers ------------------------------------------------------ */
static uint32_t rnd32(void) {
    g_rng = g_rng * 1664525u + 1013904223u;
    return g_rng;
}
static int iabs(int v) { return v < 0 ? -v : v; }
static int imin(int a, int b) { return a < b ? a : b; }
static VMUINT16* framebuffer(void) {
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}
static void px(uint16_t* fb, int x, int y, uint16_t c) {
    if ((unsigned)x < (unsigned)SW && (unsigned)y < (unsigned)SH)
        fb[y * SW + x] = c;
}
static void line8(uint16_t* fb, int x0, int y0, int x1, int y1, uint16_t c) {
    int dx = x1 - x0, dy = y1 - y0;
    int sx = dx < 0 ? -1 : 1, sy = dy < 0 ? -1 : 1;
    int adx = iabs(dx), ady = iabs(dy);
    int err = adx - ady, i, n = adx > ady ? adx : ady, e2;
    for (i = 0; i <= n; ++i) {
        px(fb, x0, y0, c);
        e2 = err << 1;
        if (e2 > -ady) { err -= ady; x0 += sx; }
        if (e2 < adx) { err += adx; y0 += sy; }
    }
}
/* Square-stamped line: the path arrow needs 3-4 px of body to read at all over
 * grass of nearly the same value, so it is drawn dark-then-light. */
static void thick(uint16_t* fb, int x0, int y0, int x1, int y1, uint16_t c,
                  int w) {
    int dx = x1 - x0, dy = y1 - y0;
    int sx = dx < 0 ? -1 : 1, sy = dy < 0 ? -1 : 1;
    int adx = iabs(dx), ady = iabs(dy);
    int err = adx - ady, i, n = adx > ady ? adx : ady, e2, h = w / 2, a, b;
    for (i = 0; i <= n; ++i) {
        for (a = -h; a <= h; ++a)
            for (b = -h; b <= h; ++b)
                px(fb, x0 + a, y0 + b, c);
        e2 = err << 1;
        if (e2 > -ady) { err -= ady; x0 += sx; }
        if (e2 < adx) { err += adx; y0 += sy; }
    }
}
static void draw_text(uint16_t* fb, int x, int y, const char* t, int font,
                      int scale, uint16_t color, uint8_t effects) {
    VxpeFontStyle st;
    VxpeRectI clip;
    vxpe_font_style_default(&st);
    st.font_id = (uint8_t)font;
    st.scale = (uint8_t)scale;
    st.effects = effects;
    st.color565 = color;
    st.shadow565 = UI_INK;
    st.outline565 = UI_INK;
    st.highlight565 = vxpe2d_rgb565(255, 250, 220);
    clip.x = 0; clip.y = 0; clip.w = SW; clip.h = SH;
    vxpe_font_draw(fb, SW, SH, x, y, t, &st, clip);
}
static int text_w(const char* t, int font, int scale) {
    VxpeFontStyle st;
    vxpe_font_style_default(&st);
    st.font_id = (uint8_t)font;
    st.scale = (uint8_t)scale;
    return vxpe_font_measure(t, &st);
}
static void draw_text_c(uint16_t* fb, int cx, int y, const char* t, int font,
                        int scale, uint16_t color, uint8_t effects) {
    draw_text(fb, cx - text_w(t, font, scale) / 2, y, t, font, scale, color,
              effects);
}
static void num_str(char* out, int v) {
    char tmp[8];
    int n = 0, i;
    if (v < 0) v = 0;
    do { tmp[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    for (i = 0; i < n; ++i) out[i] = tmp[n - 1 - i];
    out[i] = 0;
}
static void app(char* out, const char* s) { while (*out) ++out; while (*s) *out++ = *s++; *out = 0; }
static void appnum(char* out, int v) { char n[8]; num_str(n, v); app(out, n); }
static void frame4(uint16_t* fb, int x, int y, int w, int h, uint16_t c) {
    vxpe2d_fill_rect(fb, SW, SH, x, y, w, 1, c);
    vxpe2d_fill_rect(fb, SW, SH, x, y + h - 1, w, 1, c);
    vxpe2d_fill_rect(fb, SW, SH, x, y, 1, h, c);
    vxpe2d_fill_rect(fb, SW, SH, x + w - 1, y, 1, h, c);
}

/* ---- map ---------------------------------------------------------------- */
static void parse_map(void) {
    static const char* const SRC[MH] = {
        "^^^^A^^^^^^A^^^",
        "^..T.^...T..^.^",
        "...=...K...=...",
        "..T=...=...=..T",
        ".H.=...=...=.H.",
        "...=ss.=.ss=...",
        "..T=...=...=..T",
        ":::-:::-:::-:::",
        "~~~-~~~-~~~-~~~",
        "~~~-~~~-~~~-~~~",
        ";;;-;;;-;;;-;;;",
        "...=...=...=...",
        "..T=ss.=.ss..T.",
        ".H.=...=...=.H.",
        "...=...=...=...",
        "..T....t....T..",
        "..............."
    };
    int x, y;
    for (y = 0; y < MH; ++y) {
        for (x = 0; x < MW; ++x) {
            uint8_t k = TR_GRASS, f = 0;
            switch (SRC[y][x]) {
            case '=': k = TR_ROAD; break;
            case 's': k = TR_SAND; break;
            case '~': k = TR_WATER; break;
            case ':': k = TR_SHORE; break;
            case ';': k = TR_SHORE; f = 1; break;
            case 'T': k = TR_FOREST; break;
            case '^': k = TR_MOUNT; break;
            case 'A': k = TR_PEAK; break;
            case 'H': k = TR_HOUSE; break;
            case 'K': k = TR_KEEP; break;
            case 't': k = TR_TENT; break;
            case '%': k = TR_RUBBLE; break;
            case '-': k = TR_BRIDGE; break;
            default: break;
            }
            g_map[y][x] = k;
            g_flip[y][x] = f;
        }
    }
}
static int tile_id(int x, int y) {
    int h = (x * 7 + y * 13) & 7;
    switch (g_map[y][x]) {
    case TR_GRASS:  return TV_T_GRASS0 + (h & 3);
    case TR_ROAD:   return TV_T_ROAD0 + (h & 1);
    case TR_SAND:   return TV_T_SAND;
    case TR_WATER:  return TV_T_WATER0 + g_water_f;
    case TR_SHORE:  return TV_T_SHORE;
    case TR_FOREST: return TV_T_FOREST0 + (h % 3);
    case TR_MOUNT:  return TV_T_MOUNT0 + (h & 1);
    case TR_PEAK:   return TV_T_PEAK;
    case TR_HOUSE:  return TV_T_HOUSE;
    case TR_KEEP:   return TV_T_KEEP;
    case TR_TENT:   return TV_T_TENT;
    case TR_RUBBLE: return TV_T_RUBBLE;
    default:        return TV_T_BRIDGE;
    }
}
static void draw_map(uint16_t* fb) {
    VxpeSprite565 s;
    VxpeBlit565 op;
    int x, y;
    memset(&s, 0, sizeof(s));
    memset(&op, 0, sizeof(op));
    s.opaque = 1;
    s.width = s.height = TS;
    op.tint565 = 0xFFFF;
    op.alpha = 255;
    op.blend = VXPE_BLEND_COPY;
    for (y = 0; y < MH; ++y) {
        op.dst_y = (int16_t)(MAP_Y + y * TS);
        for (x = 0; x < MW; ++x) {
            s.pixels = TV_TILES[tile_id(x, y)];
            op.dst_x = (int16_t)(x * TS);
            op.flip_y = g_flip[y][x];
            vxpe2d_blit(fb, SW, SH, &s, &op);
        }
    }
}

/* ---- units -------------------------------------------------------------- */
static int unit_at(int x, int y) {
    int i;
    for (i = 0; i < g_nu; ++i)
        if (g_u[i].alive && g_u[i].x == x && g_u[i].y == y) return i;
    return -1;
}
static int terrain_ok(int x, int y, int cls) {
    int k;
    if (x < 0 || y < 0 || x >= MW || y >= MH) return 0;
    k = g_map[y][x];
    if (!TR_COST[k]) return 0;
    if (CLS[cls].hoof && !TR_HOOF[k]) return 0;
    return 1;
}
/* Enemies block movement, friends can be passed through but not stopped on. */
static int passable(int x, int y, int ui) {
    int o;
    if (!terrain_ok(x, y, g_u[ui].cls)) return 0;
    o = unit_at(x, y);
    if (o >= 0 && g_u[o].side != g_u[ui].side) return 0;
    return 1;
}
static int standable(int x, int y, int ui) {
    return passable(x, y, ui) && unit_at(x, y) < 0;
}
static int unit_sprite(int cls, int side, int pose) {
    if (cls == CLS_CAV) return TV_US_BLUE_CAV_IDLE + side * 3 + pose;
    if (cls == CLS_FOX) return TV_US_FOX_IDLE + (pose ? 1 : 0);
    return (cls * 2 + side) * 3 + pose;
}
static int hp_max(const Unit* u) { return CLS[u->cls].hp; }
static void spawn_units(void) {
    int i;
    g_nu = 0;
    for (i = 0; i < NROSTER && g_nu < MAXU; ++i) {
        Unit* u = &g_u[g_nu++];
        memset(u, 0, sizeof(*u));
        u->side = ROSTER[i].side;
        u->cls = ROSTER[i].cls;
        u->x = ROSTER[i].x;
        u->y = ROSTER[i].y;
        u->name = ROSTER[i].name;
        u->hp = CLS[u->cls].hp;
        u->alive = 1;
        u->face = (u->side == g_p1_side) ? -1 : 1;
    }
}

/* ---- ranges ------------------------------------------------------------- */
/* Dijkstra over the 300-cell grid, settled until the move budget runs out: a
 * 5-move unit settles about forty cells, so the whole field costs well under a
 * frame even though the grid is scanned linearly. */
static void compute_range(int ui) {
    static const int DX[4] = { 1, -1, 0, 0 };
    static const int DY[4] = { 0, 0, 1, -1 };
    static uint8_t done[MH][MW];
    int i, x, y, mov = CLS[g_u[ui].cls].mov;
    for (y = 0; y < MH; ++y)
        for (x = 0; x < MW; ++x) {
            g_dist[y][x] = 255;
            done[y][x] = 0;
            g_prev[y][x][0] = g_prev[y][x][1] = -1;
        }
    g_dist[g_u[ui].y][g_u[ui].x] = 0;
    for (i = 0; i < MH * MW; ++i) {
        int best = 255, bx = -1, by = -1, n;
        for (y = 0; y < MH; ++y)
            for (x = 0; x < MW; ++x)
                if (!done[y][x] && g_dist[y][x] < best) {
                    best = g_dist[y][x]; bx = x; by = y;
                }
        if (bx < 0 || best > mov) break;
        done[by][bx] = 1;
        for (n = 0; n < 4; ++n) {
            int nx = bx + DX[n], ny = by + DY[n], c;
            if (!passable(nx, ny, ui)) continue;
            c = best + TR_COST[g_map[ny][nx]];
            if (c < g_dist[ny][nx]) {
                g_dist[ny][nx] = (uint8_t)c;
                g_prev[ny][nx][0] = (int8_t)(bx - nx);
                g_prev[ny][nx][1] = (int8_t)(by - ny);
            }
        }
    }
    for (y = 0; y < MH; ++y)
        for (x = 0; x < MW; ++x)
            if (g_dist[y][x] > mov) g_dist[y][x] = 255;
}
static int in_range(int x, int y) {
    return x >= 0 && y >= 0 && x < MW && y < MH && g_dist[y][x] != 255;
}
static int build_path(int ui, int tx, int ty) {
    int n = 0, x = tx, y = ty, i;
    while (!(x == g_u[ui].x && y == g_u[ui].y)) {
        if (n >= 24) return 0;
        g_walkx[n] = (int8_t)x;
        g_walky[n] = (int8_t)y;
        ++n;
        if (g_prev[y][x][0] == -1 && g_prev[y][x][1] == -1) return 0;
        /* g_prev holds the step from this cell back toward the unit's cell, so
         * the chain is followed by adding it. */
        x += g_prev[y][x][0];
        y += g_prev[y][x][1];
    }
    for (i = 0; i < n / 2; ++i) {
        int8_t t = g_walkx[i]; g_walkx[i] = g_walkx[n - 1 - i]; g_walkx[n - 1 - i] = t;
        t = g_walky[i]; g_walky[i] = g_walky[n - 1 - i]; g_walky[n - 1 - i] = t;
    }
    g_walk_n = n;
    g_walk_i = 0;
    return n;
}
static void draw_path_arrow(uint16_t* fb, int ui, int tx, int ty) {
    int sx = g_u[ui].x, sy = g_u[ui].y, i, hx, hy, dx, dy, ax, ay;
    if (!build_path(ui, tx, ty)) return;
    for (i = 0; i < g_walk_n; ++i) {
        int x0 = sx * TS + TS / 2, y0 = MAP_Y + sy * TS + TS / 2;
        int x1 = g_walkx[i] * TS + TS / 2, y1 = MAP_Y + g_walky[i] * TS + TS / 2;
        thick(fb, x0, y0, x1, y1, UI_INK, 6);
        thick(fb, x0, y0, x1, y1, UI_IVORY, 3);
        sx = g_walkx[i]; sy = g_walky[i];
    }
    dx = sx - g_u[ui].x; dy = sy - g_u[ui].y;
    if (!dx && !dy) return;
    hx = sx * TS + TS / 2; hy = MAP_Y + sy * TS + TS / 2;
    ax = dx ? (dx > 0 ? 5 : -5) : 0;
    ay = dy ? (dy > 0 ? 5 : -5) : 0;
    line8(fb, hx, hy, hx - ax + ay, hy - ay + ax, UI_INK);
    line8(fb, hx, hy, hx - ax - ay, hy - ay - ax, UI_INK);
    line8(fb, hx, hy, hx - ax + ay, hy - ay + ax, UI_IVORY);
    line8(fb, hx, hy, hx - ax - ay, hy - ay - ax, UI_IVORY);
}
static void paint_field(uint16_t* fb, int x, int y, uint16_t c) {
    int x0 = x * TS, y0 = MAP_Y + y * TS, i, j;
    vxpe2d_overlay_rect(fb, SW, SH, x0, y0, TS, TS, c, 96, VXPE_BLEND_ALPHA);
    for (j = 0; j < TS; ++j)
        for (i = 0; i < TS; ++i)
            if ((x0 + i - y0 - j) % 6 == 0) px(fb, x0 + i, y0 + j, c);
}
static void paint_move_range(uint16_t* fb, int ui) {
    int x, y;
    (void)ui;
    for (y = 0; y < MH; ++y)
        for (x = 0; x < MW; ++x)
            if (g_dist[y][x] != 255) paint_field(fb, x, y, RNG_BLUE);
}
static void compute_attack(int ui, int fx, int fy) {
    int x, y, rmin = CLS[g_u[ui].cls].rmin, rmax = CLS[g_u[ui].cls].rmax;
    memset(g_atk, 0, sizeof(g_atk));
    for (y = 0; y < MH; ++y)
        for (x = 0; x < MW; ++x) {
            int d = iabs(x - fx) + iabs(y - fy);
            if (d >= rmin && d <= rmax) g_atk[y][x] = 1;
        }
}
static void paint_attack_range(uint16_t* fb) {
    int x, y;
    for (y = 0; y < MH; ++y)
        for (x = 0; x < MW; ++x)
            if (g_atk[y][x]) paint_field(fb, x, y, RNG_RED);
}
static int targets_in_attack_range(int ui) {
    int i, n = 0;
    for (i = 0; i < g_nu; ++i)
        if (g_u[i].alive && g_u[i].side != g_u[ui].side && g_atk[g_u[i].y][g_u[i].x])
            ++n;
    return n;
}

/* ---- combat ------------------------------------------------------------- */
/* Damage is attacker strength + weapon might minus target defence and its
 * terrain bonus; hit rate trades speed against the target's terrain cover. The
 * numbers are tuned so a road fight trades two hits for one, which is what makes
 * the terrain table worth reading at all. */
static void calc_blow(int a, int d, Blow* b) {
    const Unit* A = &g_u[a];
    const Unit* D = &g_u[d];
    int atk = CLS[A->cls].str + CLS[A->cls].mt;
    int def = CLS[D->cls].dfn + TR_DEF[g_map[D->y][D->x]];
    int dmg = atk - def + (int)(rnd32() % 3);
    int hit = 78 + (CLS[A->cls].spd - CLS[D->cls].spd) * 4
              - TR_AVOID[g_map[D->y][D->x]];
    b->valid = 1;
    b->dmg = dmg < 1 ? 1 : dmg;
    b->hit = hit < 25 ? 25 : (hit > 99 ? 99 : hit);
    b->crit = 6 + CLS[A->cls].spd / 2;
}
static void spawn_fx(int d, int dmg, int crit) {
    int i;
    for (i = 0; i < 6; ++i)
        if (!g_pop[i].live) {
            g_pop[i].live = 1; g_pop[i].t = 0; g_pop[i].crit = crit;
            g_pop[i].x = g_u[d].x * TS + 3;
            g_pop[i].y = MAP_Y + g_u[d].y * TS - 8;
            g_pop[i].val = dmg;
            break;
        }
    for (i = 0; i < 6; ++i)
        if (!g_spk[i].live) {
            g_spk[i].live = 1; g_spk[i].t = 0;
            g_spk[i].x = g_u[d].x * TS + TS / 2;
            g_spk[i].y = MAP_Y + g_u[d].y * TS + 6;
            break;
        }
}
static void deliver(int beat) {
    int a = beat ? g_band_d : g_band_a;
    int d = beat ? g_band_a : g_band_d;
    Blow* b = &g_blow[beat];
    g_beat = beat;
    g_beat_t = 0;
    g_u[a].pose = 2;
    if (!b->valid || !g_u[a].alive || !g_u[d].alive) { b->valid = 0; return; }
    if ((int)(rnd32() % 100) < b->hit) {
        int crit = (int)(rnd32() % 100) < b->crit;
        int dmg = crit ? b->dmg * 3 : b->dmg;
        /* hp is a byte: subtracting in it wraps a killing blow back to a huge
         * positive number and the unit never dies, which stalls the battle. */
        int left = (int)g_u[d].hp - dmg;
        g_u[d].hp = left < 0 ? 0 : (uint8_t)left;
        g_u[d].flash = 14;
        if (!g_u[d].hp) g_u[d].alive = 0;
        spawn_fx(d, dmg, crit);
    }
}
static void start_combat(int a, int d) {
    int dist = iabs(g_u[d].x - g_u[a].x) + iabs(g_u[d].y - g_u[a].y);
    g_band_a = a; g_band_d = d; g_band_t = 0;
    memset(g_blow, 0, sizeof(g_blow));
    calc_blow(a, d, &g_blow[0]);
    if (dist >= CLS[g_u[d].cls].rmin && dist <= CLS[g_u[d].cls].rmax)
        calc_blow(d, a, &g_blow[1]);
    g_phase = BP_CUTIN;
}
static void check_outcome(void) {
    int i, live[2] = { 0, 0 }, cmd[2] = { 0, 0 };
    for (i = 0; i < g_nu; ++i) {
        if (!g_u[i].alive) continue;
        ++live[g_u[i].side];
        if (g_u[i].cls == CLS_SWORD) cmd[g_u[i].side] = 1;
    }
    if (g_result) { g_phase = BP_RESULT; return; }
    if (!live[1 - g_p1_side] || !cmd[1 - g_p1_side]) g_result = 1;
    else if (!live[g_p1_side] || !cmd[g_p1_side]) g_result = 2;
    if (g_result) g_phase = BP_RESULT;
}
static void end_unit(void) {
    if (g_sel >= 0) {
        g_u[g_sel].done = 1;
        g_u[g_sel].pose = 0;
    }
    g_sel = -1;
    g_ai_target = -1;
    check_outcome();
    if (g_result) return;
    g_phase = g_active_side == g_p1_side ? BP_SELECT : BP_ENEMY;
}

/* ---- enemy command ------------------------------------------------------ */
/* Score every reachable tile: attack if something is in reach, and take the
 * least damage back while doing it; otherwise close on the nearest target and
 * prefer cover. Without this the enemy feeds units in one at a time. */
static int ai_score(int ui, int tx, int ty, int* best_target) {
    int i, s = -1, worst = 0, near = 99;
    *best_target = -1;
    for (i = 0; i < g_nu; ++i) {
        int d;
        if (!g_u[i].alive || g_u[i].side == g_u[ui].side) continue;
        d = iabs(g_u[i].x - tx) + iabs(g_u[i].y - ty);
        if (d < near) near = d;
        if (d >= CLS[g_u[ui].cls].rmin && d <= CLS[g_u[ui].cls].rmax) {
            Blow b, back;
            calc_blow(ui, i, &b);
            if (s < 0 || b.dmg * b.hit / 100 > s) {
                s = b.dmg * b.hit / 100;
                *best_target = i;
            }
            calc_blow(i, ui, &back);
            if (back.dmg * back.hit / 100 > worst) worst = back.dmg * back.hit / 100;
        }
    }
    if (s >= 0) return 60 + s * 4 - worst * 3 + TR_DEF[g_map[ty][tx]] / 5;
    return 10 - near * 3 + TR_DEF[g_map[ty][tx]] / 10;
}
static void ai_pick(void) {
    int ui = g_sel, x, y, best = -9999, bx = -1, by = -1, bt = -1;
    compute_range(ui);
    for (y = 0; y < MH; ++y)
        for (x = 0; x < MW; ++x) {
            int s, t;
            if (g_dist[y][x] == 255) continue;
            if (x != g_u[ui].x || y != g_u[ui].y) {
                if (!standable(x, y, ui)) continue;
            }
            s = ai_score(ui, x, y, &t);
            if (s > best) { best = s; bx = x; by = y; bt = t; }
        }
    g_ai_target = bt;
    if (bx < 0) { end_unit(); return; }
    if (bx == g_u[ui].x && by == g_u[ui].y) {
        g_walk_n = 0;
        g_walk_i = 0;
        g_phase = BP_WALK;
        return;
    }
    if (!build_path(ui, bx, by)) { end_unit(); return; }
    g_phase = BP_WALK;
}
static void start_new_round(void) {
    int i;
    for (i = 0; i < g_nu; ++i) {
        g_u[i].done = 0;
        g_u[i].pose = 0;
        /* the camp and the keep mend whoever holds them */
        if (g_u[i].alive && (g_map[g_u[i].y][g_u[i].x] == TR_TENT ||
                             g_map[g_u[i].y][g_u[i].x] == TR_KEEP))
            g_u[i].hp = (uint8_t)imin(hp_max(&g_u[i]), g_u[i].hp + 6);
    }
    g_active_side = g_p1_side;
    g_ai_i = 0;
    ++g_round;
    g_phase = BP_SELECT;
}
static int ai_next_unit(void) {
    while (g_ai_i < g_nu) {
        int i = g_ai_i++;
        if (g_u[i].alive && g_u[i].side == g_active_side && !g_u[i].done) {
            g_sel = i;
            ai_pick();
            return 1;
        }
    }
    return 0;
}

/* ---- sprites ------------------------------------------------------------ */
static void blit_sprite(uint16_t* fb, int id, int x, int y, int sw, int sh,
                        uint16_t tint, uint8_t blend, uint8_t alpha, int flip_x) {
    const TvSprite* sp = &TV_SPRITES[id];
    VxpeSprite565 s;
    VxpeBlit565 op;
    memset(&s, 0, sizeof(s));
    memset(&op, 0, sizeof(op));
    s.pixels = sp->px;
    s.mask = sp->mask;
    s.width = sp->w;
    s.height = sp->h;
    op.dst_x = (int16_t)x;
    op.dst_y = (int16_t)y;
    op.dst_w = (uint16_t)sw;
    op.dst_h = (uint16_t)sh;
    op.tint565 = tint;
    op.alpha = alpha;
    op.blend = blend;
    op.flip_x = (uint8_t)flip_x;
    vxpe2d_blit(fb, SW, SH, &s, &op);
}
static void draw_unit(uint16_t* fb, Unit* u) {
    int id = unit_sprite(u->cls, u->side, u->pose);
    const TvSprite* sp = &TV_SPRITES[id];
    int x = u->x * TS + (u->ax >> 8);
    int y = MAP_Y + u->y * TS + (u->ay >> 8);
    int dx = x + (TS - sp->w) / 2, dy = y + TS - sp->h;
    uint16_t tint = 0xFFFF;
    if (u->done && g_active_side == g_p1_side && u->side == g_p1_side)
        tint = vxpe2d_rgb565(122, 122, 142);
    vxpe2d_overlay_rect(fb, SW, SH, x + 2, y + 13, 12, 3, UI_INK, 78,
                        VXPE_BLEND_ALPHA);
    blit_sprite(fb, id, dx, dy, 0, 0, tint, VXPE_BLEND_ALPHA, 255, u->face < 0);
    if (u->flash) {
        blit_sprite(fb, id, dx, dy, 0, 0, 0xFFFF, VXPE_BLEND_ADD, 110,
                    u->face < 0);
        --u->flash;
    }
}
static void draw_hp_bar(uint16_t* fb, const Unit* u) {
    int x = u->x * TS + 1, y = MAP_Y + u->y * TS + 13;
    int w = 14, fill, max = hp_max(u);
    uint16_t c;
    if (u->hp >= max) return;
    fill = w * u->hp / max;
    c = u->hp * 3 > max * 2 ? UI_GREEN : (u->hp * 3 > max ? UI_GOLD : UI_RED);
    vxpe2d_fill_rect(fb, SW, SH, x - 1, y - 1, w + 2, 4, UI_INK);
    vxpe2d_fill_rect(fb, SW, SH, x, y, w, 2, vxpe2d_rgb565(52, 40, 40));
    vxpe2d_fill_rect(fb, SW, SH, x, y, fill, 2, c);
}
static void draw_units(uint16_t* fb) {
    int i, order[MAXU], n = 0;
    /* Painter's order by row so a knight in front hides the feet behind it. */
    for (i = 0; i < g_nu; ++i) {
        int j;
        if (!g_u[i].alive) continue;
        j = n++;
        while (j > 0 && g_u[order[j - 1]].y > g_u[i].y) {
            order[j] = order[j - 1];
            --j;
        }
        order[j] = i;
    }
    for (i = 0; i < n; ++i) draw_unit(fb, &g_u[order[i]]);
    for (i = 0; i < n; ++i) draw_hp_bar(fb, &g_u[order[i]]);
}
static void draw_cursor(uint16_t* fb) {
    int x = g_cur_x * TS, y = MAP_Y + g_cur_y * TS, i;
    uint16_t c = (g_tick & 8) ? UI_GOLD : UI_IVORY;
    static const int CX[4] = { 0, 12, 0, 12 };
    static const int CY[4] = { 0, 0, 12, 12 };
    for (i = 0; i < 4; ++i) {
        int bx = x + CX[i], by = y + CY[i];
        int sx = (i & 1) ? -1 : 1, sy = (i & 2) ? -1 : 1, k;
        for (k = 0; k < 4; ++k) {
            px(fb, bx + k * sx, by, c);
            px(fb, bx, by + k * sy, c);
        }
    }
    vxpe2d_overlay_rect(fb, SW, SH, x, y, TS, TS, c, 24, VXPE_BLEND_ALPHA);
}
static void draw_pops(uint16_t* fb) {
    int i;
    for (i = 0; i < 6; ++i) {
        char buf[8];
        if (!g_pop[i].live) continue;
        num_str(buf, g_pop[i].val);
        draw_text(fb, g_pop[i].x, g_pop[i].y - g_pop[i].t / 2, buf,
                  VXPE_FONT_UI, g_pop[i].crit ? 2 : 1,
                  g_pop[i].crit ? UI_RED : UI_IVORY,
                  VXPE_FONT_OUTLINE | VXPE_FONT_SHADOW);
    }
    for (i = 0; i < 6; ++i) {
        int r, k;
        if (!g_spk[i].live) continue;
        r = 3 + g_spk[i].t;
        for (k = 0; k < 4; ++k) {
            int a = k ? 3 : 1;
            line8(fb, g_spk[i].x - a * r / 3, g_spk[i].y - r,
                  g_spk[i].x - a, g_spk[i].y, UI_IVORY);
            line8(fb, g_spk[i].x + a * r / 3, g_spk[i].y + r,
                  g_spk[i].x + a, g_spk[i].y, UI_IVORY);
        }
        vxpe2d_radial_light_fast(fb, SW, SH, g_spk[i].x, g_spk[i].y, r + 4,
                                 UI_RED, (uint8_t)(200 - g_spk[i].t * 20));
    }
}

/* ---- chrome ------------------------------------------------------------- */
static void draw_card(uint16_t* fb, const Unit* u) {
    int i, y;
    char buf[40];
    vxpe2d_gradient_vertical(fb, SW, SH, CARD_X, CARD_Y, CARD_W, CARD_H,
                             UI_PARCH, UI_PARCH2);
    vxpe2d_fill_rect(fb, SW, SH, CARD_X, CARD_Y, CARD_W, 2, UI_GOLD);
    frame4(fb, CARD_X + 2, CARD_Y + 4, CARD_W - 4, CARD_H - 6,
           vxpe2d_rgb565(150, 116, 58));
    vxpe2d_fill_rect(fb, SW, SH, CARD_X + CARD_W - 8, CARD_Y + CARD_H - 8, 8, 8,
                     vxpe2d_rgb565(168, 150, 112));
    blit_sprite(fb, TV_US_CREST_BLUE + u->side, CARD_X + 6, CARD_Y + 8, 8, 8,
                0xFFFF, VXPE_BLEND_ALPHA, 255, 0);
    draw_text(fb, CARD_X + 18, CARD_Y + 8, u->name, VXPE_FONT_UI, 1,
              vxpe2d_rgb565(44, 32, 20), 0);
    buf[0] = 0;
    app(buf, "HP ");
    appnum(buf, u->hp);
    app(buf, "/");
    appnum(buf, hp_max(u));
    draw_text(fb, CARD_X + 18, CARD_Y + 19, buf, VXPE_FONT_UI, 1,
              vxpe2d_rgb565(74, 50, 26), 0);
    y = ROW_Y0;
    for (i = 0; i < ACT_N; ++i) {
        if (i == g_row_sel) {
            vxpe2d_overlay_rect(fb, SW, SH, CARD_X + 4, y - 3, CARD_W - 10,
                                ROW_STEP - 3, UI_TEAL, 110, VXPE_BLEND_ALPHA);
            draw_text(fb, CARD_X + 7, y, ">", VXPE_FONT_UI, 1,
                      vxpe2d_rgb565(20, 26, 46), 0);
        }
        draw_text(fb, CARD_X + 20, y, ACT[i], VXPE_FONT_UI, 1,
                  vxpe2d_rgb565(34, 28, 18), 0);
        y += ROW_STEP;
    }
}
static void draw_bars(uint16_t* fb) {
    int i, live = 0, k, y;
    char buf[48];
    vxpe2d_gradient_vertical(fb, SW, SH, 0, 0, SW, MAP_Y,
                             vxpe2d_rgb565(28, 32, 56), UI_NAVY);
    vxpe2d_fill_rect(fb, SW, SH, 0, MAP_Y - 1, SW, 1, UI_GOLD);
    buf[0] = 0;
    app(buf, "ROUND ");
    appnum(buf, g_round);
    draw_text(fb, 4, 8, buf, VXPE_FONT_UI, 1, UI_GOLD, VXPE_FONT_SHADOW);
    if (g_result) {
        draw_text(fb, 78, 8, "BATTLE OVER", VXPE_FONT_UI, 1,
                  g_result == 1 ? UI_GOLD : UI_RED, VXPE_FONT_SHADOW);
    } else {
        draw_text(fb, 78, 8,
                  g_active_side == g_p1_side ? "YOUR PHASE" : "ENEMY PHASE",
                  VXPE_FONT_UI, 1, g_active_side == g_p1_side ? UI_TEAL : UI_RED,
                  VXPE_FONT_SHADOW);
    }
    for (i = 0; i < g_nu; ++i)
        if (g_u[i].alive && g_u[i].side == g_p1_side) ++live;
    buf[0] = 0;
    app(buf, "YOU ");
    appnum(buf, live);
    draw_text(fb, 176, 8, buf, VXPE_FONT_UI, 1, UI_IVORY, VXPE_FONT_SHADOW);
    buf[0] = 0;
    app(buf, "MS ");
    appnum(buf, g_frame_ms);
    draw_text(fb, 212, 8, buf, VXPE_FONT_UI, 1, UI_DIM, 0);

    y = MAP_Y + MAP_H;
    vxpe2d_gradient_vertical(fb, SW, SH, 0, y, SW, SH - y, UI_NAVY,
                             vxpe2d_rgb565(10, 12, 20));
    vxpe2d_fill_rect(fb, SW, SH, 0, y, SW, 1, UI_GOLD);
    k = g_map[g_cur_y][g_cur_x];
    buf[0] = 0;
    app(buf, TR_NAME[k]);
    app(buf, " DEF ");
    appnum(buf, TR_DEF[k]);
    app(buf, " AVO ");
    appnum(buf, TR_AVOID[k]);
    if (!TR_COST[k]) app(buf, " BLOCKED");
    else if (CLS[g_u[g_sel < 0 ? 0 : g_sel].cls].hoof && !TR_HOOF[k])
        app(buf, " NO HOOFS");
    draw_text(fb, 4, y + 3, buf, VXPE_FONT_UI, 1, UI_DIM, 0);
    if (g_sel >= 0) {
        const Unit* u = &g_u[g_sel];
        buf[0] = 0;
        app(buf, u->name);
        app(buf, " ");
        app(buf, CLS_TAG[u->cls]);
        app(buf, " HP ");
        appnum(buf, u->hp);
        app(buf, "/");
        appnum(buf, hp_max(u));
        draw_text(fb, 4, y + 12, buf, VXPE_FONT_UI, 1, UI_IVORY, 0);
        buf[0] = 0;
        app(buf, "MV ");
        appnum(buf, CLS[u->cls].mov);
        app(buf, " RNG ");
        appnum(buf, CLS[u->cls].rmin);
        if (CLS[u->cls].rmax != CLS[u->cls].rmin) {
            app(buf, "-");
            appnum(buf, CLS[u->cls].rmax);
        }
        draw_text(fb, 150, y + 12, buf, VXPE_FONT_UI, 1, UI_TEAL, 0);
    } else if (!g_result) {
        draw_text(fb, 4, y + 12,
                  g_active_side == g_p1_side ? "PICK A UNIT: 5/OK"
                                             : "ENEMY IS MOVING",
                  VXPE_FONT_UI, 1, UI_TEAL, 0);
    }
}
/* The reference's combat cut-in: a skewed navy band, the attacker blown up 3x
 * from the very same 16x26 tile sprite, and the name in gold display type. */
static void draw_cutin(uint16_t* fb) {
    const Unit* A = &g_u[g_band_a];
    const Unit* D = &g_u[g_band_d];
    int top = 70, h = 140, j, slide, lean, bx, by, id, sw, sh;
    char buf[40];
    if (g_band_t < 8) slide = -(SW * (8 - g_band_t) / 8);
    else if (g_band_t > 26) slide = SW * (g_band_t - 26) / 6;
    else slide = 0;
    if (slide >= SW || slide <= -SW) return;
    for (j = 0; j < h; ++j) {
        int y = top + j;
        int x0 = (h / 2 - j) / 2 + slide - 14;
        int w = SW + 28;
        uint16_t c = vxpe2d_rgb565(14 + j / 10, 18 + j / 8, 42 + j / 4);
        if (j < 2 || j >= h - 2) c = UI_GOLD;
        else if (j == 3 || j == h - 6) c = vxpe2d_rgb565(96, 74, 28);
        vxpe2d_fill_rect(fb, SW, SH, x0, y, w, 1, c);
    }
    lean = (h / 2 - 46) / 2 + slide - 14;
    id = unit_sprite(A->cls, A->side, 2);
    sw = TV_SPRITES[id].w * 3;
    sh = TV_SPRITES[id].h * 3;
    bx = lean + 12;
    by = top + 24;
    vxpe2d_fill_rect(fb, SW, SH, bx - 3, by - 3, sw + 6, sh + 6, UI_INK);
    vxpe2d_fill_rect(fb, SW, SH, bx - 2, by - 2, sw + 4, sh + 4, UI_GOLD);
    blit_sprite(fb, id, bx, by, sw, sh, 0xFFFF, VXPE_BLEND_ALPHA, 255, 0);
    {
        int tx = bx + sw + 14;
        if (tx > SW - 40) tx = SW - 40;
        draw_text(fb, tx, top + 22, A->name, VXPE_FONT_DISPLAY, 2, UI_GOLD,
                  VXPE_FONT_OUTLINE);
        draw_text(fb, tx, top + 46, "ATTACKS", VXPE_FONT_UI, 1, UI_IVORY,
                  VXPE_FONT_SHADOW);
        draw_text(fb, tx, top + 60, D->name, VXPE_FONT_UI, 1,
                  D->side == g_p1_side ? UI_RED : UI_DIM, VXPE_FONT_SHADOW);
        buf[0] = 0;
        app(buf, "HP ");
        appnum(buf, D->hp);
        app(buf, "/");
        appnum(buf, hp_max(D));
        draw_text(fb, tx, top + 74, buf, VXPE_FONT_UI, 1, UI_IVORY, 0);
        if (g_beat && g_blow[0].valid) {
            buf[0] = 0;
            app(buf, CLS_TAG[A->cls]);
            app(buf, " ");
            appnum(buf, g_blow[0].dmg);
            draw_text(fb, tx, top + 88, buf, VXPE_FONT_UI, 1, UI_GOLD, 0);
        }
    }
}
static void draw_result(uint16_t* fb) {
    int i, live = 0;
    char buf[40];
    vxpe2d_overlay_rect(fb, SW, SH, 0, 0, SW, SH, UI_INK, 168, VXPE_BLEND_ALPHA);
    draw_text_c(fb, SW / 2, 112, g_result == 1 ? "VICTORY" : "DEFEAT",
                VXPE_FONT_DISPLAY, 3, g_result == 1 ? UI_GOLD : UI_RED,
                VXPE_FONT_OUTLINE | VXPE_FONT_BEVEL);
    for (i = 0; i < g_nu; ++i)
        if (g_u[i].alive && g_u[i].side == g_p1_side) ++live;
    buf[0] = 0;
    app(buf, "ROUNDS ");
    appnum(buf, g_round);
    app(buf, "   SURVIVORS ");
    appnum(buf, live);
    draw_text_c(fb, SW / 2, 152, buf, VXPE_FONT_UI, 1, UI_IVORY,
                VXPE_FONT_SHADOW);
    draw_text_c(fb, SW / 2, 190, "CLEAR: BACK TO MENU", VXPE_FONT_UI, 1, UI_TEAL,
                VXPE_FONT_SHADOW);
    draw_text_c(fb, SW / 2, 206, "5: FIGHT AGAIN", VXPE_FONT_UI, 1, UI_DIM, 0);
}
static void draw_battle(uint16_t* fb) {
    int i;
    draw_map(fb);
    if (g_phase == BP_RANGE && g_sel >= 0) {
        paint_move_range(fb, g_sel);
        if (in_range(g_cur_x, g_cur_y) &&
            (g_cur_x != g_u[g_sel].x || g_cur_y != g_u[g_sel].y))
            draw_path_arrow(fb, g_sel, g_cur_x, g_cur_y);
    }
    if (g_phase == BP_TARGET && g_sel >= 0) {
        paint_attack_range(fb);
        for (i = 0; i < g_nu; ++i)
            if (g_u[i].alive && g_u[i].side != g_p1_side && g_atk[g_u[i].y][g_u[i].x])
                paint_field(fb, g_u[i].x, g_u[i].y, UI_RED);
    }
    draw_units(fb);
    if (g_phase <= BP_TARGET && g_active_side == g_p1_side && !g_result)
        draw_cursor(fb);
    draw_pops(fb);
    draw_bars(fb);
    if (g_phase == BP_ACTION && g_sel >= 0) draw_card(fb, &g_u[g_sel]);
    if (g_phase == BP_CUTIN) draw_cutin(fb);
    if (g_phase == BP_RESULT) draw_result(fb);
}

/* ---- splash and menu ---------------------------------------------------- */
static const char* side_name(void) { return g_p1_side ? "CRIMSON" : "AZURE"; }
/* draw_map only owns y 24..295, so every overlay screen has to clear the bands
 * itself or the previous screen's text stays burned in below the map. */
static void backdrop(uint16_t* fb) {
    vxpe2d_fill_rect(fb, SW, SH, 0, 0, SW, SH, UI_INK);
}
static void scrim(uint16_t* fb, int a) {
    vxpe2d_overlay_rect(fb, SW, SH, 0, 0, SW, SH, UI_INK, (uint8_t)a,
                        VXPE_BLEND_ALPHA);
}
static void draw_splash(uint16_t* fb) {
    int t = g_splash_t, i;
    backdrop(fb);
    draw_map(fb);
    draw_units(fb);
    scrim(fb, 128);
    for (i = 0; i < 168; ++i)
        vxpe2d_fill_rect(fb, SW, SH, 18, 46 + i, SW - 36, 1,
                         vxpe2d_rgb565(16 + i / 30, 20 + i / 26, 40 + i / 5));
    vxpe2d_fill_rect(fb, SW, SH, 18, 46, SW - 36, 2, UI_GOLD);
    vxpe2d_fill_rect(fb, SW, SH, 18, 212, SW - 36, 2, UI_GOLD);
    blit_sprite(fb, TV_US_CREST_BLUE + g_p1_side, 100, 54, 40, 40, 0xFFFF,
                VXPE_BLEND_ALPHA, 255, 0);
    draw_text_c(fb, SW / 2, 100, "TACTICS", VXPE_FONT_DISPLAY, 3, UI_GOLD,
                VXPE_FONT_OUTLINE | VXPE_FONT_BEVEL);
    draw_text_c(fb, SW / 2, 128, "VANGUARD", VXPE_FONT_DISPLAY, 3, UI_IVORY,
                VXPE_FONT_OUTLINE);
    draw_text_c(fb, SW / 2, 156, "A SIXTEEN PIXEL FIELD ENGAGEMENT",
                VXPE_FONT_UI, 1, UI_TEAL, 0);
    if (t > 20 && (t & 16))
        draw_text_c(fb, SW / 2, 176, "PRESS ANY KEY", VXPE_FONT_UI, 1, UI_IVORY,
                    VXPE_FONT_SHADOW);
    if (t > 30) {
        /* (t-30)*5 reaches 120 at t=54, so the fill has to be clamped or the
         * gold bar runs 20 px past the 100 px track for its last frames. */
        int n = (t - 30) * 5;
        if (n > 100) n = 100;
        vxpe2d_fill_rect(fb, SW, SH, 70, 194, 100, 5, vxpe2d_rgb565(40, 44, 60));
        vxpe2d_fill_rect(fb, SW, SH, 70, 194, n, 5, UI_GOLD);
    }
    draw_text_c(fb, SW / 2, 296, "VXPENGINE COREMRE SAMPLE", VXPE_FONT_UI, 1,
                vxpe2d_rgb565(118, 122, 138), 0);
}
#define MENU_ROW_X 24
#define MENU_ROW_W 192
#define MENU_ROW_H 20
#define MENU_ROW_Y0 150
#define MENU_ROW_STEP 26
enum { MI_BATTLE = 0, MI_SIDE, MI_HELP, MI_EXIT, MI_N };
static const char* const MENU4[MI_N] = { "BEGIN BATTLE", "CHANGE ARMY",
                                         "BRIEFING", "EXIT" };
static void draw_menu(uint16_t* fb) {
    int i, y, n = 0;
    char buf[40];
    backdrop(fb);
    draw_map(fb);
    draw_units(fb);
    scrim(fb, 178);
    vxpe2d_gradient_vertical(fb, SW, SH, 16, 38, SW - 32, 246,
                             vxpe2d_rgb565(26, 32, 58), vxpe2d_rgb565(12, 14, 26));
    frame4(fb, 14, 36, SW - 28, 250, UI_GOLD);
    blit_sprite(fb, TV_US_CREST_BLUE + g_p1_side, 24, 46, 24, 24, 0xFFFF,
                VXPE_BLEND_ALPHA, 255, 0);
    draw_text(fb, 56, 44, "VANGUARD", VXPE_FONT_DISPLAY, 2, UI_GOLD,
              VXPE_FONT_OUTLINE);
    draw_text(fb, 56, 68, "COMMAND SELECT", VXPE_FONT_UI, 1, UI_DIM, 0);
    vxpe2d_fill_rect(fb, SW, SH, 24, 86, SW - 48, 1, vxpe2d_rgb565(96, 78, 34));
    draw_text(fb, 24, 96, "ARMY:", VXPE_FONT_UI, 1, UI_IVORY, 0);
    draw_text(fb, 66, 96, side_name(), VXPE_FONT_UI, 1,
              g_p1_side ? UI_RED : UI_TEAL, VXPE_FONT_SHADOW);
    draw_text(fb, 138, 96, "4/6 SWITCH", VXPE_FONT_UI, 1, UI_DIM, 0);
    for (i = 0; i < g_nu; ++i)
        if (g_u[i].alive && g_u[i].side == g_p1_side) ++n;
    buf[0] = 0;
    app(buf, "UNITS ");
    appnum(buf, n);
    draw_text(fb, 24, 118, buf, VXPE_FONT_UI, 1, UI_DIM, 0);
    draw_text(fb, 132, 118, "15X17 FIELD", VXPE_FONT_UI, 1,
              vxpe2d_rgb565(104, 108, 124), 0);
    vxpe2d_fill_rect(fb, SW, SH, 24, 138, SW - 48, 1, vxpe2d_rgb565(96, 78, 34));
    y = MENU_ROW_Y0;
    for (i = 0; i < MI_N; ++i) {
        if (i == g_menu_i) {
            vxpe2d_overlay_rect(fb, SW, SH, MENU_ROW_X, y, MENU_ROW_W,
                                MENU_ROW_H, UI_TEAL, 74, VXPE_BLEND_ALPHA);
            vxpe2d_fill_rect(fb, SW, SH, MENU_ROW_X, y, 3, MENU_ROW_H, UI_GOLD);
        }
        draw_text(fb, MENU_ROW_X + 14, y + 6, MENU4[i], VXPE_FONT_UI, 1,
                  i == g_menu_i ? UI_IVORY : UI_DIM,
                  i == g_menu_i ? VXPE_FONT_SHADOW : 0);
        if (i == MI_SIDE)
            draw_text(fb, MENU_ROW_X + MENU_ROW_W - 58, y + 6, side_name(),
                      VXPE_FONT_UI, 1, g_p1_side ? UI_RED : UI_TEAL, 0);
        y += MENU_ROW_STEP;
    }
    draw_text_c(fb, SW / 2, 268, "2/8 MOVE  5 SELECT  7 BACK", VXPE_FONT_UI, 1,
                vxpe2d_rgb565(118, 122, 138), 0);
}
static const char* const HELP_KEYS[5] = {
    "2/4/6/8  MOVE CURSOR", "5/OK     CONFIRM", "7        STEP BACK",
    "9 OR *   END PHASE", "CLEAR    BACK OUT" };
static const char* const HELP_ORDER[4] = {
    "PICK ONE OF YOUR UNITS,", "WALK THE HATCHED FIELD,", "THEN CHOOSE FROM THE",
    "PARCHMENT CARD." };
static const char* const HELP_GROUND[6] = {
    "WOOD AND CLIFF GIVE", "DEFENCE. PLAIN AND ROAD", "ARE OPEN GROUND. THE",
    "RIVER ONLY CROSSES AT", "THREE BRIDGES, AND", "HORSES MAY NOT CLIMB." };
static const char* const HELP_LOSE[2] = {
    "LOSE YOUR SWORDSMAN AND", "THE FIELD IS LOST." };
#define HELP_PITCH 11
/* One framed card like the menu's: the primer is read at a glance on a handset,
 * so the blocks are separated by rules instead of blank lines. */
static int help_block(uint16_t* fb, const char* const* lines, int n, int y) {
    int i;
    for (i = 0; i < n; ++i) {
        draw_text(fb, 24, y, lines[i], VXPE_FONT_UI, 1, UI_IVORY, 0);
        y += HELP_PITCH;
    }
    return y + 3;
}
static void draw_help(uint16_t* fb) {
    int y;
    backdrop(fb);
    draw_map(fb);
    draw_units(fb);
    scrim(fb, 196);
    vxpe2d_gradient_vertical(fb, SW, SH, 16, 38, SW - 32, 258,
                             vxpe2d_rgb565(26, 32, 58),
                             vxpe2d_rgb565(12, 14, 26));
    frame4(fb, 14, 36, SW - 28, 262, UI_GOLD);
    blit_sprite(fb, TV_US_CREST_BLUE + g_p1_side, 24, 46, 24, 24, 0xFFFF,
                VXPE_BLEND_ALPHA, 255, 0);
    draw_text(fb, 56, 48, "TACTICS PRIMER", VXPE_FONT_DISPLAY, 1, UI_GOLD,
              VXPE_FONT_OUTLINE);
    vxpe2d_fill_rect(fb, SW, SH, 24, 76, SW - 48, 1, vxpe2d_rgb565(96, 78, 34));
    y = help_block(fb, HELP_KEYS, 5, 82);
    vxpe2d_fill_rect(fb, SW, SH, 24, y - 2, SW - 48, 1,
                     vxpe2d_rgb565(52, 56, 74));
    y = help_block(fb, HELP_ORDER, 4, y + 1);
    vxpe2d_fill_rect(fb, SW, SH, 24, y - 2, SW - 48, 1,
                     vxpe2d_rgb565(52, 56, 74));
    y = help_block(fb, HELP_GROUND, 6, y + 1);
    vxpe2d_fill_rect(fb, SW, SH, 24, y - 2, SW - 48, 1,
                     vxpe2d_rgb565(52, 56, 74));
    y = help_block(fb, HELP_LOSE, 2, y + 1);
    draw_text_c(fb, SW / 2, y + 4, "ANY KEY: BACK", VXPE_FONT_UI, 1, UI_TEAL, 0);
}

/* ---- simulation --------------------------------------------------------- */
static void begin_battle(void) {
    int i;
    parse_map();
    spawn_units();
    g_phase = BP_SELECT;
    g_round = 1;
    g_result = 0;
    g_sel = -1;
    g_ai_i = 0;
    g_ai_target = -1;
    g_active_side = g_p1_side;
    g_cur_x = 7;
    g_cur_y = 14;
    memset(g_seen, 0, sizeof(g_seen));
    for (i = 0; i < 6; ++i) { g_pop[i].live = 0; g_spk[i].live = 0; }
    for (i = 0; i < g_nu; ++i) {
        g_u[i].ax = g_u[i].ay = 0;
        g_u[i].pose = 0;
        g_u[i].done = 0;
    }
}
static void step_walk(void) {
    Unit* u;
    int tx, ty, dx, dy, step = 64;
    if (g_sel < 0) { g_phase = BP_SELECT; return; }
    u = &g_u[g_sel];
    if (g_walk_n == 0) {
        if (g_active_side != g_p1_side) {
            if (g_ai_target >= 0 && g_u[g_ai_target].alive)
                start_combat(g_sel, g_ai_target);
            else
                end_unit();
        } else {
            g_phase = BP_ACTION;
            g_row_sel = 0;
        }
        return;
    }
    tx = g_walkx[g_walk_i];
    ty = g_walky[g_walk_i];
    dx = (tx - u->x) * 256 + u->ax;
    dy = (ty - u->y) * 256 + u->ay;
    if (dx) u->ax += (int8_t)(dx > 0 ? step : -step);
    if (dy) u->ay += (int8_t)(dy > 0 ? step : -step);
    if (dx) u->face = (dx > 0) ? 1 : -1;
    u->pose = 1;
    if (iabs(u->ax - (tx - u->x) * 256) <= step &&
        iabs(u->ay - (ty - u->y) * 256) <= step) {
        u->x = (int16_t)tx;
        u->y = (int16_t)ty;
        u->ax = u->ay = 0;
        ++g_walk_i;
        if (g_walk_i >= g_walk_n) {
            u->pose = 0;
            g_walk_n = 0;
            if (g_active_side != g_p1_side) {
                if (g_ai_target >= 0 && g_u[g_ai_target].alive)
                    start_combat(g_sel, g_ai_target);
                else
                    end_unit();
            } else {
                g_phase = BP_ACTION;
                g_row_sel = 0;
            }
        }
    }
}
static void update(void) {
    int i;
    ++g_tick;
    g_water_f = (g_tick >> 3) % 3;
    for (i = 0; i < 6; ++i)
        if (g_pop[i].live && ++g_pop[i].t > 34) g_pop[i].live = 0;
    for (i = 0; i < 6; ++i)
        if (g_spk[i].live && ++g_spk[i].t > 9) g_spk[i].live = 0;
    if (g_screen == SCR_SPLASH) {
        if (g_splash_t < 78) ++g_splash_t;
        else g_screen = SCR_MENU;
        return;
    }
    if (g_screen != SCR_BATTLE) return;
    switch (g_phase) {
    case BP_WALK:
        step_walk();
        break;
    case BP_CUTIN:
        if (++g_band_t == 10) deliver(0);
        else if (g_band_t > 34) {
            g_phase = BP_HIT;
            g_beat_t = 0;
        }
        break;
    case BP_HIT:
        if (++g_beat_t > 22) {
            if (g_beat == 0 && g_blow[1].valid && g_u[g_band_a].alive &&
                g_u[g_band_d].alive)
                deliver(1);
            else
                end_unit();
        }
        break;
    case BP_ENEMY:
        if (!ai_next_unit()) start_new_round();
        break;
    default:
        break;
    }
}

/* ---- input -------------------------------------------------------------- */
static int menu_row_at(int x, int y) {
    int i;
    if (x < MENU_ROW_X - 6 || x > MENU_ROW_X + MENU_ROW_W + 8) return -1;
    for (i = 0; i < MI_N; ++i) {
        int ry = MENU_ROW_Y0 + i * MENU_ROW_STEP;
        if (y >= ry && y < ry + MENU_ROW_H) return i;
    }
    return -1;
}
static int card_row_at(int x, int y) {
    int i;
    if (x < CARD_X || x > CARD_X + CARD_W) return -1;
    for (i = 0; i < ACT_N; ++i) {
        int ry = ROW_Y0 + i * ROW_STEP;
        if (y >= ry - 4 && y < ry + ROW_STEP - 4) return i;
    }
    return -1;
}
static void stop(void);
static void menu_pick(int i) {
    switch (i) {
    case MI_BATTLE: begin_battle(); g_screen = SCR_BATTLE; break;
    case MI_SIDE:   g_p1_side = 1 - g_p1_side; break;
    case MI_HELP:   g_screen = SCR_HELP; break;
    default:        stop(); vm_exit_app(); break;
    }
}
static void cursor_move(int dx, int dy) {
    g_cur_x += dx;
    g_cur_y += dy;
    if (g_cur_x < 0) g_cur_x = MW - 1;
    if (g_cur_x >= MW) g_cur_x = 0;
    if (g_cur_y < 0) g_cur_y = MH - 1;
    if (g_cur_y >= MH) g_cur_y = 0;
}
static int selectable_here(void) {
    int i = unit_at(g_cur_x, g_cur_y);
    if (i < 0 || g_u[i].side != g_p1_side || g_u[i].done) return -1;
    return i;
}
static void do_action(int row) {
    Unit* u = &g_u[g_sel];
    if (row != ACT_ATTACK || g_result) { end_unit(); return; }
    compute_attack(g_sel, u->x, u->y);
    if (!targets_in_attack_range(g_sel)) { end_unit(); return; }
    g_phase = BP_TARGET;
}
static void try_attack_target(void) {
    int i = unit_at(g_cur_x, g_cur_y);
    if (i < 0 || g_u[i].side == g_p1_side) return;
    if (!g_atk[g_u[i].y][g_u[i].x]) return;
    start_combat(g_sel, i);
}
static void confirm(void) {
    switch (g_phase) {
    case BP_SELECT:
        if (g_active_side != g_p1_side) return;
        {
            int i = selectable_here();
            if (i < 0) return;
            g_sel = i;
            compute_range(i);
            g_phase = BP_RANGE;
        }
        break;
    case BP_RANGE:
        if (!in_range(g_cur_x, g_cur_y)) return;
        if (g_cur_x == g_u[g_sel].x && g_cur_y == g_u[g_sel].y) {
            g_walk_n = g_walk_i = 0;
            g_phase = BP_ACTION;
            g_row_sel = 0;
            return;
        }
        if (!standable(g_cur_x, g_cur_y, g_sel)) return;
        if (!build_path(g_sel, g_cur_x, g_cur_y)) return;
        g_phase = BP_WALK;
        break;
    case BP_ACTION:
        do_action(g_row_sel);
        break;
    case BP_TARGET:
        try_attack_target();
        break;
    case BP_RESULT:
        if (g_result == 2) g_screen = SCR_MENU;
        else begin_battle();
        break;
    default: break;
    }
}
static void back_out(void) {
    if (g_phase == BP_TARGET) { g_phase = BP_ACTION; return; }
    if ((g_phase == BP_ACTION || g_phase == BP_RANGE) && g_sel >= 0) {
        g_u[g_sel].pose = 0;
        g_sel = -1;
        g_phase = BP_SELECT;
        return;
    }
    g_screen = SCR_MENU;
}
static void end_phase(void) {
    int i;
    if (g_active_side != g_p1_side || g_phase > BP_TARGET) return;
    for (i = 0; i < g_nu; ++i)
        if (g_u[i].alive && g_u[i].side == g_p1_side) g_u[i].done = 1;
    g_sel = -1;
    g_active_side = 1 - g_p1_side;
    g_ai_i = 0;
    g_phase = BP_ENEMY;
}
static void row_move(int d) {
    g_row_sel += d;
    if (g_row_sel < 0) g_row_sel = ACT_N - 1;
    if (g_row_sel >= ACT_N) g_row_sel = 0;
}
static void handle_key(int keycode) {
    if (g_screen == SCR_SPLASH) { g_screen = SCR_MENU; return; }
    if (g_screen == SCR_HELP) { g_screen = SCR_MENU; return; }
    if (g_screen == SCR_MENU) {
        switch (keycode) {
        case VM_KEY_UP: case VM_KEY_NUM2:
            g_menu_i = (g_menu_i + MI_N - 1) % MI_N; break;
        case VM_KEY_DOWN: case VM_KEY_NUM8:
            g_menu_i = (g_menu_i + 1) % MI_N; break;
        case VM_KEY_LEFT: case VM_KEY_NUM4:
            if (g_menu_i == MI_SIDE) g_p1_side = 0;
            else g_menu_i = (g_menu_i + MI_N - 1) % MI_N;
            break;
        case VM_KEY_RIGHT: case VM_KEY_NUM6:
            if (g_menu_i == MI_SIDE) g_p1_side = 1;
            else g_menu_i = (g_menu_i + 1) % MI_N;
            break;
        case VM_KEY_OK: case VM_KEY_NUM5: menu_pick(g_menu_i); break;
        case VM_KEY_RIGHT_SOFTKEY: case VM_KEY_CLEAR: case VM_KEY_BACK:
            stop(); vm_exit_app(); break;
        default: break;
        }
        return;
    }
    if (g_phase == BP_ACTION) {
        switch (keycode) {
        case VM_KEY_UP: case VM_KEY_NUM2: row_move(-1); break;
        case VM_KEY_DOWN: case VM_KEY_NUM8: row_move(1); break;
        case VM_KEY_OK: case VM_KEY_NUM5: do_action(g_row_sel); break;
        case VM_KEY_NUM7: case VM_KEY_BACK: back_out(); break;
        case VM_KEY_CLEAR: g_screen = SCR_MENU; break;
        case VM_KEY_RIGHT_SOFTKEY: stop(); vm_exit_app(); break;
        default: break;
        }
        return;
    }
    switch (keycode) {
    case VM_KEY_UP: case VM_KEY_NUM2: cursor_move(0, -1); break;
    case VM_KEY_DOWN: case VM_KEY_NUM8: cursor_move(0, 1); break;
    case VM_KEY_LEFT: case VM_KEY_NUM4: cursor_move(-1, 0); break;
    case VM_KEY_RIGHT: case VM_KEY_NUM6: cursor_move(1, 0); break;
    case VM_KEY_OK: case VM_KEY_NUM5: case VM_KEY_POUND: confirm(); break;
    case VM_KEY_NUM7: case VM_KEY_BACK: back_out(); break;
    case VM_KEY_NUM9: case VM_KEY_STAR: end_phase(); break;
    case VM_KEY_CLEAR: g_screen = SCR_MENU; break;
    case VM_KEY_RIGHT_SOFTKEY: stop(); vm_exit_app(); break;
    default: break;
    }
}

/* ---- app lifecycle ------------------------------------------------------ */
static void draw(void) {
    VMUINT16* fb = framebuffer();
    uint32_t t0;
    if (!fb) return;
    t0 = vm_get_tick_count();
    switch (g_screen) {
    case SCR_SPLASH: draw_splash(fb); break;
    case SCR_MENU:   draw_menu(fb); break;
    case SCR_HELP:   draw_help(fb); break;
    default:         draw_battle(fb); break;
    }
    g_frame_ms = (int)(vm_get_tick_count() - t0);
    vm_graphic_flush_layer(&g_layer, 1);
}
/* VXPEmu fires the app timer at whatever rate it can paint, so the simulation
 * steps on wall-clock time and plays the same on a handset. */
#define STEP_MS 33
static void tick(VMINT tid) {
    static uint32_t last_ms;
    static int acc;
    uint32_t now = vm_get_tick_count();
    int32_t dt = (int32_t)(now - last_ms);
    (void)tid;
    if (!last_ms || dt > 200) dt = STEP_MS;
    last_ms = now;
    for (acc += dt; acc >= STEP_MS; acc -= STEP_MS) update();
    draw();
}
static void start(void) {
    if (g_layer < 0) g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    parse_map();
    spawn_units();
    g_screen = SCR_SPLASH;
    g_splash_t = 0;
    g_menu_i = 0;
    if (g_timer < 0) g_timer = vm_create_timer(50, tick);
    draw();
}
static void stop(void) {
    if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }
    if (g_layer >= 0) { vm_graphic_delete_layer(g_layer); g_layer = -1; }
}
void handle_sysevt(VMINT message, VMINT param) {
    (void)param;
    switch (message) {
    case VM_MSG_CREATE:
    case VM_MSG_ACTIVE: start(); break;
    case VM_MSG_PAINT: draw(); break;
    case VM_MSG_INACTIVE:
    case VM_MSG_QUIT:
        stop();
        if (message == VM_MSG_QUIT) vm_exit_app();
        break;
    default: break;
    }
}
void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN) handle_key(keycode);
}
void handle_penevt(VMINT event, VMINT x, VMINT y) {
    if (event != VM_PEN_EVENT_TAP) return;
    if (g_screen == SCR_SPLASH) { g_screen = SCR_MENU; return; }
    if (g_screen == SCR_HELP) { g_screen = SCR_MENU; return; }
    if (g_screen == SCR_MENU) {
        int row = menu_row_at(x, y);
        if (row >= 0) { g_menu_i = row; menu_pick(row); }
        return;
    }
    if (g_phase == BP_ACTION) {
        int row = card_row_at(x, y);
        if (row >= 0) { g_row_sel = row; do_action(row); }
        return;
    }
    if (y < MAP_Y || y >= MAP_Y + MAP_H) return;
    {
        int tx = x / TS, ty = (y - MAP_Y) / TS, same;
        if (tx < 0 || ty < 0 || tx >= MW || ty >= MH) return;
        same = (tx == g_cur_x && ty == g_cur_y);
        g_cur_x = tx;
        g_cur_y = ty;
        if (same) confirm();
        else if (g_phase == BP_SELECT && selectable_here() >= 0) confirm();
    }
}
void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
