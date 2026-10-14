/* StormArena25D - 240x320 anime-style 1v1 fighter sample.
 *
 * Recreates the graphics recipe of a mobile anime fighting game:
 *   - endless perspective grid arena via vxpe25d_draw_ground
 *   - cel-outlined sprite fighters: a 96x176 canvas re-rendered per tick from
 *     8 procedural poses, drawn as 1:1 2.5D billboards with facing flips and
 *     ground shadows through the auto-sorting batch
 *   - world-space arena boundary ellipse via vxpe25d_draw_rope_world
 *   - radial hit bursts, impact rings, puffy dust clouds and full-screen super
 *     speed lines via vxpe2d_draw_burst / vxpe2d_draw_ring
 *   - fighting-game HUD: name plates, thin gold HP bars with damage flash,
 *     teal segmented super gauges, centre infinity, yellow combo counter and
 *     rising damage popups
 * Original characters REN (silver/green) and KURO (black/red): the reference
 * roster is fan art of a licensed franchise and is not reproduced.
 *
 * 4/6 move, 2 jump, 5 punch, 7 kick, 8 super (gauge full), 5 rematch after
 * KO, CLEAR backs out, right softkey exits.  Pen: thirds move, centre tap
 * punches.
 *
 * Screens: a splash card boots into a menu that reuses the fight arena as its
 * backdrop (both fighters idle behind a scrim, exactly like the reference's
 * character-select frames), a how-to-play page, and the match itself.
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpScene25D.h"
#include "graphics/VxpVfx2D.h"
#include "graphics/VxpPixelFont.h"
#include "sprites_gen.h"
#include <stdint.h>
#include <string.h>

#define SW 240
#define SH 320
#define HORIZON 132
#define CAM_Y 120
#define FIGHT_Z 170          /* both fighters march on this depth line */
#define ARENA_HALF 110
#define FW SA_FIG_W
#define FH SA_FIG_H

enum { ST_IDLE = 0, ST_WALK, ST_JUMP, ST_PUNCH, ST_KICK, ST_SUPER,
       ST_HIT, ST_KO };
enum { SLOT_IDLE0 = 0, SLOT_IDLE1, SLOT_WALK0, SLOT_WALK1, SLOT_PUNCH,
       SLOT_KICK, SLOT_HIT, SLOT_JUMP };

typedef struct Atk {
    uint8_t startup, active, recover, dmg, range;
} Atk;
/* Frame counts are simulation steps at STEP_MS, so one punch lands in ~0.4 s
 * like the reference clip. */
static const Atk ATK_PUNCH = { 3, 2, 7, 6, 100 };
static const Atk ATK_KICK  = { 4, 3, 10, 10, 116 };
static const Atk ATK_SUPER = { 6, 4, 16, 25, 150 };

typedef struct Fighter {
    int x, vx;
    int y10, vy10;           /* jump height in tenths of a world unit */
    int hp, gauge;
    int face;                /* +1 -> sprite faces right */
    int state, st_t, hit_done;
    int combo, combo_dmg, combo_t;
    int flash, ai_cool;
    const VxpeSpriteA8* spr;
} Fighter;

typedef struct Vfx {
    int live, kind, t, wx, wy, wz;
} Vfx;

typedef struct Popup {
    int live, x, y, val, t;
} Popup;

static VMINT g_layer = -1;
static VMINT g_timer = -1;
/* g_tick counts simulation steps (STEP_MS each), not timer callbacks: the
 * callback rate varies with frame cost, so it cannot drive animation or the
 * hit-flash blink. */
static uint32_t g_tick = 0, g_rng = 0xA26E5F01u;
static uint32_t g_frame_ms = 0;
static int g_left = 0, g_right = 0, g_over = 0, g_shake = 0, g_slow = 0;
static uint32_t g_last_input_ms; /* last human press; 0 = never, so the demo runs */

/* Screens. The splash is a brand card, the menu reuses the fight arena as its
 * backdrop, and HELP is the key table. SCR_FIGHT is the match itself. */
enum { SCR_SPLASH = 0, SCR_MENU, SCR_HELP, SCR_FIGHT };
enum { MI_FIGHT = 0, MI_DEMO, MI_SIDE, MI_HELP, MI_EXIT, MI_N };
#define SPLASH_STEPS 78        /* ~2.6 s of simulation steps at STEP_MS */
static int g_screen = SCR_SPLASH, g_menu_i = 0, g_splash_t = 0;
static int g_p1_side = 0;      /* 0 -> player controls REN, 1 -> KURO */
static int g_human = 1;        /* 0 -> attract mode: both sides are CPU */

/* The new screens speak the HUD's language: gold display type with a dark
 * outline over studio navy, teal for anything the player can act on. */
#define UI_NAVY  vxpe2d_rgb565(12, 14, 22)
#define UI_INK   vxpe2d_rgb565(8, 9, 14)
#define UI_GOLD  vxpe2d_rgb565(240, 205, 60)
#define UI_IVORY vxpe2d_rgb565(236, 238, 245)
#define UI_TEAL  vxpe2d_rgb565(120, 205, 190)
#define UI_DIM   vxpe2d_rgb565(150, 156, 172)
/* Row geometry is shared by the renderer and the pen hit-test. */
#define MENU_ROW_X 30
#define MENU_ROW_W 180
#define MENU_ROW_H 20
#define MENU_ROW_Y0 186
#define MENU_ROW_STEP 22

static Fighter g_f[2];
static Vfx g_vfx[6];
static Popup g_pop[4];

/* Fighter art is baked offline by tools/generate_stormarena_sprites.py into
 * 10 body parts per fighter (RGB565 + 1-bit visibility mask, 1-px outline).
 * Compositing the six slots of a pose into one 96x176 scratch sprite keeps the
 * ROM cost at ~92 KB; eight full frames per fighter would cost ~790 KB. */
#include "sprites_gen.h"

static uint16_t g_atlas_px[2][FW * FH];
static uint8_t g_atlas_a[2][FW * FH];
static VxpeSpriteA8 g_ninja[2];
static uint16_t g_grid_px[16 * 16];
static VxpeSpriteA8 g_grid;
/* The same 16x16 tile, re-declared as an RGB565 sprite so the splash can run
 * it through vxpe2d_perspective_floor, which takes a 565 texture. */
static VxpeSprite565 g_grid565;
static VxpeCamera25D g_cam;
static VxpeBillboardBatch25D g_batch;

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
static void rect(uint16_t* fb, int x, int y, int w, int h, uint16_t c) {
    int i, j;
    for (j = 0; j < h; ++j)
        for (i = 0; i < w; ++i)
            px(fb, x + i, y + j, c);
}
/* Bresenham. The splash paints an out-of-focus arena grid and the menu runs a
 * leader line from each name plate to its fighter; VxpVfx2D has no plain line
 * primitive, and a beam style would cost more than the 13 lines need. */
