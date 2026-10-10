/* TacticsKingdom - 240x320 turn-based tactics sample (Fire-Emblem-like).
 *
 * 15x20 grid of 16px tiles: grass, tree, mountain, water, path, castles.
 * 4 blue knights vs 3 red soldiers. Cursor (arrows), OK selects/moves,
 * blue overlay = move range (BFS), auto-attack adjacent foe, enemy phase
 * with greedy AI, castles heal, win/lose + restart. All art procedural.
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define SW 240
#define SH 320
#define COLS 15
#define ROWS 20
#define TS 16

/* terrain */
enum { T_GRASS, T_TREE, T_MOUNT, T_WATER, T_PATH, T_CASTLE, T_TOWER };
static uint8_t g_map[ROWS][COLS];

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static uint32_t g_tick = 0;
static uint32_t g_rng = 0x7AC71C5u;

/* cursor + selection */
static int g_cx = 7, g_cy = 10;
static int g_sel = -1;          /* selected player unit index */
static int g_phase = 0;         /* 0 player, 1 enemy, 2 over */
static int g_result = 0;        /* 0 none, 1 win, 2 lose */
static int g_turn = 1;
static int g_hit_x = -1, g_hit_y = -1, g_hit_t = 0;

#define MAXU 7
typedef struct Unit {
    int active;
    int side; /* 0 player, 1 enemy */
    int x, y;
    int hp, max_hp;
    int move, atk;
    int moved;
} Unit;
static Unit g_units[MAXU];
static int g_unit_count = 0;

/* BFS distances for current selection */
static int8_t g_reach[ROWS][COLS];

static uint16_t g_tiles[7][256]; /* terrain tilesets, opaque */

static uint16_t g_knight_px[256]; static uint8_t g_knight_a[256];
static uint16_t g_foe_px[256];    static uint8_t g_foe_a[256];

static uint32_t rnd32(void) {
    g_rng = g_rng * 1664525u + 1013904223u;
    return g_rng;
}

static VMUINT16* framebuffer(void) {
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}

static void px(uint16_t* fb, int x, int y, uint16_t c) {
    if ((unsigned)x < (unsigned)SW && (unsigned)y < (unsigned)SH)
        fb[y * SW + x] = c;
}

static void bar(uint16_t* fb, int x, int y, int w, int h, uint16_t c) {
    int i, j;
    for (j = 0; j < h; ++j)
        for (i = 0; i < w; ++i)
            px(fb, x + i, y + j, c);
}

static void frame(uint16_t* fb, int x, int y, int w, int h, uint16_t c) {
    int i;
    for (i = 0; i < w; ++i) { px(fb, x + i, y, c); px(fb, x + i, y + h - 1, c); }
    for (i = 0; i < h; ++i) { px(fb, x, y + i, c); px(fb, x + w - 1, y + i, c); }
}

/* ---------- procedural tiles ---------- */
static uint16_t grass_c(int x, int y) {
    uint32_t h = (uint32_t)(x * 73 + y * 149);
    h = (h ^ (h >> 3)) & 7;
    return vxpe2d_rgb565((uint8_t)(104 + h * 3), (uint8_t)(168 + h * 4),
                         (uint8_t)(70 + h * 2));
}