static void line(uint16_t* fb, int x0, int y0, int x1, int y1, uint16_t c) {
    int dx = x1 - x0, dy = y1 - y0;
    int sx = dx < 0 ? -1 : 1, sy = dy < 0 ? -1 : 1;
    int adx = dx < 0 ? -dx : dx, ady = dy < 0 ? -dy : dy;
    int err = adx - ady, i, n = adx > ady ? adx : ady, e2;
    for (i = 0; i <= n; ++i) {
        px(fb, x0, y0, c);
        e2 = err << 1;
        if (e2 > -ady) { err -= ady; x0 += sx; }
        if (e2 < adx) { err += adx; y0 += sy; }
    }
}

/* ---- fighter atlas generation (frames face right; flip_x mirrors) ---- */
static void blit_part(uint16_t* p, uint8_t* a, const SaPart* sp, int dx,
                      int dy) {
    int x, y, w = sp->w, h = sp->h;
    for (y = 0; y < h; ++y) {
        int gy = sp->oy + y + dy;
        if (gy < 0 || gy >= FH) continue;
        for (x = 0; x < w; ++x) {
            int k = y * w + x, gx = sp->ox + x + dx;
            if (!(sp->mask[k >> 3] & (0x80 >> (k & 7)))) continue;
            if (gx < 0 || gx >= FW) continue;
            p[gy * FW + gx] = sp->px[k];
            a[gy * FW + gx] = 255;
        }
    }
}
static void build_assets(void) {
    int i, x, y;
    for (y = 0; y < 16; ++y)
        for (x = 0; x < 16; ++x) {
            int line = (x == 0 || y == 0);
            int sub = (!line && (x == 8 || y == 8));
            uint16_t c;
            if (line) c = vxpe2d_rgb565(90, 95, 109);
            else if (sub) c = vxpe2d_rgb565(78, 83, 96);
            else c = vxpe2d_rgb565(70, 75, 88);
            if (!line && !sub && ((x * 31 + y * 17) & 63) == 0)
                c = vxpe2d_rgb565(74, 79, 92);
            g_grid_px[y * 16 + x] = c;
        }
    memset(&g_grid, 0, sizeof(g_grid));
    g_grid.pixels = g_grid_px;
    g_grid.width = g_grid.height = g_grid.stride = 16;
    g_grid.opaque = 1;
    for (i = 0; i < 2; ++i) {
        g_ninja[i].pixels = g_atlas_px[i];
        g_ninja[i].alpha = g_atlas_a[i];
        g_ninja[i].width = FW;
        g_ninja[i].height = FH;
        g_ninja[i].stride = FW;
        g_ninja[i].alpha_stride = FW;
        g_ninja[i].opaque = 0;
    }
}

/* ---- combat ---- */
static int slot_of(const Fighter* f) {
    switch (f->state) {
    case ST_PUNCH:
    case ST_SUPER: return SLOT_PUNCH;
    case ST_KICK:  return SLOT_KICK;
    case ST_HIT:
    case ST_KO:    return SLOT_HIT;
    case ST_JUMP:  return SLOT_JUMP;
    case ST_WALK:  return (g_tick >> 3) & 1 ? SLOT_WALK0 : SLOT_WALK1;
    default:       return (g_tick >> 4) & 1 ? SLOT_IDLE0 : SLOT_IDLE1;
    }
}
/* Composite the current pose of each fighter out of its baked parts. Each part
 * already carries its own material-tinted 1-px outline, so no dilation pass is
 * needed and overlapping parts never stack into a dark seam. */
static void refresh_sprites(void) {
    const SaPart* tabs[2];
    int i, s;
    /* The menu can hand the player either fighter, so the palette tables are
     * bound per slot rather than hard-wired to P1 = REN. */
    tabs[g_p1_side] = SA_PARTS_REN;
    tabs[1 - g_p1_side] = SA_PARTS_KURO;
    for (i = 0; i < 2; ++i) {
        uint16_t* p = g_atlas_px[i];
        uint8_t* a = g_atlas_a[i];
        const SaPoseSlot* slots = SA_POSES[slot_of(&g_f[i])];
        memset(p, 0, sizeof(g_atlas_px[i]));
        memset(a, 0, sizeof(g_atlas_a[i]));
        for (s = 0; s < SA_POSE_LEN; ++s)
            if (slots[s].part >= 0)
                blit_part(p, a, &tabs[i][slots[s].part], slots[s].dx,
                          slots[s].dy);
    }
}
/* Which character occupies fighter slot i, given the menu's P1 choice. */
static const char* side_name(int i) {
    return g_p1_side == i ? "REN" : "KURO";
}
static void start_attack(Fighter* f, int state) {
    if (f->state == ST_PUNCH || f->state == ST_KICK || f->state == ST_SUPER ||
        f->state == ST_HIT || f->state == ST_KO) return;
    if (state == ST_SUPER) {
        if (f->gauge < 100) return;
        f->gauge = 0;
        g_slow = 10;
        g_shake = 10;
    }
    f->state = state;
    f->st_t = 0;
    f->hit_done = 0;
}
static void spawn_vfx(int kind, int wx, int wz) {
    int i;
    for (i = 0; i < 6; ++i)
        if (!g_vfx[i].live) {
            g_vfx[i].live = 1; g_vfx[i].kind = kind;
            g_vfx[i].t = 0; g_vfx[i].wx = wx; g_vfx[i].wz = wz;
            return;
        }
}
static void spawn_popup(int x, int y, int val) {
    int i;
    for (i = 0; i < 4; ++i)
        if (!g_pop[i].live) {
            g_pop[i].live = 1; g_pop[i].x = x; g_pop[i].y = y;
            g_pop[i].val = val; g_pop[i].t = 0;
            return;
        }
}
static void land_hit(Fighter* atk, Fighter* def, const Atk* a) {
    VxpeProjected25D pp;
    int mid_x = (atk->x + def->x) / 2;
    atk->hit_done = 1;
    def->hp -= a->dmg;
    def->gauge += a->dmg / 3;
    atk->gauge += a->dmg / 2 + 4;
    if (atk->gauge > 100) atk->gauge = 100;
    if (def->gauge > 100) def->gauge = 100;
    def->state = ST_HIT; def->st_t = 0;
    def->vx = atk->face * (a->dmg >= 20 ? 14 : (a->dmg >= 10 ? 9 : 6));
    def->flash = 12;
    atk->combo += 1;
    atk->combo_dmg += a->dmg;
    atk->combo_t = 60;
    if (vxpe25d_project(&g_cam, mid_x, 100 + (def->y10 / 10), FIGHT_Z, &pp))
        spawn_popup(pp.x, pp.y - 30, a->dmg);
    spawn_vfx(a->dmg >= 20 ? 2 : 1, mid_x, FIGHT_Z);
    if (a->dmg >= 20) {
        spawn_vfx(3, def->x, FIGHT_Z);   /* white dust cloud like the video */
        g_shake = 12;
    }
    if (def->hp <= 0) {
        def->hp = 0;
        def->state = ST_KO;
        def->vy10 = 180;                 /* dramatic launch-back */
        g_over = 1;
    }
}
static void step_attack(Fighter* f, Fighter* o, int state, const Atk* a) {
    if (f->state != state) return;
    ++f->st_t;
    if (f->st_t == 1 && state == ST_SUPER) o->vy10 = 200;
    if (f->st_t > a->startup && f->st_t <= a->startup + a->active &&
        !f->hit_done && o->state != ST_KO) {
        int dx = o->x - f->x;
        if (dx * f->face >= 0 && dx * dx <= a->range * a->range &&
            (o->y10 / 10) < (state == ST_SUPER ? 90 : 50))
            land_hit(f, o, a);
    }
    if (f->st_t >= a->startup + a->active + a->recover)
        f->state = f->y10 > 0 ? ST_JUMP : ST_IDLE;
}
static void physics(Fighter* f, int l, int r) {
    int actionable = (f->state != ST_PUNCH && f->state != ST_KICK &&
                      f->state != ST_SUPER && f->state != ST_HIT &&
                      f->state != ST_KO);
    if (f->state == ST_HIT) {
        ++f->st_t;
        if (f->st_t > 12 && f->y10 <= 0) f->state = ST_IDLE;
    }
    if (actionable) {
        int mv = (r ? 1 : 0) - (l ? 1 : 0);
        if (mv) {
            f->vx = mv * 4;
            if (f->y10 <= 0) f->state = ST_WALK;
        } else if (f->state == ST_WALK) f->state = ST_IDLE;
    }
    f->x += f->vx;
    f->vx = (f->vx * 2) / 3;
    if (f->x < -ARENA_HALF) f->x = -ARENA_HALF;
    if (f->x > ARENA_HALF) f->x = ARENA_HALF;
    if (f->y10 > 0 || f->vy10 > 0) {
        f->y10 += f->vy10;
        f->vy10 -= 20;
        if (f->y10 <= 0) {
            f->y10 = 0; f->vy10 = 0;
            if (f->state == ST_JUMP) f->state = ST_IDLE;
        }
    }
    if (f->flash) --f->flash;
    if (f->combo_t) {
        --f->combo_t;
        if (!f->combo_t) { f->combo = 0; f->combo_dmg = 0; }
    }
}
static void reset_match(void) {
    memset(g_f, 0, sizeof(g_f));
    g_f[0].hp = 100; g_f[0].x = -110; g_f[0].face = 1; g_f[0].spr = &g_ninja[0];
    g_f[1].hp = 100; g_f[1].x = 110;  g_f[1].face = -1; g_f[1].spr = &g_ninja[1];
    memset(g_vfx, 0, sizeof(g_vfx));
    memset(g_pop, 0, sizeof(g_pop));
    g_over = 0; g_slow = 0; g_shake = 0;
    g_last_input_ms = vm_get_tick_count();
}
/* The menu shows the two fighters as a VS line-up rather than at fighting
 * range: 58 world units each side of the camera centre projects to screen
 * x 62 and 178 at the fight depth, which leaves the logo band clear. */
static void menu_stance(void) {
    reset_match();
    g_f[0].x = -58;
    g_f[1].x = 58;
}
/* Start a match. human=0 runs both sides on the AI: g_last_input_ms==0 is what
 * update() reads as "never pressed", which is how the attract demo works. */
static void begin_match(int human) {
    g_human = human;
    reset_match();
    g_last_input_ms = human ? vm_get_tick_count() : 0;
    g_screen = SCR_FIGHT;
}
static void ai_control(Fighter* me, Fighter* op) {
    int dx = op->x - me->x;
    int adx = dx < 0 ? -dx : dx;
    if (me->state == ST_HIT || me->state == ST_KO || g_over) return;
    me->face = dx >= 0 ? 1 : -1;
    if (me->ai_cool > 0) --me->ai_cool;
    if (adx > 92) {
        me->vx = (dx > 0 ? 1 : -1) * 4;
    } else if (!me->ai_cool) {
        /* one committed exchange every ~0.5 s; rolling per tick turns the
         * sample into a 1-second knock-out instead of a fight */
        int roll = (int)(rnd32() % 100);
        if (me->gauge >= 100 && roll < 26) start_attack(me, ST_SUPER);
        else if (roll < 52) start_attack(me, ST_PUNCH);
        else if (roll < 78) start_attack(me, ST_KICK);
        else me->vx = (dx > 0 ? -1 : 1) * 6;
        me->ai_cool = 10 + (int)(rnd32() % 16);
    }
}
static void update(void) {
    Fighter* p1 = &g_f[0];
    Fighter* p2 = &g_f[1];
    int i;
    ++g_tick;
    if (g_screen == SCR_SPLASH) {
        if (g_splash_t < SPLASH_STEPS) ++g_splash_t;
        else g_screen = SCR_MENU;
        return;
    }
    if (g_screen != SCR_FIGHT) {
        /* The menu and help page keep the arena live behind their scrim, so the
         * pair still cycles the two idle frames, but nothing may walk, attack,
         * flash or accumulate damage on these screens. */
        for (i = 0; i < 2; ++i) {
            g_f[i].state = ST_IDLE;
            g_f[i].vx = 0;
            g_f[i].flash = 0;
            g_f[i].y10 = 0;
            g_f[i].vy10 = 0;
            g_f[i].combo = 0;
            g_f[i].combo_t = 0;
            g_f[i].combo_dmg = 0;
        }
        for (i = 0; i < 6; ++i) g_vfx[i].live = 0;
        for (i = 0; i < 4; ++i) g_pop[i].live = 0;
        if (g_shake) --g_shake;
        return;
    }
    if (g_slow) --g_slow;
    else if (!g_over) {
        /* attract mode: the clip this sample copies is a fight between two
         * animated fighters, so P1 boxes on its own until a key is pressed.
         * The gate is wall-clock because the app timer's callback rate is not
         * fixed (measured 11.5-76 Hz on VXPEmu depending on frame cost). */
        uint32_t now_ms = vm_get_tick_count();
        int attract = !g_last_input_ms || now_ms - g_last_input_ms > 3000u;
        if (!attract) p1->face = p2->x >= p1->x ? 1 : -1;
        if (attract) ai_control(p1, p2);
        physics(p1, g_left, g_right);
        ai_control(p2, p1);
        physics(p2, 0, 0);
        step_attack(p1, p2, ST_PUNCH, &ATK_PUNCH);
        step_attack(p1, p2, ST_KICK, &ATK_KICK);
        step_attack(p1, p2, ST_SUPER, &ATK_SUPER);
        step_attack(p2, p1, ST_PUNCH, &ATK_PUNCH);
        step_attack(p2, p1, ST_KICK, &ATK_KICK);
        step_attack(p2, p1, ST_SUPER, &ATK_SUPER);
    } else {
        physics(p1, 0, 0);
        physics(p2, 0, 0);
    }
    for (i = 0; i < 6; ++i)
        if (g_vfx[i].live && g_vfx[i].t++ >
            (g_vfx[i].kind == 2 ? 14 : g_vfx[i].kind == 3 ? 9 : 7))
            g_vfx[i].live = 0;
    for (i = 0; i < 4; ++i)
        if (g_pop[i].live) {
            g_pop[i].t += 1; g_pop[i].y -= 1;
            if (g_pop[i].t > 26) g_pop[i].live = 0;
        }
    if (g_shake) --g_shake;
}