static void build_tiles(void) {
    int t, x, y;
    for (t = 0; t < 7; ++t)
        for (y = 0; y < 16; ++y)
            for (x = 0; x < 16; ++x) {
                uint16_t c = grass_c(x, y);
                if (t == T_TREE) {
                    int dx = x - 8, dy = y - 7;
                    int d2 = dx * dx + dy * dy;
                    if (d2 < 34) {
                        c = vxpe2d_rgb565(34, 110, 44);
                        if (((x + y) & 3) == 0)
                            c = vxpe2d_rgb565(52, 140, 60);
                        if (dx == 0 && dy > 2)
                            c = vxpe2d_rgb565(110, 70, 40);
                    }
                } else if (t == T_MOUNT) {
                    int ridge = 8 - (x > 8 ? x - 8 : 8 - x);
                    if (y > 14 - ridge && ridge > 0) {
                        int shade = (x + y) & 1;
                        c = shade ? vxpe2d_rgb565(120, 118, 130)
                                  : vxpe2d_rgb565(88, 86, 98);
                        if (y < 16 - ridge - 3)
                            c = vxpe2d_rgb565(235, 235, 245);
                    }
                } else if (t == T_WATER) {
                    int wv = ((x + y * 2) & 7) < 4 ? 0 : 12;
                    c = vxpe2d_rgb565((uint8_t)(30 + wv), (uint8_t)(90 + wv),
                                      (uint8_t)(170 + wv));
                    if (((x * 3 + y) & 15) == 0)
                        c = vxpe2d_rgb565(150, 210, 240);
                } else if (t == T_PATH) {
                    c = vxpe2d_rgb565(212, 196, 150);
                    if (((x * 5 + y * 3) & 7) == 0)
                        c = vxpe2d_rgb565(190, 172, 128);
                } else if (t == T_CASTLE) {
                    c = grass_c(x, y);
                    if (y >= 4 && y < 13 && x >= 2 && x < 14) {
                        c = vxpe2d_rgb565(170, 130, 80);
                        if (((x + y) & 3) == 0)
                            c = vxpe2d_rgb565(150, 110, 66);
                        if (y < 6) c = vxpe2d_rgb565(200, 90, 60);
                        if (x == 7 || x == 8) {
                            if (y >= 8) c = vxpe2d_rgb565(60, 40, 30);
                            else c = vxpe2d_rgb565(60, 90, 200);
                        }
                    }
                } else if (t == T_TOWER) {
                    c = grass_c(x, y);
                    if (y >= 2 && y < 14 && x >= 3 && x < 13) {
                        c = vxpe2d_rgb565(130, 130, 145);
                        if (((x + y) & 3) == 0)
                            c = vxpe2d_rgb565(110, 110, 125);
                        if (y < 4) c = vxpe2d_rgb565(200, 60, 60);
                        if (x >= 7 && x <= 8 && y >= 6 && y < 11)
                            c = vxpe2d_rgb565(40, 40, 55);
                    }
                }
                g_tiles[t][y * 16 + x] = c;
            }
    /* knight (blue) */
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            int dx = x - 8;
            if (y >= 3 && y < 7 && dx >= -3 && dx <= 3) {
                /* helmet */
                a = 1; c = vxpe2d_rgb565(200, 205, 220);
                if (y == 5) c = vxpe2d_rgb565(60, 90, 200);
                if (dx == 0 && y >= 5) c = vxpe2d_rgb565(230, 80, 70);
            } else if (y >= 7 && y < 12 && dx >= -4 && dx <= 4) {
                /* armor */
                a = 1; c = vxpe2d_rgb565(70, 110, 210);
                if (dx == -4 || dx == 4) c = vxpe2d_rgb565(50, 80, 170);
                if (y == 7) c = vxpe2d_rgb565(150, 170, 230);
            } else if (y >= 12 && y < 15 && dx >= -3 && dx <= 3) {
                a = 1; c = vxpe2d_rgb565(90, 70, 60);
            } else if (x >= 11 && x < 13 && y >= 6 && y < 13) {
                /* sword */
                a = 1; c = vxpe2d_rgb565(225, 230, 240);
            }
            g_knight_px[y * 16 + x] = c; g_knight_a[y * 16 + x] = a;
        }
    /* foe soldier (red/dark) */
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x) {
            uint16_t c = 0; uint8_t a = 0;
            int dx = x - 8;
            if (y >= 2 && y < 6 && dx >= -4 && dx <= 4) {
                a = 1; c = vxpe2d_rgb565(150, 155, 170);
                if (dx >= -1 && dx <= 1 && y >= 3)
                    c = vxpe2d_rgb565(40, 40, 55);
            } else if (y >= 6 && y < 12 && dx >= -4 && dx <= 4) {
                a = 1; c = vxpe2d_rgb565(170, 60, 60);
                if (dx == -4 || dx == 4) c = vxpe2d_rgb565(130, 40, 40);
            } else if (y >= 12 && y < 15 && dx >= -3 && dx <= 3) {
                a = 1; c = vxpe2d_rgb565(70, 55, 50);
            } else if (x >= 3 && x < 5 && y >= 6 && y < 13) {
                a = 1; c = vxpe2d_rgb565(120, 120, 135);
            }
            g_foe_px[y * 16 + x] = c; g_foe_a[y * 16 + x] = a;
        }
}

/* ---------- map ---------- */
static int in_bounds(int x, int y) {
    return x >= 0 && y >= 0 && x < COLS && y < ROWS;
}