/* ---- rendering ---- */
static void draw_text(uint16_t* fb, int x, int y, const char* t, int font,
                      int scale, uint16_t color) {
    VxpeFontStyle st;
    vxpe_font_style_default(&st);
    st.font_id = (uint8_t)font;
    st.scale = (uint8_t)scale;
    st.color565 = color;
    st.shadow565 = vxpe2d_rgb565(10, 10, 16);
    {
        VxpeRectI clip;
        clip.x = 0; clip.y = 0; clip.w = (uint16_t)SW; clip.h = (uint16_t)SH;
        vxpe_font_draw(fb, SW, SH, x, y, t, &st, clip);
    }
}
/* Text with the full effect stack. The splash and menu titles use
 * VXPE_FONT_DISPLAY with OUTLINE|BEVEL: the HUD's plain shadowed string is
 * written for a dark plate, and these titles sit over a lit grid arena. */
static void draw_text_fx(uint16_t* fb, int x, int y, const char* t, int font,
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
    st.highlight565 = vxpe2d_rgb565(255, 248, 214);
    clip.x = 0; clip.y = 0; clip.w = (uint16_t)SW; clip.h = (uint16_t)SH;
    vxpe_font_draw(fb, SW, SH, x, y, t, &st, clip);
}
/* Logical width, outline and shadow excluded. */
static int text_w(const char* t, int font, int scale) {
    VxpeFontStyle st;
    vxpe_font_style_default(&st);
    st.font_id = (uint8_t)font;
    st.scale = (uint8_t)scale;
    return vxpe_font_measure(t, &st);
}
static void draw_text_c(uint16_t* fb, int cx, int y, const char* t, int font,
                        int scale, uint16_t color, uint8_t effects) {
    draw_text_fx(fb, cx - text_w(t, font, scale) / 2, y, t, font, scale, color,
                 effects);
}
static void ui_frame(uint16_t* fb, int x, int y, int w, int h, uint16_t c) {
    rect(fb, x, y, w, 1, c);
    rect(fb, x, y + h - 1, w, 1, c);
    rect(fb, x, y, 1, h, c);
    rect(fb, x + w - 1, y, 1, h, c);
}
static void int_to_str(char* out, int v) {
    char tmp[8];
    int n = 0, i;
    if (v < 0) v = 0;
    do { tmp[n++] = (char)('0' + v % 10); v /= 10; } while (v);
    for (i = 0; i < n; ++i) out[i] = tmp[n - 1 - i];
    out[i] = 0;
}
static void draw_hud(uint16_t* fb) {
    int i, gw;
    Fighter* p1 = &g_f[0];
    Fighter* p2 = &g_f[1];
    const char* names[2];
    Fighter* fs[2] = { p1, p2 };
    names[0] = side_name(0);
    names[1] = side_name(1);
    for (i = 0; i < 2; ++i) {
        int bx = i == 0 ? 6 : 130;
        int w = fs[i]->hp * 104 / 100;
        int p;
        draw_text(fb, i == 0 ? 6 : SW - 30, 1, names[i], 0, 1,
                  vxpe2d_rgb565(226, 228, 236));
        /* thin gold HP bar stacked over a wider teal gauge, like the video */
        rect(fb, bx - 1, 7, 106, 6, vxpe2d_rgb565(12, 14, 20));
        rect(fb, bx, 8, 104, 4, vxpe2d_rgb565(96, 34, 38));
        if (i == 0) rect(fb, bx, 8, w, 4, vxpe2d_rgb565(240, 215, 94));
        else rect(fb, bx + 104 - w, 8, w, 4, vxpe2d_rgb565(240, 215, 94));
        if (fs[i]->flash)
            rect(fb, bx, 8, 104, 4, vxpe2d_rgb565(255, 244, 236));
        gw = fs[i]->gauge * 104 / 100;
        rect(fb, bx - 1, 14, 106, 7, vxpe2d_rgb565(12, 14, 20));
        rect(fb, bx, 15, 104, 5, vxpe2d_rgb565(28, 42, 46));
        if (i == 0) rect(fb, bx, 15, gw, 5, vxpe2d_rgb565(77, 147, 139));
        else rect(fb, bx + 104 - gw, 15, gw, 5, vxpe2d_rgb565(77, 147, 139));
        for (p = 1; p < 4; ++p)
            rect(fb, bx + p * 26, 15, 1, 5, vxpe2d_rgb565(12, 14, 20));
    }
    /* centre infinity */
    for (i = 0; i < 2; ++i) {
        int cx = 114 + i * 8;
        rect(fb, cx, 8, 6, 8, vxpe2d_rgb565(232, 234, 242));
        rect(fb, cx + 1, 10, 4, 2, vxpe2d_rgb565(18, 20, 28));
        rect(fb, cx + 2, 12, 2, 2, vxpe2d_rgb565(232, 234, 242));
    }
    /* numbered skill-icon column on the left edge, like the reference */
    {
        uint16_t ic[8];
        ic[0] = vxpe2d_rgb565(220, 70, 80);
        ic[1] = vxpe2d_rgb565(90, 170, 240);
        ic[2] = vxpe2d_rgb565(110, 220, 130);
        ic[3] = vxpe2d_rgb565(240, 205, 60);
        ic[4] = vxpe2d_rgb565(190, 120, 230);
        ic[5] = vxpe2d_rgb565(70, 74, 90);
        ic[6] = vxpe2d_rgb565(70, 74, 90);
        ic[7] = vxpe2d_rgb565(70, 74, 90);
        for (i = 0; i < 8; ++i) {
            char d[2];
            d[0] = (char)('1' + i); d[1] = 0;
            rect(fb, 2, 28 + i * 9, 7, 7, vxpe2d_rgb565(14, 16, 22));
            rect(fb, 3, 29 + i * 9, 5, 5, ic[i]);
            draw_text(fb, 11, 28 + i * 9, d, 0, 1,
                      vxpe2d_rgb565(140, 146, 160));
        }
    }
    /* combo counter */
    {
        Fighter* atk = p1->combo_t >= 2 ? p1 : (p2->combo_t >= 2 ? p2 : 0);
        if (atk && atk->combo >= 2) {
            char buf[24];
            int n;
            int_to_str(buf, atk->combo);
            n = (int)strlen(buf);
            buf[n++] = ' '; buf[n++] = 'H'; buf[n++] = 'I'; buf[n++] = 'T';
            buf[n++] = 'S'; buf[n] = 0;
            draw_text(fb, 12, 46, buf, 1, 2, vxpe2d_rgb565(240, 205, 60));
            int_to_str(buf, atk->combo_dmg);
            n = (int)strlen(buf);
            buf[n++] = ' '; buf[n++] = 'D'; buf[n++] = 'M'; buf[n++] = 'G';
            buf[n] = 0;
            draw_text(fb, 12, 66, buf, 0, 1, vxpe2d_rgb565(240, 205, 60));
        }
    }
    /* damage popups */
    for (i = 0; i < 4; ++i)
        if (g_pop[i].live) {
            char buf[12];
            buf[0] = '+';
            int_to_str(buf + 1, g_pop[i].val);
            draw_text(fb, g_pop[i].x - 4, g_pop[i].y, buf, 0, 1,
                      vxpe2d_rgb565(255, 255, 255));
        }
    /* frame-time probe (same convention as MeadowRush25D) */
    rect(fb, 4, SH - 12, 64, 8, vxpe2d_rgb565(16, 18, 24));
    rect(fb, 4, SH - 12, 2, 8, vxpe2d_rgb565(255, 255, 255));
    {
        int ms = (int)(g_frame_ms > 999 ? 999 : g_frame_ms);
        int w = ms > 63 ? 63 : ms;
        uint16_t c = ms <= 20 ? vxpe2d_rgb565(80, 220, 110)
                   : ms <= 40 ? vxpe2d_rgb565(240, 200, 70)
                              : vxpe2d_rgb565(240, 80, 80);
        rect(fb, 6, SH - 10, w, 4, c);
    }
    if (g_over) {
        char buf[24];
        const char* w = p1->hp ? side_name(0) : side_name(1);
        int n = 0;
        draw_text_fx(fb, SW / 2 - text_w("K.O.", 1, 3) / 2, 138, "K.O.", 1, 3,
                     vxpe2d_rgb565(255, 220, 60),
                     VXPE_FONT_SHADOW | VXPE_FONT_OUTLINE);
        while (*w) buf[n++] = *w++;
        buf[n++] = ' '; buf[n++] = 'W'; buf[n++] = 'I'; buf[n++] = 'N';
        buf[n++] = 'S'; buf[n] = 0;
        draw_text_fx(fb, SW / 2 - text_w(buf, 0, 1) / 2, 168, buf, 0, 1,
                     vxpe2d_rgb565(240, 240, 245), VXPE_FONT_SHADOW);
        if ((g_tick & 16) == 0)
            draw_text_fx(fb, SW / 2 - text_w("5: REMATCH", 0, 1) / 2, 184,
                         "5: REMATCH", 0, 1, vxpe2d_rgb565(150, 210, 255),
                         VXPE_FONT_SHADOW);
    }
}
/* The arena is both the fight stage and the menu backdrop: one function paints
 * the whole scene, each screen composites its own UI layer on top of it. */