static void build_map(void) {
    int x, y;
    for (y = 0; y < ROWS; ++y)
        for (x = 0; x < COLS; ++x) {
            uint8_t t = T_GRASS;
            /* mountains: left edge cluster + few peaks */
            if ((x <= 1 && (y + x) % 3 != 0 && y < 12) ||
                (x == 5 && (y == 5 || y == 6)) ||
                ((x == 12 || x == 13) && (y == 8 || y == 9)))
                t = T_MOUNT;
            /* lake top-right */
            if (x >= 7 && x <= 11 && y <= 4 && !(x == 7 && y == 4))
                t = T_WATER;
            /* pond bottom */
            {
                int dx = x - 8, dy = y - 17;
                if (dx * dx + dy * dy * 2 <= 8) t = T_WATER;
            }
            /* paths: horizontal row 8 + vertical col 3 + curve */
            if (y == 8 || x == 3 || (y == 12 && x >= 3 && x <= 9) ||
                (x == 9 && y >= 8 && y <= 12))
                if (t == T_GRASS) t = T_PATH;
            /* trees scattered (not on path/water) */
            if (t == T_GRASS && ((x * 31 + y * 57) & 7) == 0)
                t = T_TREE;
            g_map[y][x] = t;
        }
    /* castle (player base) + enemy tower */
    g_map[6][2] = T_CASTLE;
    g_map[5][11] = T_TOWER;
}

static int move_cost(int x, int y) {
    uint8_t t;
    if (!in_bounds(x, y)) return 99;
    t = g_map[y][x];
    if (t == T_WATER) return 99;
    if (t == T_MOUNT) return 3;
    if (t == T_TREE) return 2;
    return 1;
}

static int unit_at(int x, int y) {
    int i;
    for (i = 0; i < g_unit_count; ++i)
        if (g_units[i].active && g_units[i].x == x && g_units[i].y == y)
            return i;
    return -1;
}

/* ---------- units ---------- */
static void add_unit(int side, int x, int y, int hp, int move, int atk) {
    Unit* u = &g_units[g_unit_count++];
    u->active = 1; u->side = side; u->x = x; u->y = y;
    u->hp = hp; u->max_hp = hp; u->move = move; u->atk = atk; u->moved = 0;
}

static void reset_game(void) {
    int i;
    g_unit_count = 0;
    add_unit(0, 2, 7, 12, 5, 4);
    add_unit(0, 4, 7, 12, 5, 4);
    add_unit(0, 3, 9, 14, 4, 5);
    add_unit(0, 5, 10, 10, 6, 3);
    add_unit(1, 11, 4, 9, 4, 3);
    add_unit(1, 12, 7, 9, 4, 3);
    add_unit(1, 10, 11, 11, 4, 4);
    for (i = 0; i < g_unit_count; ++i) g_units[i].moved = 0;
    g_cx = 3; g_cy = 8; g_sel = -1;
    g_phase = 0; g_result = 0; g_turn = 1;
    g_hit_x = -1; g_hit_t = 0;
    for (i = 0; i < ROWS; ++i)
        memset(g_reach[i], -1, COLS);
}

/* ---------- BFS range ---------- */
static void bfs_range(Unit* u) {
    static int qx[300], qy[300];
    int head = 0, tail = 0, x, y, d;
    int i;
    for (y = 0; y < ROWS; ++y)
        for (x = 0; x < COLS; ++x) g_reach[y][x] = -1;
    g_reach[u->y][u->x] = 0;
    qx[tail] = u->x; qy[tail] = u->y; tail++;
    while (head < tail) {
        static const int8_t DX[4] = {1, -1, 0, 0};
        static const int8_t DY[4] = {0, 0, 1, -1};
        x = qx[head]; y = qy[head]; head++;
        d = g_reach[y][x];
        for (i = 0; i < 4; ++i) {
            int nx = x + DX[i], ny = y + DY[i];
            int nd, ui;
            if (!in_bounds(nx, ny) || g_reach[ny][nx] >= 0) continue;
            nd = d + move_cost(nx, ny);
            if (nd > u->move) continue;
            ui = unit_at(nx, ny);
            if (ui >= 0 && ui != (int)(u - g_units)) continue; /* blocked */
            g_reach[ny][nx] = (int8_t)nd;
            qx[tail] = nx; qy[tail] = ny; tail++;
        }
    }
}