static void draw_scene(VMUINT16* fb) {
    VxpeGround25D ground;
    VxpeProjected25D pp;
    int i, shake_x;
    shake_x = g_shake ? ((g_tick & 1) ? 2 : -2) : 0;
    /* flat studio backdrop down to the horizon */
    vxpe2d_gradient_vertical(fb, SW, SH, 0, 0, SW, HORIZON,
        vxpe2d_rgb565(48, 52, 64), vxpe2d_rgb565(56, 61, 74));
    rect(fb, 0, HORIZON, SW, SH - HORIZON, vxpe2d_rgb565(70, 75, 88));
    /* camera follows the midpoint of the fight */
    g_cam.world_x = (g_f[0].x + g_f[1].x) / 2 + shake_x;
    /* endless grid floor */
    memset(&ground, 0, sizeof(ground));
    ground.src.w = 16; ground.src.h = 16;
    ground.tile_w = 56; ground.tile_h = 56;
    ground.blend = VXPE_BLEND_COPY; ground.use_fog = 1;
    vxpe25d_draw_ground(fb, SW, SH, &g_cam, &g_grid, &ground);
    /* arena boundary ring + radial ticks, like the reference stage */
    {
        static const int16_t COSQ[16] = {
            16384, 15164, 11863, 7903, 0, -7903, -11863, -15164,
            -16384, -15164, -11863, -7903, 0, 7903, 11863, 15164
        };
        VxpeRopeStyle25D ring;
        int k;
        memset(&ring, 0, sizeof(ring));
        /* the reference stage paints its boundary in a warm tan line */
        ring.outer_color565 = vxpe2d_rgb565(140, 122, 86);
        ring.core_color565 = 0;
        ring.outer_width = 1; ring.core_width = 0;
        ring.alpha = 235; ring.blend = VXPE_BLEND_ALPHA;
        /* Ring centre sits deeper than the fight line so the near arc lands
         * on-screen at the bottom edge - a full ellipse like the video. */
        for (k = 0; k < 16; ++k) {
            int k2 = (k + 1) & 15;
            vxpe25d_draw_rope_world(fb, SW, SH, &g_cam,
                (150 * COSQ[(4 - k) & 15]) >> 14, 0,
                FIGHT_Z + 90 + ((150 * COSQ[k]) >> 14),
                (150 * COSQ[(4 - k2) & 15]) >> 14, 0,
                FIGHT_Z + 90 + ((150 * COSQ[k2]) >> 14), &ring);
            if (!(k & 1))   /* 8 ticks */
                vxpe25d_draw_rope_world(fb, SW, SH, &g_cam,
                    (138 * COSQ[(4 - k) & 15]) >> 14, 0,
                    FIGHT_Z + 90 + ((138 * COSQ[k]) >> 14),
                    (156 * COSQ[(4 - k) & 15]) >> 14, 0,
                    FIGHT_Z + 90 + ((156 * COSQ[k]) >> 14), &ring);
        }
    }
    /* fighters: the batch keeps shadow-then-body order and depth sorting */
    refresh_sprites();
    vxpe25d_batch_init(&g_batch);
    for (i = 0; i < 2; ++i) {
        Fighter* f = &g_f[i];
        VxpeBatchEntry25D e;
        memset(&e, 0, sizeof(e));
        e.sprite = f->spr;
        e.billboard.src.x = 0;
        e.billboard.src.y = 0;
        e.billboard.src.w = FW;
        e.billboard.src.h = FH;
        e.billboard.world_x = f->x;
        e.billboard.world_y = f->y10 / 10;
        e.billboard.world_z = FIGHT_Z;
        e.billboard.world_w = FW;
        e.billboard.world_h = FH;
        /* anchor at the sandal line (figure canvas y=166), not the empty rows */
        e.billboard.pivot_y_q8 = 243;
        e.billboard.flip_x = (uint8_t)(f->face < 0);
        /* the body sits at canvas x=40 of FW, not the centre; flip_x mirrors
         * inside the destination rect, so the pivot has to mirror too */
        e.billboard.pivot_x_q8 = e.billboard.flip_x ? 150 : 106;
        e.billboard.alpha = 255;
        e.billboard.blend = VXPE_BLEND_ALPHA;
        e.billboard.tint565 = f->flash && (g_tick & 1)
            ? vxpe2d_rgb565(255, 200, 200) : 0xFFFF;
        e.shadow_radius_x = 20; e.shadow_radius_y = 6;
        e.shadow_color565 = vxpe2d_rgb565(24, 26, 36);
        e.shadow_alpha = 90; e.shadow_blend = VXPE_BLEND_ALPHA;
        vxpe25d_batch_push(&g_batch, &e);
    }
    vxpe25d_batch_flush(&g_batch, fb, SW, SH, &g_cam);
    /* impact VFX in screen space over the fighters */
    for (i = 0; i < 6; ++i) {
        Vfx* v = &g_vfx[i];
        int t;
        if (!v->live) continue;
        t = v->t;
        if (!vxpe25d_project(&g_cam, v->wx, v->kind == 3 ? 40 : 100, v->wz,
                             &pp)) continue;
        if (v->kind == 2) {
            /* super: full-screen radial speed lines */
            vxpe2d_draw_burst(fb, SW, SH, pp.x, pp.y, 34 + t * 6,
                120 + t * 16, 16, (uint8_t)((t * 2) & 15),
                vxpe2d_rgb565(235, 238, 248),
                (uint8_t)(150 - t * 6), VXPE_BLEND_ADD);
        } else if (v->kind == 3) {
            /* puffy white dust cloud with a grey rim, like the video */
            static const int8_t off[12] = {
                0, 0, -18, -2, 18, -2, -10, -14, 10, -14, 0, -22
            };
            int j, r = 12 + t * 2;
            uint8_t al = (uint8_t)(t < 4 ? 255 : 255 - (t - 4) * 45);
            for (j = 0; j < 6; ++j)
                vxpe2d_draw_ring(fb, SW, SH,
                    pp.x + (off[j * 2] * r) / 10,
                    pp.y + (off[j * 2 + 1] * r) / 10,
                    r + 2, 2, vxpe2d_rgb565(150, 155, 170), al,
                    VXPE_BLEND_ALPHA);
            for (j = 0; j < 6; ++j)
                vxpe2d_draw_ring(fb, SW, SH,
                    pp.x + (off[j * 2] * r) / 10,
                    pp.y + (off[j * 2 + 1] * r) / 10,
                    r, r, vxpe2d_rgb565(248, 250, 253), al, VXPE_BLEND_ALPHA);
        } else {
            /* compact white starburst + flash core, like the video's hits */
            int cr = 7 - t;
            vxpe2d_draw_burst(fb, SW, SH, pp.x, pp.y, 6 + t * 2, 22 + t * 5,
                16, (uint8_t)((t * 3) & 15),
                vxpe2d_rgb565(250, 252, 255),
                (uint8_t)(240 - t * 28), VXPE_BLEND_ADD);
            if (cr > 0)
                vxpe2d_draw_ring(fb, SW, SH, pp.x, pp.y, cr, cr,
                    vxpe2d_rgb565(255, 255, 255),
                    (uint8_t)(250 - t * 30), VXPE_BLEND_ADD);
            vxpe2d_draw_ring(fb, SW, SH, pp.x, pp.y, 8 + t * 5, 1,
                vxpe2d_rgb565(255, 255, 255),
                (uint8_t)(180 - t * 24), VXPE_BLEND_ADD);
        }
    }
}
static void draw_fight(VMUINT16* fb) {
    draw_scene(fb);
    draw_hud(fb);
}
/* ---- splash card ---- */
/* A brand card, not a placeholder: the arena grid, out of focus, under the logo
 * lockup. The bar is real progress through SPLASH_STEPS simulation steps, so it
 * fills at the same wall-clock rate on a handset as on the emulator. */
static void draw_splash(VMUINT16* fb) {
    static const int16_t ROWS[5] = { 240, 248, 260, 278, 302 };
    int i, w, pct;
    vxpe2d_gradient_vertical_dithered(fb, SW, SH, 0, 0, SW, SH, UI_NAVY,
        vxpe2d_rgb565(40, 44, 58));
    /* vanishing-point grid: 13 verticals to (120, 236) + 5 horizontals */
    {
        uint16_t gc = vxpe2d_rgb565(34, 56, 62);
        for (i = -6; i <= 6; ++i)
            line(fb, 120 + i * 46, SH, 120 + i * 7, 237, gc);
        for (i = 0; i < 5; ++i)
            rect(fb, 0, ROWS[i], SW, 1, gc);
        rect(fb, 0, 236, SW, 2, vxpe2d_rgb565(66, 120, 118));
    }
    /* Inset frame with corner ticks: without an edge the card reads as an
     * unfinished black rectangle on a 240x320 panel. */
    ui_frame(fb, 3, 3, 234, 314, vxpe2d_rgb565(84, 74, 40));
    for (i = 0; i < 4; ++i) {
        int right = i & 1, bottom = (i >> 1) & 1;
        rect(fb, right ? SW - 16 : 3, bottom ? SH - 4 : 3, 13, 1, UI_GOLD);
        rect(fb, right ? SW - 4 : 3, bottom ? SH - 16 : 3, 1, 13, UI_GOLD);
    }
    /* Dark plate under the logo so the bevel highlight reads against the glow. */
    vxpe2d_overlay_rect(fb, SW, SH, 26, 68, 188, 92, UI_INK, 130,
        VXPE_BLEND_ALPHA);
    vxpe2d_radial_light_fast(fb, SW, SH, SW / 2, 116, 96,
        vxpe2d_rgb565(120, 96, 30), 90);
    draw_text_c(fb, SW / 2, 78, "STORM\nARENA", VXPE_FONT_DISPLAY, 3, UI_GOLD,
        VXPE_FONT_OUTLINE | VXPE_FONT_BEVEL);
    rect(fb, 52, 154, 136, 1, UI_GOLD);
    rect(fb, 52, 157, 60, 1, vxpe2d_rgb565(77, 147, 139));
    rect(fb, 128, 157, 60, 1, vxpe2d_rgb565(77, 147, 139));
    draw_text_c(fb, SW / 2, 168, "1-VS-1 FIGHTING SAMPLE", VXPE_FONT_UI, 1,
        UI_DIM, VXPE_FONT_SHADOW);
    draw_text_c(fb, SW / 2, 200, "LOADING ARENA", VXPE_FONT_UI, 1, UI_TEAL,
        VXPE_FONT_SHADOW);
    rect(fb, 40, 212, 160, 9, UI_INK);
    ui_frame(fb, 39, 211, 162, 11, vxpe2d_rgb565(58, 62, 78));
    pct = g_splash_t * 100 / SPLASH_STEPS;
    w = g_splash_t * 158 / SPLASH_STEPS;
    if (w > 0) rect(fb, 41, 213, w, 7, UI_TEAL);
    if (w > 2) rect(fb, 41, 213, 2, 7, UI_GOLD);
    {
        char num[8], txt[12];
        int n;
        int_to_str(num, pct);
        n = (int)strlen(num);
        memcpy(txt, num, n);
        txt[n++] = '%';
        txt[n] = 0;
        draw_text_c(fb, SW / 2, 226, txt, VXPE_FONT_DIGITS, 1, UI_IVORY,
            VXPE_FONT_SHADOW);
    }
    if ((g_tick & 16) == 0)
        draw_text_c(fb, SW / 2, 266, "PRESS ANY KEY", VXPE_FONT_UI, 1,
            UI_IVORY, VXPE_FONT_SHADOW);
    draw_text_c(fb, SW / 2, 300, "VXPEngine coremre 2.0.0", VXPE_FONT_UI, 1,
        vxpe2d_rgb565(96, 100, 116), VXPE_FONT_SHADOW);
}
/* ---- menu ---- */
static const char* menu_label(int i, char* buf) {
    switch (i) {
    case MI_FIGHT: strcpy(buf, "FIGHT A CPU"); break;
    case MI_DEMO:  strcpy(buf, "WATCH DEMO"); break;
    case MI_SIDE:
        strcpy(buf, "P1 SIDE: ");
        strcat(buf, g_p1_side ? "KURO" : "REN");
        break;
    case MI_HELP:  strcpy(buf, "HOW TO PLAY"); break;
    default:       strcpy(buf, "EXIT"); break;
    }
    return buf;
}
/* Right-aligned on every row: the card is 180px wide, and a bare label column
 * left the whole right half dead. */