/* ---------- combat ---------- */
static int adjacent_foe(int ui, int* best) {
    static const int8_t DX[4] = {1, -1, 0, 0};
    static const int8_t DY[4] = {0, 0, 1, -1};
    int i, found = -1, besthp = 999;
    for (i = 0; i < 4; ++i) {
        int nx = g_units[ui].x + DX[i], ny = g_units[ui].y + DY[i];
        int vi;
        if (!in_bounds(nx, ny)) continue;
        vi = unit_at(nx, ny);
        if (vi >= 0 && g_units[vi].side != g_units[ui].side &&
            g_units[vi].hp < besthp) {
            besthp = g_units[vi].hp;
            found = vi;
        }
    }
    if (best) *best = found;
    return found;
}

static void strike(int atk, int def) {
    int dmg = g_units[atk].atk + (int)(rnd32() % 3) - 1;
    if (dmg < 1) dmg = 1;
    /* castle guard: half damage on own base */
    if ((g_units[def].side == 0 && g_map[g_units[def].y][g_units[def].x] == T_CASTLE) ||
        (g_units[def].side == 1 && g_map[g_units[def].y][g_units[def].x] == T_TOWER))
        dmg = (dmg + 1) / 2;
    g_units[def].hp -= dmg;
    g_hit_x = g_units[def].x; g_hit_y = g_units[def].y; g_hit_t = 8;
    if (g_units[def].hp <= 0) {
        g_units[def].hp = 0;
        g_units[def].active = 0;
    }
}

static int side_alive(int side) {
    int i, n = 0;
    for (i = 0; i < g_unit_count; ++i)
        if (g_units[i].active && g_units[i].side == side) n++;
    return n;
}

static void check_end(void) {
    if (!side_alive(1)) { g_phase = 2; g_result = 1; }
    else if (!side_alive(0)) { g_phase = 2; g_result = 2; }
}

/* enemy AI: step toward nearest player, attack if adjacent */
static void enemy_turn(void) {
    int i, x, y;
    for (i = 0; i < g_unit_count; ++i) {
        Unit* e;
        int vi, bx = 0, by = 0, best = 9999, bd = 0;
        static const int8_t DX[4] = {1, -1, 0, 0};
        static const int8_t DY[4] = {0, 0, 1, -1};
        if (!g_units[i].active || g_units[i].side != 1) continue;
        e = &g_units[i];
        bfs_range(e);
        /* nearest player */
        for (vi = 0; vi < g_unit_count; ++vi) {
            int d;
            if (!g_units[vi].active || g_units[vi].side != 0) continue;
            d = abs(e->x - g_units[vi].x) + abs(e->y - g_units[vi].y);
            if (d < best) { best = d; bd = vi; }
        }
        if (best == 9999) continue;
        /* best reachable cell: min manhattan to target */
        bx = e->x; by = e->y;
        for (y = 0; y < ROWS; ++y)
            for (x = 0; x < COLS; ++x) {
                int d;
                if (g_reach[y][x] < 0) continue;
                d = abs(x - g_units[bd].x) + abs(y - g_units[bd].y);
                if (d < best) { best = d; bx = x; by = y; }
            }
        e->x = bx; e->y = by;
        if (adjacent_foe(i, &vi))
            strike(i, vi);
        check_end();
        if (g_phase == 2) return;
    }
    /* new player turn: reset + heal on castle */
    for (i = 0; i < g_unit_count; ++i) {
        if (!g_units[i].active) continue;
        g_units[i].moved = 0;
        if (g_units[i].side == 0 &&
            g_map[g_units[i].y][g_units[i].x] == T_CASTLE &&
            g_units[i].hp < g_units[i].max_hp) {
            g_units[i].hp += 2;
            if (g_units[i].hp > g_units[i].max_hp)
                g_units[i].hp = g_units[i].max_hp;
        }
    }
    g_turn++;
    g_phase = 0;
    g_sel = -1;
}