static const char* menu_hint(int i) {
    switch (i) {
    case MI_FIGHT: return "1P VS CPU";
    case MI_DEMO:  return "CPU VS CPU";
    case MI_SIDE:  return "< >";
    case MI_HELP:  return "KEYS";
    default:       return "QUIT";
    }
}
static void draw_menu(uint16_t* fb) {
    VxpeProjected25D pp;
    char buf[24];
    int i;
    draw_scene(fb);
    /* Scrim: the arena reads as a backdrop, but gold display type over a lit
     * grid is illegible without it. */
    vxpe2d_overlay_rect(fb, SW, SH, 0, 0, SW, SH, UI_INK, 118,
        VXPE_BLEND_ALPHA);
    vxpe2d_overlay_rect(fb, SW, SH, 0, 0, SW, 60, UI_INK, 190,
        VXPE_BLEND_ALPHA);
    rect(fb, 0, 60, SW, 1, vxpe2d_rgb565(96, 82, 44));
    draw_text_c(fb, SW / 2, 10, "STORM ARENA", VXPE_FONT_DISPLAY, 2, UI_GOLD,
        VXPE_FONT_OUTLINE | VXPE_FONT_BEVEL);
    draw_text_c(fb, SW / 2, 38, "MODE SELECT", VXPE_FONT_UI, 1, UI_TEAL,
        VXPE_FONT_SHADOW);
    /* name plates above each idle fighter, like the reference's select frames */
    for (i = 0; i < 2; ++i) {
        int tw;
        if (!vxpe25d_project(&g_cam, g_f[i].x, 186, FIGHT_Z, &pp)) continue;
        if (pp.x < 26) pp.x = 26;
        if (pp.x > SW - 26) pp.x = SW - 26;
        tw = text_w(side_name(i), VXPE_FONT_UI, 1);
        rect(fb, pp.x - tw / 2 - 4, 66, tw + 8, 11, UI_INK);
        ui_frame(fb, pp.x - tw / 2 - 4, 66, tw + 8, 11,
            vxpe2d_rgb565(58, 62, 78));
        draw_text_c(fb, pp.x, 68, side_name(i), VXPE_FONT_UI, 1,
            i == g_p1_side ? UI_GOLD : UI_IVORY, VXPE_FONT_SHADOW);
        line(fb, pp.x, 77, pp.x, 90, vxpe2d_rgb565(58, 62, 78));
    }
    /* VS badge between the two fighters. The ring radius has to clear the
     * scale-2 glyph half-width (15px) or the letters sit on the ring. */
    vxpe2d_draw_ring(fb, SW, SH, SW / 2, 124, 21, 2,
        vxpe2d_rgb565(120, 100, 40), 150, VXPE_BLEND_ALPHA);
    draw_text_c(fb, SW / 2, 115, "VS", VXPE_FONT_DISPLAY, 2, UI_GOLD,
        VXPE_FONT_OUTLINE);
    /* row card */
    vxpe2d_overlay_rect(fb, SW, SH, 18, 178, 204, 120, UI_INK, 200,
        VXPE_BLEND_ALPHA);
    ui_frame(fb, 18, 178, 204, 120, vxpe2d_rgb565(96, 82, 44));
    for (i = 0; i < MI_N; ++i) {
        int ry = MENU_ROW_Y0 + i * MENU_ROW_STEP;
        int sel = i == g_menu_i;
        const char* hint = menu_hint(i);
        /* No shadow pass on the row text: the plate is only 2px taller than
         * the glyphs, so the shadow would print onto the card frame. */
        if (sel) {
            vxpe2d_overlay_rect(fb, SW, SH, MENU_ROW_X - 4, ry,
                MENU_ROW_W + 8, MENU_ROW_H, vxpe2d_rgb565(38, 44, 60), 235,
                VXPE_BLEND_ALPHA);
            rect(fb, MENU_ROW_X - 4, ry, 3, MENU_ROW_H, UI_GOLD);
        }
        draw_text_fx(fb, MENU_ROW_X + 10, ry + 7, menu_label(i, buf),
            VXPE_FONT_UI, 1, sel ? UI_IVORY : UI_DIM, 0);
        draw_text_fx(fb, MENU_ROW_X + MENU_ROW_W + 6 - text_w(hint,
            VXPE_FONT_UI, 1), ry + 7, hint, VXPE_FONT_UI, 1,
            sel ? UI_TEAL : vxpe2d_rgb565(84, 88, 104), 0);
    }
    draw_text_c(fb, SW / 2, 304, "OK PICKS / CLEAR EXITS", VXPE_FONT_UI, 1,
        vxpe2d_rgb565(96, 100, 116), VXPE_FONT_SHADOW);
}
/* ---- how to play ---- */
static void draw_help(uint16_t* fb) {
    /* Two columns: the key in gold, the action in ivory. Splitting them this
     * way keeps the finger action readable without a proportional font. */
    static const char* KEYS[5] = {"4/6", "2", "5", "7", "8"};
    static const char* ACTS[5] = {"MOVE LEFT / RIGHT", "JUMP", "PUNCH", "KICK",
                                  "SUPER (FULL GAUGE)"};
    static const char* PENK[2] = {"TAP L/R", "TAP MID"};
    static const char* PENA[2] = {"MOVE", "PUNCH"};
    static const char* NOTES[4] = {
        "AFTER A K.O. PRESS 5 FOR",
        "A REMATCH. CLEAR LEAVES",
        "THE FIGHT AND RETURNS",
        "TO THE MENU.",
    };
    int i, y;
    draw_scene(fb);
    vxpe2d_overlay_rect(fb, SW, SH, 0, 0, SW, SH, UI_INK, 170,
        VXPE_BLEND_ALPHA);
    rect(fb, 0, 60, SW, 1, vxpe2d_rgb565(96, 82, 44));
    draw_text_c(fb, SW / 2, 10, "HOW TO PLAY", VXPE_FONT_DISPLAY, 2, UI_GOLD,
        VXPE_FONT_OUTLINE | VXPE_FONT_BEVEL);
    draw_text_c(fb, SW / 2, 38, "CONTROLS", VXPE_FONT_UI, 1, UI_TEAL,
        VXPE_FONT_SHADOW);
    vxpe2d_overlay_rect(fb, SW, SH, 16, 68, 208, 212, UI_INK, 210,
        VXPE_BLEND_ALPHA);
    ui_frame(fb, 16, 68, 208, 212, vxpe2d_rgb565(96, 82, 44));
    y = 80;
    for (i = 0; i < 5; ++i) {
        draw_text_fx(fb, 26, y, KEYS[i], VXPE_FONT_UI, 1, UI_GOLD, 0);
        draw_text_fx(fb, 76, y, ACTS[i], VXPE_FONT_UI, 1, UI_IVORY, 0);
        y += 15;
    }
    rect(fb, 26, 158, 188, 1, vxpe2d_rgb565(40, 44, 58));
    y = 166;
    for (i = 0; i < 2; ++i) {
        draw_text_fx(fb, 26, y, PENK[i], VXPE_FONT_UI, 1, UI_GOLD, 0);
        draw_text_fx(fb, 76, y, PENA[i], VXPE_FONT_UI, 1, UI_IVORY, 0);
        y += 15;
    }
    rect(fb, 26, 198, 188, 1, vxpe2d_rgb565(40, 44, 58));
    y = 206;
    for (i = 0; i < 4; ++i) {
        draw_text_fx(fb, 26, y, NOTES[i], VXPE_FONT_UI, 1, UI_DIM, 0);
        y += 15;
    }
    draw_text_c(fb, SW / 2, 288, "ANY KEY: BACK", VXPE_FONT_UI, 1, UI_TEAL,
        VXPE_FONT_SHADOW);
}
/* ---- screens ---- */
static void draw(void) {
    VMUINT16* fb = framebuffer();
    uint32_t t0;
    if (!fb) return;
    t0 = vm_get_tick_count();
    switch (g_screen) {
    case SCR_SPLASH: draw_splash(fb); break;
    case SCR_MENU:   draw_menu(fb); break;
    case SCR_HELP:   draw_help(fb); break;
    default:         draw_fight(fb); break;
    }
    g_frame_ms = vm_get_tick_count() - t0;
    vm_graphic_flush_layer(&g_layer, 1);
}
/* VXPEmu fires the 50 ms app timer at whatever rate it can paint - measured
 * 11.5 Hz on this scene and 76 Hz on a lighter one - so the simulation steps on
 * wall-clock time instead of on callbacks, and plays the same on a handset. */
#define STEP_MS 33
static void tick(VMINT tid) {
    static uint32_t g_last_ms;
    static int g_acc;
    uint32_t now = vm_get_tick_count();
    int32_t dt = (int32_t)(now - g_last_ms);
    if (!g_last_ms || dt > 200) dt = STEP_MS;
    g_last_ms = now;
    for (g_acc += dt; g_acc >= STEP_MS; g_acc -= STEP_MS) update();
    draw();
}
static void start(void) {
    if (g_layer < 0)
        g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    build_assets();
    vxpe25d_camera_init(&g_cam, SW, SH, HORIZON, 170);
    g_cam.world_y = CAM_Y;
    g_cam.near_z = 60; g_cam.far_z = 900;
    g_cam.fog_near_z = 420; g_cam.fog_far_z = 820;
    g_cam.fog_color565 = vxpe2d_rgb565(56, 61, 74);
    g_cam.fog_strength = 150;
    menu_stance();
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
    }
}
static void trigger_attack(int kind) {
    if (g_over) { begin_match(g_human); return; }
    if (kind == 0) start_attack(&g_f[0], ST_PUNCH);
    else if (kind == 1) start_attack(&g_f[0], ST_KICK);
    else start_attack(&g_f[0], ST_SUPER);
}
/* Which row the pen is over, or -1. Taps outside the card do nothing so a
 * stray press cannot start a match. */
static int menu_row_at(int x, int y) {
    int i;
    if (x < MENU_ROW_X - 6 || x > MENU_ROW_X + MENU_ROW_W + 8) return -1;
    for (i = 0; i < MI_N; ++i) {
        int ry = MENU_ROW_Y0 + i * MENU_ROW_STEP;
        if (y >= ry && y < ry + MENU_ROW_H) return i;
    }
    return -1;
}
static void menu_pick(int i) {
    switch (i) {
    case MI_FIGHT: begin_match(1); break;
    case MI_DEMO:  begin_match(0); break;
    case MI_SIDE:  g_p1_side = !g_p1_side; break;
    case MI_HELP:  g_screen = SCR_HELP; break;
    default:       stop(); vm_exit_app(); break;
    }
}
static void menu_move(int d) {
    g_menu_i += d;
    if (g_menu_i < 0) g_menu_i = MI_N - 1;
    if (g_menu_i >= MI_N) g_menu_i = 0;
}
void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN) {
        if (g_screen == SCR_SPLASH) { g_screen = SCR_MENU; return; }
        if (g_screen == SCR_HELP) { g_screen = SCR_MENU; return; }
        g_last_input_ms = vm_get_tick_count();
        if (g_screen == SCR_MENU) {
            switch (keycode) {
            case VM_KEY_UP: case VM_KEY_NUM2: menu_move(-1); break;
            case VM_KEY_DOWN: case VM_KEY_NUM8: menu_move(1); break;
            case VM_KEY_LEFT: case VM_KEY_NUM4:
                if (g_menu_i == MI_SIDE) g_p1_side = 0; else menu_move(-1);
                break;
            case VM_KEY_RIGHT: case VM_KEY_NUM6:
                if (g_menu_i == MI_SIDE) g_p1_side = 1; else menu_move(1);
                break;
            case VM_KEY_OK: case VM_KEY_NUM5: menu_pick(g_menu_i); break;
            case VM_KEY_RIGHT_SOFTKEY: case VM_KEY_CLEAR: case VM_KEY_BACK:
                stop(); vm_exit_app(); break;
            }
            return;
        }
        switch (keycode) {
        case VM_KEY_LEFT: case VM_KEY_NUM4: g_left = 1; break;
        case VM_KEY_RIGHT: case VM_KEY_NUM6: g_right = 1; break;
        case VM_KEY_UP: case VM_KEY_NUM2:
            if (!g_over && g_f[0].y10 <= 0 && g_f[0].state < ST_PUNCH) {
                g_f[0].y10 = 1; g_f[0].vy10 = 170;
                g_f[0].state = ST_JUMP;
            }
            break;
        case VM_KEY_OK: case VM_KEY_NUM5: trigger_attack(0); break;
        case VM_KEY_NUM7: trigger_attack(1); break;
        case VM_KEY_NUM8: trigger_attack(2); break;
        case VM_KEY_CLEAR: case VM_KEY_BACK:
            menu_stance();
            g_screen = SCR_MENU;
            break;
        case VM_KEY_RIGHT_SOFTKEY:
            vm_exit_app(); break;
        }
    } else if (event == VM_KEY_EVENT_UP) {
        switch (keycode) {
        case VM_KEY_LEFT: case VM_KEY_NUM4: g_left = 0; break;
        case VM_KEY_RIGHT: case VM_KEY_NUM6: g_right = 0; break;
        }
    }
}
void handle_penevt(VMINT event, VMINT x, VMINT y) {
    int down = (event == VM_PEN_EVENT_TAP || event == VM_PEN_EVENT_MOVE ||
                event == VM_PEN_EVENT_LONG_TAP);
    if (!down) { g_left = g_right = 0; return; }
    if (g_screen == SCR_SPLASH) { g_screen = SCR_MENU; return; }
    if (g_screen == SCR_HELP) { g_screen = SCR_MENU; return; }
    if (g_screen == SCR_MENU) {
        if (event != VM_PEN_EVENT_TAP) return;
        {
            int row = menu_row_at(x, y);
            if (row >= 0) { g_menu_i = row; menu_pick(row); }
        }
        return;
    }
    g_last_input_ms = vm_get_tick_count();
    if (y < 24) return;
    if (x < SW / 3) { g_left = 1; g_right = 0; }
    else if (x > 2 * SW / 3) { g_right = 1; g_left = 0; }
    else if (event == VM_PEN_EVENT_TAP) trigger_attack(0);
}
void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