static void player_confirm(void) {
    int ui = unit_at(g_cx, g_cy);
    if (g_sel < 0) {
        /* select own unmoved unit */
        if (ui >= 0 && g_units[ui].side == 0 && !g_units[ui].moved) {
            g_sel = ui;
            bfs_range(&g_units[ui]);
        }
        return;
    }
    if (ui == g_sel) { g_sel = -1; return; } /* deselect */
    if (g_reach[g_cy][g_cx] >= 0 && unit_at(g_cx, g_cy) < 0) {
        Unit* u = &g_units[g_sel];
        int vi;
        u->x = g_cx; u->y = g_cy; u->moved = 1;
        if (adjacent_foe(g_sel, &vi))
            strike(g_sel, vi);
        g_sel = -1;
        check_end();
        if (g_phase == 2) return;
        /* all moved -> enemy phase */
        {
            int i, rest = 0;
            for (i = 0; i < g_unit_count; ++i)
                if (g_units[i].active && g_units[i].side == 0 && !g_units[i].moved)
                    rest++;
            if (!rest) {
                int y, x;
                g_phase = 1;
                for (y = 0; y < ROWS; ++y)
                    for (x = 0; x < COLS; ++x) g_reach[y][x] = -1;
            }
        }
    } else {
        g_sel = -1;
    }
}

/* ---------- draw ---------- */
static void draw_sprite(uint16_t* fb, int dx, int dy,
                        const uint16_t* pxs, const uint8_t* a) {
    int x, y;
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x)
            if (a[y * 16 + x]) px(fb, dx + x, dy + y, pxs[y * 16 + x]);
}

static void draw_hud(uint16_t* fb) {
    int i, n = 0;
    /* phase bar: blue player / red enemy / gold end */
    uint16_t pc = g_phase == 0 ? vxpe2d_rgb565(80, 140, 240)
                 : g_phase == 1 ? vxpe2d_rgb565(230, 80, 80)
                                : vxpe2d_rgb565(240, 200, 80);
    bar(fb, 0, 0, SW, 3, pc);
    /* turn pips */
    for (i = 0; i < 8 && i < g_turn; ++i)
        bar(fb, 4 + i * 7, 5, 5, 3, vxpe2d_rgb565(150, 170, 200));
    /* remaining units */
    for (i = 0; i < g_unit_count; ++i)
        if (g_units[i].active && g_units[i].side == 0) {
            uint16_t c = g_units[i].moved ? vxpe2d_rgb565(90, 100, 130)
                                          : vxpe2d_rgb565(120, 180, 250);
            bar(fb, SW - 12 - n * 12, 5, 8, 5, c);
            n++;
        }
}

static void draw(void) {
    VMUINT16* fb = framebuffer();
    int x, y, i;
    if (!fb) return;
    /* terrain */
    for (y = 0; y < ROWS; ++y)
        for (x = 0; x < COLS; ++x) {
            uint16_t* t = g_tiles[g_map[y][x]];
            int px_, py_;
            int water_anim = (g_map[y][x] == T_WATER) ? ((g_tick >> 2) & 1) : 0;
            for (py_ = 0; py_ < 16; ++py_)
                for (px_ = 0; px_ < 16; ++px_) {
                    uint16_t c = t[py_ * 16 + px_];
                    if (water_anim && ((px_ + py_) & 7) == 0)
                        c = vxpe2d_rgb565(150, 210, 240);
                    fb[(y * 16 + py_) * SW + x * 16 + px_] = c;
                }
        }
    /* move-range overlay (hatched blue like reference) */
    if (g_sel >= 0 && g_phase == 0) {
        for (y = 0; y < ROWS; ++y)
            for (x = 0; x < COLS; ++x) {
                int px_, py_;
                if (g_reach[y][x] < 0) continue;
                for (py_ = 0; py_ < 16; py_ += 2)
                    for (px_ = ((y + py_) & 1); px_ < 16; px_ += 2)
                        px(fb, x * 16 + px_, y * 16 + py_,
                           vxpe2d_rgb565(120, 180, 250));
            }
    }
    /* units sorted by y */
    {
        int order[MAXU], n = 0, a, b;
        for (i = 0; i < g_unit_count; ++i)
            if (g_units[i].active) order[n++] = i;
        for (a = 0; a < n; ++a)
            for (b = a + 1; b < n; ++b)
                if (g_units[order[b]].y < g_units[order[a]].y) {
                    int t = order[a]; order[a] = order[b]; order[b] = t;
                }
        for (a = 0; a < n; ++a) {
            Unit* u = &g_units[order[a]];
            int dx = u->x * 16, dy = u->y * 16;
            int flash = (order[a] == g_sel) && ((g_tick & 8) == 0);
            int hit = (u->x == g_hit_x && u->y == g_hit_y && g_hit_t > 0);
            if (!flash && !hit) {
                if (u->side == 0)
                    draw_sprite(fb, dx, dy, g_knight_px, g_knight_a);
                else
                    draw_sprite(fb, dx, dy, g_foe_px, g_foe_a);
            } else {
                bar(fb, dx + 2, dy + 2, 12, 12,
                    hit ? vxpe2d_rgb565(255, 255, 255)
                        : vxpe2d_rgb565(250, 220, 100));
            }
            /* hp pips */
            {
                int w = u->hp * 14 / u->max_hp;
                uint16_t c = u->side == 0 ? vxpe2d_rgb565(90, 230, 120)
                                          : vxpe2d_rgb565(235, 90, 90);
                bar(fb, dx + 1, dy - 3 < 0 ? 0 : dy - 3, 14, 2,
                    vxpe2d_rgb565(20, 22, 34));
                bar(fb, dx + 1, dy - 3 < 0 ? 0 : dy - 3, w, 2, c);
            }
        }
    }
    /* selected frame */
    if (g_sel >= 0) {
        Unit* u = &g_units[g_sel];
        frame(fb, u->x * 16 - 1, u->y * 16 - 1, 18, 18,
              vxpe2d_rgb565(250, 220, 100));
    }
    /* cursor */
    if (g_phase != 2)
        frame(fb, g_cx * 16, g_cy * 16, 16, 16,
              vxpe2d_rgb565(245, 245, 250));
    /* enemy-attack warning: red frame on cursor cell foe */
    {
        int ui = unit_at(g_cx, g_cy);
        if (ui >= 0 && g_units[ui].side == 1 && g_phase == 0)
            frame(fb, g_cx * 16 + 2, g_cy * 16 + 2, 12, 12,
                  vxpe2d_rgb565(235, 70, 70));
    }
    /* end banner */
    if (g_phase == 2) {
        int x0, y0;
        for (y0 = 140; y0 < 180; ++y0)
            for (x0 = 50; x0 < SW - 50; ++x0)
                if (x0 == 50 || x0 == SW - 51 || y0 == 140 || y0 == 179)
                    px(fb, x0, y0, vxpe2d_rgb565(240, 240, 245));
                else if (((x0 + y0) & 1) == 0)
                    px(fb, x0, y0, g_result == 1 ? vxpe2d_rgb565(40, 90, 160)
                                                 : vxpe2d_rgb565(140, 50, 50));
        if ((g_tick & 16) == 0)
            bar(fb, SW / 2 - 20, 162, 40, 6,
                vxpe2d_rgb565(250, 220, 100));
    }
    draw_hud(fb);
    vm_graphic_flush_layer(&g_layer, 1);
}

static void tick(VMINT tid) {
    (void)tid;
    g_tick++;
    if (g_hit_t > 0) g_hit_t--;
    if (g_phase == 1) {
        /* run enemy phase inside tick (fast, few units) */
        enemy_turn();
    }
    draw();
}

static void start(void) {
    if (g_layer < 0)
        g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    build_tiles();
    build_map();
    reset_game();
    if (g_timer < 0) g_timer = vm_create_timer(120, tick);
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
    }
}

static void move_cursor(int dx, int dy) {
    g_cx += dx; g_cy += dy;
    if (g_cx < 0) g_cx = 0;
    if (g_cy < 0) g_cy = 0;
    if (g_cx >= COLS) g_cx = COLS - 1;
    if (g_cy >= ROWS) g_cy = ROWS - 1;
}

void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN) {
        switch (keycode) {
        case VM_KEY_LEFT: case VM_KEY_NUM4: move_cursor(-1, 0); break;
        case VM_KEY_RIGHT: case VM_KEY_NUM6: move_cursor(1, 0); break;
        case VM_KEY_UP: case VM_KEY_NUM2: move_cursor(0, -1); break;
        case VM_KEY_DOWN: case VM_KEY_NUM8: move_cursor(0, 1); break;
        case VM_KEY_OK: case VM_KEY_NUM5:
            if (g_phase == 2) { reset_game(); }
            else if (g_phase == 0) player_confirm();
            break;
        case VM_KEY_RIGHT_SOFTKEY: case VM_KEY_CLEAR: case VM_KEY_BACK:
            vm_exit_app(); break;
        }
        if (g_phase != 2) draw();
    }
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    (void)event; (void)x; (void)y;
}

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
