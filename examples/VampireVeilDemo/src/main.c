/* Vampire Veil: Night Hunt - 240x320 side-scrolling action sample for
 * VXPEngine/coremre.
 *
 * The reference is the "Vampire's Veil" trailer, a Symphony-of-the-Night stage:
 * three wrapped pine bands sliding at different rates under a moon, a 16-px
 * tilemap whose walkable lip is a continuous golden cobble seam broken by
 * magenta moss, a cloak-wearing hunter who opens a red whip crescent in front of
 * his own hitbox, bats/imps/owls that die into soul motes, a hooded villager who
 * mends and saves, and a stone Warden in the far court with a name plate of its
 * own. The HUD is the reference's layout: round portrait plate, heart row, MP
 * gauge, corner room minimap, soul counter under it.
 *
 * Everything above the framebuffer is the action2d core, nothing else:
 *   VxpTilemap2D  - the two tile layers and every collision query
 *   VxpCamera2D   - two-axis follow, lookahead bias, deterministic shake
 *   VxpBody2D     - run/jump/coyote/one-way/ladder/hazard movement
 *   VxpCombat2D   - whip swings, i-frames, hit-stop, enemy projectiles
 *   VxpHud2D      - plate, portrait, hearts, gauge, boss plate, minimap
 *   VxpInputMap2D - handset codes and pen taps become named action edges
 * There is no per-module glue: the game only owns data (level tables, entity
 * pools) and the drawing order.
 *
 * One tilemap, two atlases. VxpeBody2D collides through the flag array only, so
 * the opaque ground atlas and the masked ledge atlas are two VxpeTilemap2D views
 * that share one flags array: a ledge is solid to the mover and transparent to
 * the blitter, and the copy_tile fast path survives on the ground layer where it
 * matters (9 rows x 15 columns per frame).
 *
 * Keys: arrows or 2/4/6/8 run and climb, 5/7 or the left softkey and OK whip and
 * jump, 3 or the right softkey spends 50 MP on a soul burst, 9 pauses, 1 or
 * CLEAR backs out, the right softkey on a menu confirms. Pen, in three bands:
 * tap the sky to leap, the middle row to run left/right or whip in its centre,
 * the bottom row to climb or burst. The title screen runs the same simulation
 * with an autopilot hunter.
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpPixelFont.h"
#include "action2d/VxpTilemap2D.h"
#include "action2d/VxpCamera2D.h"
#include "action2d/VxpBody2D.h"
#include "action2d/VxpCombat2D.h"
#include "action2d/VxpHud2D.h"
#include "action2d/VxpInputMap2D.h"
#include "vxp_public_cache.h"
#include "assets_gen.h"
#include <string.h>

#define SW 240
#define SH 320
#define TS VV_TILE                 /* 16, and the atlas cell size */
#define MAP_W 128
#define MAP_H 24
#define WORLD_W (MAP_W * TS)       /* 2048 px of stage */
#define WORLD_H (MAP_H * TS)       /* 384 px, so the camera has 64 px to climb */
#define PLANE_ROW 15               /* y 240: the near band's feet line */
#define DT_MS 33                   /* 30 fps on the handset timer */
#define MAX_ACT 14                 /* slot 0 hero, 1..12 stage, 13 the Warden */
#define MAX_ITEM 20
#define MAX_FX 48
#define ROOM_CX 4                  /* tiles per minimap room */
#define ROOM_CY 4
#define ROOMS_W (MAP_W / ROOM_CX)  /* 32 rooms */
#define ROOMS_H (MAP_H / ROOM_CY)  /* 6 rooms */
#define HERO_HP 8
#define MP_MAX 100
#define MP_BURST 50
#define WARDEN_HP 40
#define WHITE565 0xFFFFu           /* vxpe2d tint identity */

enum { SCR_SPLASH, SCR_MENU, SCR_HELP, SCR_GAME, SCR_PAUSE, SCR_OVER, SCR_WIN };
enum { EN_NONE, EN_BAT, EN_IMP, EN_OWL, EN_WARDEN };
enum { IT_SOUL, IT_ORB, IT_COIN, IT_KINDS };

enum {
    ACT_LEFT, ACT_RIGHT, ACT_UP, ACT_DOWN, ACT_JUMP, ACT_ATTACK, ACT_BURST,
    ACT_OK, ACT_PAUSE, ACT_BACK, ACT_MENU, ACT_N
};

/* Synthetic codes: the pen has none, so the virtual pad feeds the map through
 * the same door as a physical key and the game never sees coordinates. */
#define PEN_LEFT  200
#define PEN_RIGHT 201
#define PEN_JUMP  202
#define PEN_ATK   203
#define PEN_UP    204
#define PEN_DOWN  205
#define PEN_BURST 206

/* --- colours the sampler measured off the reference frames ---------------- */
#define C_VOID     vxpe2d_rgb565(6, 6, 14)
#define C_PIT_LIP  vxpe2d_rgb565(30, 26, 48)
#define C_GOLD     vxpe2d_rgb565(232, 196, 92)
#define C_IVORY    vxpe2d_rgb565(232, 234, 242)
#define C_BLOOD    vxpe2d_rgb565(176, 40, 48)
#define C_DIM      vxpe2d_rgb565(148, 156, 182)
#define C_MP       vxpe2d_rgb565(96, 170, 226)

/* --- level authoring ------------------------------------------------------
 * A column is solid from its top row down to the map floor, so the walkable
 * plane is always the top tile's upper edge - the same row VxpBody2D resolves
 * against. Columns whose top sits below PLANE_ROW read as holes in the forest
 * floor and get a void rect drawn over the air above them. */
typedef struct GroundRun { uint8_t c0, c1, top; } GroundRun;
static const GroundRun GROUND_RUNS[] = {
    {   0,  25, 15 },   /* gate green: lamp, fence, the villager's bench */
    {  26,  33, 14 },
    {  34,  43, 13 },   /* terrace of gravestones, imps */
    {  44,  51, 14 },
    {  52,  55, 17 },   /* spike trench: hazard floor, ladder out on the far wall */
    {  56,  63, 14 },
    {  64,  71, 15 },   /* hollow, owls roost high */
    {  72,  79, 12 },   /* crypt wall, reached from the balcony ledges */
    {  80,  87, 15 },
    {  88,  95, 17 },   /* chasm, one slab to hop, ladder up the east wall */
    {  96, 103, 14 },
    { 104, 111, 13 },
    { 112, 119, 15 },
    { 120, 127, 15 }    /* the Warden's court */
};
#define N_GROUND_RUN ((int)(sizeof GROUND_RUNS / sizeof GROUND_RUNS[0]))

/* Spikes: a hazard word lives on the floor tile, so standing anywhere in the
 * trench bleeds. The mover never treats HAZARD as blocking - SOLID does that. */
typedef struct HazardRun { uint8_t c0, c1, row; } HazardRun;
static const HazardRun HAZARD_RUNS[] = {
    { 52, 55, 17 }, { 90, 92, 17 }
};
#define N_HAZARD_RUN ((int)(sizeof HAZARD_RUNS / sizeof HAZARD_RUNS[0]))

/* One-way slabs on the masked atlas: left cap, middle, right cap. */
typedef struct Ledge { uint8_t c0, c1, row; } Ledge;
static const Ledge LEDGES[] = {
    { 18,  20, 12 }, { 30,  33, 10 }, { 57,  59, 11 }, { 69,  71, 13 },
    { 74,  76,  9 }, { 91,  92, 15 }, { 96,  98, 10 }, { 101, 104, 9 },
    { 116, 118, 10 }
};
#define N_LEDGE ((int)(sizeof LEDGES / sizeof LEDGES[0]))

typedef struct Ladder { uint8_t col, r0, r1; } Ladder;
static const Ladder LADDERS[] = {
    { 55, 14, 16 }, { 95, 14, 16 }, { 100, 10, 13 }
};
#define N_LADDER ((int)(sizeof LADDERS / sizeof LADDERS[0]))

/* Decor sits on the plane of its own column: feet anchored, sprite centred. */
typedef struct Prop { uint8_t spr; uint8_t col; uint8_t back; } Prop;
static const Prop PROPS[] = {
    { VV_SP_LAMP,     6, 0 }, { VV_SP_FENCE,   9, 0 }, { VV_SP_FENCE,  10, 0 },
    { VV_SP_GRAVE,   13, 0 }, { VV_SP_LAMP,    24, 0 }, { VV_SP_GRAVE,  35, 0 },
    { VV_SP_GRAVE,   37, 0 }, { VV_SP_STATUE,  40, 0 }, { VV_SP_FENCE,  45, 0 },
    { VV_SP_FENCE,   46, 0 }, { VV_SP_GRAVE,   58, 0 }, { VV_SP_LAMP,   63, 0 },
    { VV_SP_GRAVE,   66, 0 }, { VV_SP_STATUE,  82, 0 }, { VV_SP_FENCE,  85, 0 },
    { VV_SP_FENCE,   86, 0 }, { VV_SP_GRAVE,   97, 0 }, { VV_SP_LAMP,  106, 0 },
    { VV_SP_GRAVE,  110, 0 }, { VV_SP_STATUE, 122, 0 }, { VV_SP_GRAVE,  126, 0 }
};
#define N_PROP ((int)(sizeof PROPS / sizeof PROPS[0]))

typedef struct Spawn { uint8_t kind, col, row; } Spawn;
static const Spawn SPAWNS[] = {
    { EN_BAT,  15,  9 }, { EN_BAT,  21,  8 }, { EN_IMP,  36, 12 },
    { EN_IMP,  42, 12 }, { EN_OWL,  60,  7 }, { EN_BAT,  66, 10 },
    { EN_OWL,  74,  6 }, { EN_BAT,  78,  8 }, { EN_IMP,  84, 14 },
    { EN_IMP, 107, 12 }, { EN_OWL, 113,  8 }, { EN_BAT, 118, 10 }
};
#define N_SPAWN ((int)(sizeof SPAWNS / sizeof SPAWNS[0]))

/* Loot: rows are plane-relative so the pile always rests on its own column. */
typedef struct Loot { uint8_t spr, col, row; } Loot;
static const Loot LOOT[] = {
    { VV_SP_COIN,  19, 11 }, { VV_SP_ORB,  31,  9 }, { VV_SP_COIN,  58, 10 },
    { VV_SP_SOUL, 102,  8 }, { VV_SP_COIN, 117,  9 }, { VV_SP_ORB,   65, 14 },
    { VV_SP_COIN,  73, 11 }, { VV_SP_SOUL,  44, 13 }
};
#define N_LOOT ((int)(sizeof LOOT / sizeof LOOT[0]))

static const int VILLAGE_COL = 11;        /* the villager who mends and saves */
static const int BOSS_GATE_COL = 112;     /* the court the Warden wakes in */

/* --- attacks -------------------------------------------------------------
 * off_x reads from the owner's box and mirrors with facing, so every swing
 * stays in front of the body it belongs to after a turn. */
static const VxpeAttack2D ATK_WHIP = {
    8, 6, 26, 14,               /* offset, hitbox size */
    70, 130, 190,               /* windup, active, recovery */
    2, 150 << 8, -(34 << 8),      /* damage, knockback (Q8 px/s) */
    640, 70, 150, 1, 0          /* victim i-frames, hit-stop, stun, pierce */
};
static const VxpeAttack2D ATK_CLUB = {
    4, 4, 16, 12, 220, 120, 320, 2, 110 << 8, -(20 << 8), 700, 50, 200, 0, 0
};
static const VxpeAttack2D ATK_TOUCH = {
    -1, -1, 16, 12, 0, 1000, 260, 1, 70 << 8, -(46 << 8), 700, 40, 90, 0, 0
};
static const VxpeAttack2D ATK_TALON = {
    0, 2, 22, 16, 90, 260, 420, 1, 90 << 8, -(30 << 8), 700, 40, 120, 1, 0
};
static const VxpeAttack2D ATK_SLAM = {
    -6, 2, 34, 36, 300, 180, 460, 2, 170 << 8, -(70 << 8), 900, 110, 260, 1, 0
};

/* --- state --------------------------------------------------------------- */
static VMINT g_layer = -1;
static VMINT g_timer = -1;
static uint16_t* FB;

static uint16_t g_cells_g[MAP_W * MAP_H];    /* opaque ground atlas */
static uint16_t g_cells_p[MAP_W * MAP_H];    /* masked ledge atlas */
static uint16_t g_flags[MAP_W * MAP_H];      /* shared by both layers */
static uint8_t g_surf[MAP_W];
static uint8_t g_rooms[ROOMS_W * ROOMS_H];
static uint8_t g_room_tags[ROOMS_W * ROOMS_H];

static VxpeTilemap2D g_map_g;   /* what the mover and the queries read */
static VxpeTilemap2D g_map_p;
static VxpeSprite565 g_spr[VV_NSPRITE];

static VxpeCamera2D g_cam;
static VxpeBodyTuning2D g_walk;   /* the hero: fast, high, responsive */
static VxpeBodyTuning2D g_imp;    /* ground enemies: half the run speed */
static VxpeBodyTuning2D g_fly;    /* zero gravity, capped hover */
static VxpeInputMap2D g_in;

static VxpeBody2D g_body[MAX_ACT];
static VxpeCombatant2D g_com[MAX_ACT];
static uint8_t g_kind[MAX_ACT], g_alive[MAX_ACT], g_state[MAX_ACT];
static uint16_t g_clock[MAX_ACT], g_anim_ms[MAX_ACT];
static uint16_t g_cast_ms[MAX_ACT], g_reinforce_ms[MAX_ACT];
static int16_t g_home_x[MAX_ACT], g_hover_y[MAX_ACT];

typedef struct Item { int16_t x, y, vx, vy; uint8_t spr, alive; uint16_t age; } Item;
typedef struct Fx { int16_t x, y, vx, vy; uint8_t spr, alive, life, scale; } Fx;
static Item g_item[MAX_ITEM];
static Fx g_fx[MAX_FX];
static uint8_t g_proj_spr[VXPE_PROJ_POOL2D_MAX];

static VxpeProjectilePool2D g_proj;
static VxpeCombatEvent2D g_events[12];

static VxpeHudPlate2D g_plate;
static VxpeHudGauge2D g_mpbar;
static VxpeHudIconRow2D g_hearts;
static VxpeHudBossPlate2D g_boss;
static VxpeHudMinimap2D g_mm;

typedef struct Save { uint32_t magic; uint16_t best, kills, clears, hunts; } Save;
static Save g_save;

static int g_scr, g_menu, g_prev_scr;
static int g_hero_slot;           /* always 0, named for readability */
static uint32_t g_rng;
static uint32_t g_run_ms;
static int g_score, g_kills;
static int g_mp, g_hit_stop_visual_ms;
static int g_win_ms, g_dead_ms, g_flash;
static uint16_t g_anim;           /* shared frame clock for loot and FX */
static char g_msg[72];
static int g_msg_ms;
/* The villager mends on contact, so the handset's tiny keyboard does not need a
 * dedicated interact key - this is the cooldown that keeps one stop from
 * refilling every time the hero brushes past. */
static int g_mend_ms;
static int g_pen_action;          /* synthetic code still held by the pen */
static int g_title_ms;            /* attract pan + splash timer */
/* Paint cost in ms, shown by the HUD. The emulator is the only handset-shaped
 * target most builds get, so the frame budget has to be readable from a
 * screenshot rather than from a log the device never produces. */
static int g_frame_ms;

/* --- small helpers -------------------------------------------------------- */
static uint32_t rnd(void) {
    g_rng ^= g_rng << 13; g_rng ^= g_rng >> 17; g_rng ^= g_rng << 5;
    return g_rng;
}
static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
static int absi(int v) { return v < 0 ? -v : v; }

static const VxpeSprite565* SP(int id) { return &g_spr[id]; }

static void blit(int sx, int sy, int id, int flip, uint16_t tint, uint8_t alpha) {
    VxpeBlit565 op;
    const VxpeSprite565* s = SP(id);
    memset(&op, 0, sizeof op);
    op.dst_x = (int16_t)sx;
    op.dst_y = (int16_t)sy;
    op.tint565 = tint ? tint : WHITE565;
    /* alpha is coverage in every blend mode, COPY included, so "no blending"
     * here has to mean fully opaque - 0 would blank the whole sprite. */
    op.alpha = (uint8_t)(alpha ? alpha : 255u);
    op.blend = (uint8_t)(alpha ? VXPE_BLEND_ALPHA : VXPE_BLEND_COPY);
    op.flip_x = (uint8_t)(flip ? 1 : 0);
    vxpe2d_blit(FB, SW, SH, s, &op);
}

/* Feet-anchored world sprite: id centred on world x, bottom edge on feet_y. */
static void blit_feet(int wx, int feet_y, int id, int flip, uint16_t tint,
                      uint8_t alpha) {
    const VxpeSprite565* s = SP(id);
    blit(vxpe_cam_to_screen_x(&g_cam, wx) - (int)s->width / 2,
         vxpe_cam_to_screen_y(&g_cam, feet_y) - s->height, id, flip, tint, alpha);
}

/* --- level build --------------------------------------------------------- */
static int surf_at(int c) {
    int i;
    c = clampi(c, 0, MAP_W - 1);
    for (i = 0; i < N_GROUND_RUN; ++i)
        if (c >= GROUND_RUNS[i].c0 && c <= GROUND_RUNS[i].c1) return GROUND_RUNS[i].top;
    return PLANE_ROW;
}

static int hazard_cell(int c, int r) {
    int i;
    for (i = 0; i < N_HAZARD_RUN; ++i)
        if (c >= HAZARD_RUNS[i].c0 && c <= HAZARD_RUNS[i].c1 && r == HAZARD_RUNS[i].row)
            return 1;
    return 0;
}

static void level_build(void) {
    int c, r, i;
    memset(g_cells_g, 0, sizeof g_cells_g);
    memset(g_cells_p, 0, sizeof g_cells_p);
    memset(g_flags, 0, sizeof g_flags);
    memset(g_surf, 0, sizeof g_surf);

    for (c = 0; c < MAP_W; ++c) {
        int top = surf_at(c);
        int left = c > 0 ? surf_at(c - 1) : PLANE_ROW;
        int right = c < MAP_W - 1 ? surf_at(c + 1) : PLANE_ROW;
        int face = left > top ? left : right;   /* exposed cliff rows share one edge */
        g_surf[c] = (uint8_t)top;
        for (r = top; r < MAP_H; ++r) {
            uint16_t cell, fl = VXPE_TF_SOLID;
            if (r == top) {
                /* The lip owns rows 0..4 of its tile: surface_below() resolves the
                 * floor to ty*tile_h, so the walkable plane is the tile's top edge. */
                int pick = (c + (top >> 1)) % 3;
                cell = pick == 0 ? VV_T_TOP_COBBLE : (pick == 1 ? VV_T_TOP_MOSS : VV_T_TOP_FLOWERS);
            } else if (r < top + 3) {
                cell = (c & 1) ? VV_T_ROCK : VV_T_ROCK_ALT;
            } else {
                cell = VV_T_ROCK_DEEP;
            }
            if (r < face) cell = VV_T_WALL_COBBLE;   /* cliff facing the lower column */
            if (hazard_cell(c, r)) fl |= VXPE_TF_HAZARD;
            g_cells_g[r * MAP_W + c] = cell;
            g_flags[r * MAP_W + c] = (uint16_t)(g_flags[r * MAP_W + c] | fl);
        }
    }

    for (i = 0; i < N_LEDGE; ++i) {
        int c0 = LEDGES[i].c0, c1 = LEDGES[i].c1, r = LEDGES[i].row, x;
        for (x = c0; x <= c1; ++x) {
            uint16_t cell = x == c0 ? VV_P_PLAT_L : (x == c1 ? VV_P_PLAT_R : VV_P_PLAT);
            g_cells_p[r * MAP_W + x] = cell;
            g_flags[r * MAP_W + x] = (uint16_t)(g_flags[r * MAP_W + x] | VXPE_TF_ONEWAY);
        }
    }

    for (i = 0; i < N_LADDER; ++i)
        for (r = LADDERS[i].r0; r <= LADDERS[i].r1; ++r)
            g_flags[r * MAP_W + LADDERS[i].col] =
                (uint16_t)(g_flags[r * MAP_W + LADDERS[i].col] | VXPE_TF_LADDER);

    /* Minimap rooms: a room is walkable when its columns reach its row band,
     * because every column is solid from its own top row down. */
    memset(g_rooms, 0, sizeof g_rooms);
    memset(g_room_tags, 0, sizeof g_room_tags);
    for (c = 0; c < MAP_W; c += ROOM_CX) {
        int rx = c / ROOM_CX;
        int low = MAP_H;                       /* shallowest top row in the band */
        for (i = 0; i < ROOM_CX; ++i) {
            int t = surf_at(c + i);
            if (t < low) low = t;
        }
        for (r = low / ROOM_CY; r < ROOMS_H; ++r) g_rooms[r * ROOMS_W + rx] = 1;
    }
    /* Boss court and the mending bench get marks so the corner map teaches the
     * route before the player has walked it. */
    {
        int rx_boss = (BOSS_GATE_COL + 4) / ROOM_CX;
        int rx_shop = VILLAGE_COL / ROOM_CX;
        int ry = surf_at(BOSS_GATE_COL + 4) / ROOM_CY;
        int ry2 = surf_at(VILLAGE_COL) / ROOM_CY;
        if (rx_boss < ROOMS_W) { g_rooms[ry * ROOMS_W + rx_boss] = 1; g_room_tags[ry * ROOMS_W + rx_boss] = VXPE_MM_BOSS; }
        if (rx_shop < ROOMS_W) { g_rooms[ry2 * ROOMS_W + rx_shop] = 1; g_room_tags[ry2 * ROOMS_W + rx_shop] = VXPE_MM_SHOP; }
    }

    memset(&g_map_g, 0, sizeof g_map_g);
    g_map_g.cells = g_cells_g;
    g_map_g.flags = g_flags;          /* one flag array serves both layers */
    g_map_g.atlas = &VV_ATLAS;
    g_map_g.width = MAP_W;
    g_map_g.height = MAP_H;
    g_map_g.tile_w = TS;
    g_map_g.tile_h = TS;
    g_map_g.atlas_cols = VV_ATLAS_COLS;
    g_map_g.oob_blocks = 1;

    g_map_p = g_map_g;
    g_map_p.cells = g_cells_p;
    g_map_p.atlas = &VV_ATLAS2;
    g_map_p.atlas_cols = VV_ATLAS2_COLS;
    g_map_p.oob_blocks = 0;
}

static void sprites_init(void) {
    int i;
    for (i = 0; i < VV_NSPRITE; ++i) {
        g_spr[i].pixels = VV_SPRITES[i].px;
        g_spr[i].mask = VV_SPRITES[i].mask;
        g_spr[i].width = VV_SPRITES[i].w;
        g_spr[i].height = VV_SPRITES[i].h;
        g_spr[i].stride = VV_SPRITES[i].w;   /* packed, no row padding */
        g_spr[i].opaque = 0;
    }
}

static void input_init(void) {
    vxpe_input_init(&g_in);
    vxpe_input_bind(&g_in, ACT_LEFT,   VM_KEY_LEFT,  VM_KEY_NUM4, PEN_LEFT);
    vxpe_input_bind(&g_in, ACT_RIGHT,  VM_KEY_RIGHT, VM_KEY_NUM6, PEN_RIGHT);
    vxpe_input_bind(&g_in, ACT_UP,     VM_KEY_UP,    VM_KEY_NUM8, PEN_UP);
    vxpe_input_bind(&g_in, ACT_DOWN,   VM_KEY_DOWN,  VM_KEY_NUM2, PEN_DOWN);
    vxpe_input_bind(&g_in, ACT_JUMP,   VM_KEY_OK,    VM_KEY_NUM7, PEN_JUMP);
    vxpe_input_bind(&g_in, ACT_ATTACK, VM_KEY_LEFT_SOFTKEY, VM_KEY_NUM5, PEN_ATK);
    vxpe_input_bind(&g_in, ACT_BURST,  VM_KEY_RIGHT_SOFTKEY, VM_KEY_NUM3, PEN_BURST);
    vxpe_input_bind(&g_in, ACT_OK,     VM_KEY_OK,    VXPE_IN_KEY_NONE, VXPE_IN_KEY_NONE);
    vxpe_input_bind(&g_in, ACT_PAUSE,  VM_KEY_NUM9,  VM_KEY_STAR, VXPE_IN_KEY_NONE);
    vxpe_input_bind(&g_in, ACT_BACK,   VM_KEY_BACK,  VM_KEY_CLEAR, VM_KEY_NUM1);
    vxpe_input_bind(&g_in, ACT_MENU,   VM_KEY_NUM0,  VM_KEY_POUND, VXPE_IN_KEY_NONE);
}

/* Three tuning tables off one preset. Every field is px/s in Q8.8, so the
 * numbers read like the design doc: the hunter crosses the 240 px screen in
 * 2.3 s, an imp in 4.6 s, and a flier has no gravity at all because its AI
 * writes vx/vy straight and only wants the step to resolve collisions. */
static void physics_init(void) {
    vxpe_body_tuning_default(&g_walk);
    g_walk.run_max_q8 = 104 * 256;
    g_walk.run_accel_q8 = 1080 * 256;
    g_walk.run_friction_q8 = 920 * 256;
    g_walk.air_accel_q8 = 640 * 256;
    g_walk.gravity_q8 = 660 * 256;
    g_walk.jump_vel_q8 = 240 * 256;
    g_walk.jump_cut_q8 = 80 * 256;
    g_walk.fall_max_q8 = 288 * 256;
    g_walk.wall_slide_q8 = 46 * 256;
    g_walk.climb_q8 = 62 * 256;
    g_walk.coyote_ms = 95;
    g_walk.jump_buffer_ms = 120;
    g_walk.step_down_px = 14;

    vxpe_body_tuning_default(&g_imp);
    g_imp.run_max_q8 = 52 * 256;
    g_imp.run_accel_q8 = 420 * 256;
    g_imp.run_friction_q8 = 520 * 256;
    g_imp.air_accel_q8 = 260 * 256;
    g_imp.jump_vel_q8 = 0;
    g_imp.jump_cut_q8 = 0;
    g_imp.climb_q8 = 0;
    g_imp.coyote_ms = 0;
    g_imp.jump_buffer_ms = 0;
    g_imp.step_up_px = 16;
    g_imp.step_down_px = 10;

    memset(&g_fly, 0, sizeof g_fly);
    g_fly.fall_max_q8 = 0;
    g_fly.step_up_px = 0;
    g_fly.step_down_px = 0;
}

/* --- entities ------------------------------------------------------------- */
static void msg(const char* text, int ms);
static void reveal_around(void);
static void save_write(void);
static void hud_update(uint16_t dt);
static void warden_gate(void);
static void draw_world(void);
static void draw_screens(void);
static void sim_update(uint16_t dt, int attract);

static int hero_x(void) { return (int)(g_body[0].x_q8 >> 8) + g_body[0].w / 2; }
static int hero_y(void) { return (int)(g_body[0].y_q8 >> 8) + g_body[0].h / 2; }

/* Attract autopilot. Instead of panning an empty stage, the title screen plays
 * itself: the hunter walks, hops and cracks the whip for real. Only a direction
 * is state, so no ping-pong maths (and no divide) is involved. The turnarounds
 * keep him on the gate green and the terrace, away from the trench at column 52. */
static int8_t g_attract_dir = 1;
static void demo_control(uint16_t dt) {
    VxpeBodyIntent2D in;
    int x = hero_x();
    if (x > 44 * TS) g_attract_dir = -1;
    else if (x < 6 * TS) g_attract_dir = 1;
    memset(&in, 0, sizeof in);
    in.x = g_attract_dir;
    /* A masked millisecond counter gives the beats: hop about every 1.1 s and
     * swing about every 2.1 s, with the hold window short enough for a low hop. */
    in.jump = (uint8_t)((g_title_ms & 1023) < dt);
    in.jump_held = (uint8_t)((g_title_ms & 1023) < 120);
    if ((g_title_ms & 2047) < dt && !vxpe_combat_frozen(&g_com[0]))
        vxpe_combat_attack(&g_com[0], &ATK_WHIP);
    vxpe_combat_body_control(&g_com[0], &g_map_g, &g_walk, &in, dt);
}

static void fx_spawn(int id, int x, int y, int vx, int vy, int life_ms, int scale) {
    int i, slot = 0;
    for (i = 0; i < MAX_FX; ++i) {
        if (!g_fx[i].alive) { slot = i; break; }
        if (g_fx[i].life < g_fx[slot].life) slot = i;
    }
    g_fx[slot].spr = (uint8_t)id;
    g_fx[slot].x = (int16_t)x;
    g_fx[slot].y = (int16_t)y;
    g_fx[slot].vx = (int16_t)vx;
    g_fx[slot].vy = (int16_t)vy;
    g_fx[slot].life = (uint8_t)life_ms;
    g_fx[slot].scale = (uint8_t)scale;
    g_fx[slot].alive = 1;
}

/* n motes thrown outward: vx is a random lateral kick, vy a fixed lift. */
static void fx_burst(int id, int x, int y, int n, int spread, int life_ms) {
    int i;
    for (i = 0; i < n; ++i) {
        int vx = (int)(rnd() % (uint32_t)(2 * spread + 1)) - spread;
        int vy = -2 - (int)(rnd() % 4);
        fx_spawn(id, x + (int)(rnd() % 7u) - 3, y + (int)(rnd() % 5u) - 2, vx, vy,
                 life_ms, 1);
    }
}

static void item_spawn(int id, int x, int y) {
    int i, slot = 0;
    for (i = 0; i < MAX_ITEM; ++i) {
        if (!g_item[i].alive) { slot = i; break; }
        if (g_item[i].age > g_item[slot].age) slot = i;
    }
    g_item[slot].spr = (uint8_t)id;
    g_item[slot].x = (int16_t)x;
    g_item[slot].y = (int16_t)y;
    g_item[slot].vx = (int16_t)((rnd() % 5) - 2);
    g_item[slot].vy = -3;
    g_item[slot].age = 0;
    g_item[slot].alive = 1;
}

static void enemy_spawn(int slot, int kind, int col, int row) {
    int w = 12, h = 24, hp = 4;
    switch (kind) {
        case EN_BAT:    w = 12; h = 10; hp = 4;  break;
        case EN_IMP:    w = 12; h = 20; hp = 8;  break;
        case EN_OWL:    w = 18; h = 14; hp = 6;  break;
        case EN_WARDEN: w = 18; h = 34; hp = WARDEN_HP; break;
        default: return;
    }
    vxpe_body_init(&g_body[slot], col * TS + (TS - w) / 2, row * TS, w, h);
    if (kind != EN_BAT && kind != EN_OWL) vxpe_body_settle(&g_body[slot], &g_map_g);
    vxpe_combat_init(&g_com[slot], &g_body[slot], (uint16_t)hp, 1, slot);
    g_kind[slot] = (uint8_t)kind;
    g_alive[slot] = 1;
    g_state[slot] = 0;
    g_clock[slot] = 0;
    g_cast_ms[slot] = 0;
    g_anim_ms[slot] = 0;
    g_home_x[slot] = (int16_t)(col * TS + TS / 2);
    g_hover_y[slot] = (int16_t)((row + 1) * TS + h / 2);
    g_body[slot].facing = 1;
}

static void enemy_clear(int slot) {
    g_alive[slot] = 0;
    g_kind[slot] = EN_NONE;
    memset(&g_com[slot], 0, sizeof g_com[slot]);
    memset(&g_body[slot], 0, sizeof g_body[slot]);
}

static int free_slot(void) {
    int i;
    for (i = 1; i < MAX_ACT - 1; ++i)
        if (!g_alive[i] && g_kind[i] == EN_NONE) return i;
    for (i = 1; i < MAX_ACT - 1; ++i)
        if (!g_alive[i]) return i;
    return -1;
}

static void shoot(int team, int dir, int x, int y, int speed, int arc, int sprite_id) {
    VxpeProjectile2D p;
    VxpeProjectile2D* live;
    memset(&p, 0, sizeof p);
    p.vx_q8 = (int32_t)(dir < 0 ? -speed : speed) << 8;
    p.vy_q8 = (int32_t)arc << 8;
    p.gravity_q8 = 150 << 8;
    p.w = 8; p.h = 8;
    p.damage = 1;
    p.life_ms = 2600;
    p.kb_x_q8 = 60 << 8;
    p.kb_y_q8 = -(30 << 8);
    p.invuln_ms = 700;
    p.stun_ms = 120;
    p.hit_stop_ms = 40;
    p.team = (int8_t)team;
    p.dies_on_tile = 1;
    live = vxpe_proj_spawn(&g_proj, &p, x, y);
    if (live != NULL) g_proj_spr[live - g_proj.items] = (uint8_t)sprite_id;
}

/* --- the hunt ------------------------------------------------------------- */
static void start_run(void) {
    int i;
    for (i = 0; i < MAX_ACT; ++i) enemy_clear(i);
    for (i = 0; i < MAX_ITEM; ++i) g_item[i].alive = 0;
    for (i = 0; i < MAX_FX; ++i) g_fx[i].alive = 0;
    vxpe_proj_pool_init(&g_proj);
    for (i = 0; i < VXPE_PROJ_POOL2D_MAX; ++i) g_proj_spr[i] = VV_SP_ORB;

    vxpe_body_init(&g_body[0], 3 * TS, (PLANE_ROW - 2) * TS, 12, 24);
    vxpe_body_settle(&g_body[0], &g_map_g);
    vxpe_combat_init(&g_com[0], &g_body[0], HERO_HP, 0, 0);
    g_kind[0] = EN_NONE;
    g_alive[0] = 1;
    g_hero_slot = 0;

    for (i = 0; i < N_SPAWN; ++i) enemy_spawn(1 + i, SPAWNS[i].kind, SPAWNS[i].col, SPAWNS[i].row);
    for (i = 0; i < N_LOOT; ++i)
        item_spawn(LOOT[i].spr, LOOT[i].col * TS + TS / 2,
                   (LOOT[i].row + 1) * TS - (int)SP(LOOT[i].spr)->height / 2);

    vxpe_cam_init(&g_cam, SW, SH, WORLD_W, WORLD_H);
    vxpe_cam_set_deadzone(&g_cam, 74, 74, 120, 96);
    vxpe_cam_set_follow_ms(&g_cam, 110);
    vxpe_cam_snap(&g_cam, hero_x() - SW / 2, hero_y() - SH / 2);

    vxpe_hud_plate_default(&g_plate);
    vxpe_hud_gauge_init(&g_mpbar, 40, 22, 58, 6, MP_MAX);
    g_mpbar.color_full = C_MP;
    g_mpbar.color_low = vxpe2d_rgb565(74, 96, 148);
    g_mpbar.color_ghost = vxpe2d_rgb565(30, 52, 86);
    g_mpbar.segments = 5;
    g_mpbar.low_at = 20;
    vxpe_hud_gauge_set(&g_mpbar, 0);
    vxpe_hud_icon_row_init(&g_hearts, SP(VV_SP_HEART), SP(VV_SP_HEART_EMPTY), 40, 6, HERO_HP);
    g_hearts.pitch_x = 10;
    g_hearts.pitch_y = 10;
    vxpe_hud_boss_init(&g_boss, SW, SH, WARDEN_HP);
    vxpe_hud_minimap_init(&g_mm, g_rooms, g_room_tags, ROOMS_W, ROOMS_H, 3,
                          SW - ROOMS_W * 3 - 4, 4);
    /* Lifted off the core default: the plate behind the map is near-black, so a
     * near-black map interior leaves no separation between frame and field. */
    g_mm.color_bg = vxpe2d_rgb565(24, 26, 52);
    g_mm.color_room = vxpe2d_rgb565(98, 108, 146);

    g_run_ms = 0;
    g_score = 0;
    g_kills = 0;
    g_mp = 0;
    g_hit_stop_visual_ms = 0;
    g_win_ms = 0;
    g_dead_ms = 0;
    g_msg[0] = 0;
    g_msg_ms = 0;
    g_mend_ms = 0;
    g_scr = SCR_GAME;
    vxpe_cam_snap(&g_cam, hero_x() - SW / 2, hero_y() - SH / 2);
    vxpe_hud_boss_hide(&g_boss);
    reveal_around();
    msg("NIGHT HUNT - reach the east court", 3000);
}

static void msg(const char* text, int ms) {
    strncpy(g_msg, text, sizeof g_msg - 1);
    g_msg[sizeof g_msg - 1] = 0;
    g_msg_ms = ms;
}

/* Rooms the hero can currently see light up the corner map. */
static void reveal_around(void) {
    int rx = clampi(hero_x() / (ROOM_CX * TS), 0, ROOMS_W - 1);
    int ry = clampi((int)(g_body[0].y_q8 >> 8) / (ROOM_CY * TS), 0, ROOMS_H - 1);
    int dx, dy;
    for (dy = -1; dy <= 1; ++dy)
        for (dx = -1; dx <= 1; ++dx)
            if ((unsigned)(rx + dx) < ROOMS_W && (unsigned)(ry + dy) < ROOMS_H)
                if (g_rooms[(ry + dy) * ROOMS_W + rx + dx])
                    vxpe_hud_minimap_mark(&g_mm, rx + dx, ry + dy);
}

/* --- simulation ----------------------------------------------------------- */
#define WARDEN_SLOT (MAX_ACT - 1)

static void soul_burst(void) {
    int i;
    int hx = hero_x(), hy = hero_y();
    g_mp -= MP_BURST;
    vxpe_hud_gauge_set(&g_mpbar, (uint16_t)g_mp);
    vxpe_cam_shake(&g_cam, 5, 260);
    for (i = 0; i < 10; ++i) fx_spawn(VV_SP_SPARK, hx, hy, (int)(rnd() % 13u) - 6,
                                      (int)(rnd() % 13u) - 6, 16, 2);
    for (i = 1; i < MAX_ACT; ++i) {
        if (!g_alive[i] || !g_com[i].alive) continue;
        if (absi((int)(g_body[i].x_q8 >> 8) + g_body[i].w / 2 - hx) > 60) continue;
        if (absi((int)(g_body[i].y_q8 >> 8) + g_body[i].h / 2 - hy) > 60) continue;
        vxpe_combat_hurt(&g_com[i], 3, g_body[i].x_q8 >> 8 < hx ? -1 : 1,
                         120 << 8, -(60 << 8), 420, 180, 50, 0, NULL);
    }
    msg("SOUL BURST", 900);
}

static void try_villager(void) {
    int i;
    int npcx = VILLAGE_COL * TS + TS / 2;
    if (g_mend_ms > 0 || !g_com[0].alive) return;
    if (absi(hero_x() - npcx) > 26) return;
    if (absi((int)(g_body[0].y_q8 >> 8) - (surf_at(VILLAGE_COL) - 2) * TS) > 40) return;
    if (g_com[0].hp == g_com[0].max_hp && g_mp == MP_MAX) return;
    g_mend_ms = 6000;
    g_com[0].hp = g_com[0].max_hp;
    g_mp = MP_MAX;
    vxpe_hud_gauge_set(&g_mpbar, (uint16_t)g_mp);
    save_write();
    for (i = 0; i < 8; ++i)
        fx_spawn(VV_SP_SPARK, npcx, (PLANE_ROW - 1) * TS,
                 (int)(rnd() % 9u) - 4, -3, 20, 2);
    msg("MENDED AND SAVED - the court lies east", 2600);
}

static void save_write(void) {
    if (g_score > g_save.best) g_save.best = (uint16_t)g_score;
    g_save.kills = (uint16_t)(g_save.kills + g_kills);
    g_kills = 0;
    g_save.magic = 0x56534C31u;
    vxpe_cache_save(&g_save, (uint32_t)sizeof g_save);
}

static void events_apply(int n) {
    int i;
    for (i = 0; i < n; ++i) {
        const VxpeCombatEvent2D* e = &g_events[i];
        switch (e->kind) {
            case VXPE_CE2D_WINDUP:
                if (e->attacker == 0) {
                    fx_spawn(VV_SP_SPARK, e->x, e->y, 2, -1, 8, 1);
                } else if (e->attacker == WARDEN_SLOT) {
                    vxpe_cam_shake(&g_cam, 2, 120);
                }
                break;
            case VXPE_CE2D_HIT:
                fx_burst(VV_SP_BLOOD, e->x, e->y, 4, 5, 15);
                fx_spawn(VV_SP_SPARK, e->x, e->y, 0, 0, 9, 2);
                if (e->victim == 0) {
                    vxpe_cam_shake(&g_cam, 4, 220);
                    g_flash = 340;
                    if (g_msg_ms <= 0) msg("THE VEIL BITES BACK", 800);
                } else {
                    vxpe_cam_shake(&g_cam, e->attacker == 0 ? 2 : 3, 130);
                    if (e->attacker == 0) {
                        g_mp = clampi(g_mp + 7, 0, MP_MAX);
                        g_hit_stop_visual_ms = e->damage ? 70 : 0;
                    }
                    if (e->victim == WARDEN_SLOT)
                        vxpe_hud_boss_set_hp(&g_boss, e->hp_left);
                }
                break;
            case VXPE_CE2D_BLOCKED:
                fx_spawn(VV_SP_SPARK, e->x, e->y, -1, -2, 8, 1);
                break;
            case VXPE_CE2D_KILL:
                fx_burst(VV_SP_SOUL, e->x, e->y, 5, 6, 22);
                if (e->victim == 0) {
                    /* The verdict panel covers the middle of the screen but the
                     * plate rests on the bottom edge, so it has to retract: a
                     * dead hunt still showing a live boss bar reads as a bug.
                     * And a kill the hero is the victim of is not a kill. */
                    vxpe_hud_boss_hide(&g_boss);
                    break;
                }
                g_score += e->victim == WARDEN_SLOT ? 500 : 30;
                if (e->victim == WARDEN_SLOT) {
                    vxpe_cam_shake(&g_cam, 8, 900);
                    vxpe_hud_boss_hide(&g_boss);
                    g_win_ms = 1500;
                    msg("THE WARDEN FALLS", 2400);
                } else {
                    g_kills++;
                    item_spawn(VV_SP_SOUL, e->x, e->y);
                    if (rnd() % 3u == 0u) item_spawn(VV_SP_ORB, e->x + 8, e->y);
                }
                break;
            default: break;
        }
    }
}

static void hero_control(uint16_t dt) {
    VxpeBodyIntent2D in;
    in.x = vxpe_input_axis(&g_in, ACT_LEFT, ACT_RIGHT);
    in.y = (int8_t)((vxpe_input_held(&g_in, ACT_UP) ? -1 : 0) +
                    (vxpe_input_held(&g_in, ACT_DOWN) ? 1 : 0));
    in.jump = (uint8_t)vxpe_input_pressed(&g_in, ACT_JUMP);
    in.jump_held = (uint8_t)vxpe_input_held(&g_in, ACT_JUMP);
    if (vxpe_input_pressed(&g_in, ACT_ATTACK))
        vxpe_combat_attack(&g_com[0], &ATK_WHIP);
    if (vxpe_input_pressed(&g_in, ACT_BURST) && g_mp >= MP_BURST &&
        !vxpe_combat_frozen(&g_com[0]) && g_com[0].alive)
        soul_burst();
    try_villager();
    vxpe_combat_body_control(&g_com[0], &g_map_g, &g_walk, &in, dt);
    if (vxpe_body_touching(&g_body[0], &g_map_g, VXPE_TF_HAZARD)) {
        VxpeCombatEvent2D ev;
        if (vxpe_combat_hurt(&g_com[0], 1, in.x, 40 << 8, -(110 << 8), 900, 140, 40,
                             0xFF, &ev))
            events_apply(1);
    }
}

/* Triangle-wave hover in px/s. ARMv5TE has no divide instruction, so the phase
 * comes from a shift of the millisecond counter and the ramp is a multiply. */
static int tri16(int clock_ms, int shift, int amp) {
    int v = (clock_ms >> shift) & 7;      /* 0..7, mirrored below */
    if (v > 3) v = 7 - v;                 /* 0..3, then back down */
    return ((v * 2 - 3) * amp) >> 2;      /* roughly -amp .. +amp */
}

static void enemy_update(int i, uint16_t dt) {
    VxpeBody2D* b = &g_body[i];
    int cx = (int)(b->x_q8 >> 8) + b->w / 2;
    int cy = (int)(b->y_q8 >> 8) + b->h / 2;
    int dx = hero_x() - cx;
    int dy = hero_y() - cy;
    int dist = absi(dx);

    if (!g_alive[i] || !g_com[i].alive) return;
    if (vxpe_combat_frozen(&g_com[i])) return;   /* hit-stop holds the animation too */
    g_clock[i] += dt;
    if (g_cast_ms[i] > dt) g_cast_ms[i] -= dt; else g_cast_ms[i] = 0;
    if (g_reinforce_ms[i] > dt) g_reinforce_ms[i] -= dt; else g_reinforce_ms[i] = 0;

    /* Only bodies within a screen-width of the hero burn cycles. Ground walkers
     * keep falling so they cannot float where the mover left them. */
    if (i != WARDEN_SLOT && dist > SW + 40) {
        b->vx_q8 = 0;
        if (g_kind[i] == EN_BAT || g_kind[i] == EN_OWL) b->vy_q8 = 0;
        return;
    }

    switch (g_kind[i]) {
        case EN_BAT:
            if (!vxpe_combat_attacking(&g_com[i])) vxpe_combat_attack(&g_com[i], &ATK_TOUCH);
            switch (g_state[i]) {
                case 0: {
                    int target = g_home_x[i] + (((g_clock[i] >> 10) & 1) ? 46 : -46);
                    b->vx_q8 = (int32_t)(target > cx ? 24 : -24) << 8;
                    b->vy_q8 = (int32_t)tri16(g_clock[i], 6, 34) << 8;
                    if (dist < 96 && dy > -12 && dy < 70) { g_state[i] = 1; g_clock[i] = 0; }
                    break;
                }
                case 1:
                    b->vx_q8 = (int32_t)(dx > 3 ? 84 : dx < -3 ? -84 : 0) << 8;
                    b->vy_q8 = (int32_t)(dy > 3 ? 72 : dy < -3 ? -72 : 0) << 8;
                    if (g_clock[i] > 950) { g_state[i] = 2; g_clock[i] = 0; }
                    break;
                default:
                    b->vy_q8 = -(58 << 8);
                    b->vx_q8 = (int32_t)(g_home_x[i] > cx ? 20 : -20) << 8;
                    if (cy <= g_hover_y[i]) g_state[i] = 0;
                    break;
            }
            vxpe_combat_body_step(&g_com[i], &g_map_g, &g_fly, dt);
            break;

        case EN_IMP: {
            VxpeBodyIntent2D in;
            int patrol = (((g_clock[i] + 6000) >> 11) & 1) ? 40 : -40;
            int want = (g_state[i] == 1) ? dx : (g_home_x[i] + patrol - cx);
            in.x = (int8_t)(want > 6 ? 1 : want < -6 ? -1 : 0);
            in.y = 0;
            in.jump = 0;
            in.jump_held = 0;
            if (g_state[i] == 0) {
                if (dist < 132 && absi(dy) < 56) { g_state[i] = 1; g_clock[i] = 0; }
                if (g_cast_ms[i] == 0 && dist > 64 && dist < 190 && absi(dy) < 44) {
                    shoot(1, dx, cx, cy - 4, 74, -26, VV_SP_ORB);
                    g_cast_ms[i] = 2700;
                }
            } else {
                if (dist > 210) { g_state[i] = 0; g_clock[i] = 0; }
                if (dist < 24 && !vxpe_combat_attacking(&g_com[i]))
                    vxpe_combat_attack(&g_com[i], &ATK_CLUB);
                if (g_cast_ms[i] == 0 && dist > 90 && absi(dy) < 44) {
                    shoot(1, dx, cx, cy - 4, 80, -30, VV_SP_ORB);
                    g_cast_ms[i] = 2200;
                }
            }
            b->facing = (uint8_t)(dx > 0 ? 1 : 0);
            vxpe_combat_body_control(&g_com[i], &g_map_g, &g_imp, &in, dt);
            break;
        }

        case EN_OWL:
            if (g_state[i] == 0) {
                b->vx_q8 = (int32_t)(dx > 12 ? 34 : dx < -12 ? -34 : 0) << 8;
                b->vy_q8 = (int32_t)tri16(g_clock[i], 7, 30) << 8;
                if (dist < 150 && dy > 8 && vxpe_combat_attacking(&g_com[i]) == 0) {
                    g_state[i] = 1; g_clock[i] = 0;
                    vxpe_combat_attack(&g_com[i], &ATK_TALON);
                }
                vxpe_combat_body_step(&g_com[i], &g_map_g, &g_fly, dt);
            } else if (g_state[i] == 1) {
                b->vx_q8 = (int32_t)(dx > 4 ? 108 : dx < -4 ? -108 : 0) << 8;
                b->vy_q8 = (int32_t)(dy > 4 ? 96 : -40) << 8;
                vxpe_combat_body_step(&g_com[i], &g_map_g, &g_fly, dt);
                if (g_clock[i] > 820) { g_state[i] = 2; g_clock[i] = 0; }
            } else {
                b->vy_q8 = -(74 << 8);
                b->vx_q8 = (int32_t)(dx > 0 ? -18 : 18) << 8;
                vxpe_combat_body_step(&g_com[i], &g_map_g, &g_fly, dt);
                if (cy <= g_hover_y[i]) { g_state[i] = 0; g_clock[i] = 0; }
            }
            break;

        case EN_WARDEN: {
            VxpeBodyIntent2D in;
            int fast = g_com[i].hp <= WARDEN_HP / 2;
            in.x = (int8_t)(dx > 26 ? 1 : dx < -26 ? -1 : 0);
            in.y = 0; in.jump = 0; in.jump_held = 0;
            b->facing = (uint8_t)(dx > 0 ? 1 : 0);
            if (dist < 44 && !vxpe_combat_attacking(&g_com[i])) {
                vxpe_combat_attack(&g_com[i], &ATK_SLAM);
                vxpe_cam_shake(&g_cam, 3, 180);
            }
            if (g_cast_ms[i] == 0 && dist > 80) {
                shoot(1, dx, cx, cy - 10, 88, -34, VV_SP_SOUL);
                shoot(1, dx, cx, cy - 18, 82, -60, VV_SP_SOUL);
                shoot(1, dx, cx, cy - 2, 82, 6, VV_SP_SOUL);
                g_cast_ms[i] = (uint16_t)(fast ? 1700 : 3400);
            }
            if (g_reinforce_ms[i] == 0) {
                int s = free_slot();
                if (s > 0) {
                    enemy_spawn(s, EN_BAT, cx / TS + 2, PLANE_ROW - 5);
                    fx_burst(VV_SP_SPARK, cx, cy - 20, 6, 5, 14);
                }
                g_reinforce_ms[i] = (uint16_t)(fast ? 5200 : 8800);
            }
            vxpe_combat_body_control(&g_com[i], &g_map_g, &g_imp, &in, dt);
            break;
        }
        default: break;
    }
}

/* Loot runs in whole pixels per 33 ms tick: a Q8 velocity would need a divide by
 * 1000 to integrate on a core with no divide instruction, and at this scale the
 * sub-pixel term is invisible anyway. */
static void items_update(void) {
    int i;
    for (i = 0; i < MAX_ITEM; ++i) {
        Item* it = &g_item[i];
        int dxa, dya;
        if (!it->alive) continue;
        it->age++;
        dxa = hero_x() - it->x;
        dya = hero_y() - it->y;
        if (absi(dxa) < 56 && absi(dya) < 44) {        /* soul motes home in */
            it->vx = (int16_t)clampi(it->vx + (dxa > 0 ? 1 : -1), -6, 6);
            it->vy = (int16_t)clampi(it->vy + (dya > 0 ? 1 : -1), -6, 6);
        } else if (vxpe_tilemap_blocks_at_px(&g_map_g, it->x, it->y + 4,
                                            VXPE_TF_SOLID | VXPE_TF_ONEWAY)) {
            it->vy = 0;
            it->vx = (int16_t)(it->vx - (it->vx > 0 ? 1 : it->vx < 0 ? -1 : 0));
        } else if (it->vy < 6) {
            it->vy++;
        }
        it->x = (int16_t)(it->x + it->vx);
        it->y = (int16_t)(it->y + it->vy);
        if (absi(dxa) < 12 && absi(dya) < 14) {
            it->alive = 0;
            if (it->spr == VV_SP_ORB) {
                g_mp = clampi(g_mp + 24, 0, MP_MAX);
                vxpe_hud_gauge_set(&g_mpbar, (uint16_t)g_mp);
                msg("SOUL MP +24", 700);
            } else {
                g_score += it->spr == VV_SP_SOUL ? 50 : 15;
            }
            fx_spawn(VV_SP_SPARK, it->x, it->y, 0, -1, 10, 2);
            continue;
        }
        if (it->age > 900) it->alive = 0;
    }
    vxpe_hud_icon_row_set(&g_hearts, g_com[0].hp);
}

static void fx_update(uint16_t dt) {
    int i;
    (void)dt;
    for (i = 0; i < MAX_FX; ++i) {
        Fx* p = &g_fx[i];
        if (!p->alive) continue;
        p->x = (int16_t)(p->x + p->vx);
        p->y = (int16_t)(p->y + p->vy);
        p->vy = (int16_t)(p->vy + 1);
        if (--p->life == 0) p->alive = 0;
    }
}

static void sim_update(uint16_t dt, int attract) {
    int i, written;
    g_run_ms += dt;
    g_anim = (uint16_t)(g_anim + 1);

    for (i = 0; i < MAX_ACT; ++i) {
        if (!g_alive[i] || !g_com[i].alive) continue;
        vxpe_combat_update(&g_com[i], dt, NULL, 0);
    }

    if (attract) {
        /* The demo hunter is untouchable so an attract loop cannot end on a
         * menu screen; everything else about him is the real controller. */
        g_com[0].invuln_ms = 200;
        g_com[0].stun_ms = 0;
        demo_control(dt);
    } else if (g_com[0].alive) {
        hero_control(dt);
    }
    for (i = 1; i < MAX_ACT; ++i) enemy_update(i, dt);
    if (!attract) warden_gate();

    written = vxpe_combat_resolve(&g_com[0], MAX_ACT, &g_com[0], MAX_ACT,
                                 g_events, (int)(sizeof g_events / sizeof g_events[0]));
    if (written) events_apply(written);

    vxpe_proj_update(&g_proj, &g_map_g, dt);
    written = vxpe_proj_resolve(&g_proj, &g_com[0], MAX_ACT, g_events,
                              (int)(sizeof g_events / sizeof g_events[0]));
    if (written) events_apply(written);

    items_update();
    fx_update(dt);

    if (g_win_ms > 0) {
        g_win_ms -= dt;
        if (g_win_ms <= 0) {
            g_win_ms = 0;
            g_save.clears++;
            save_write();
            g_scr = SCR_WIN;
            g_title_ms = 0;
        }
    }
    if (!g_com[0].alive && g_scr == SCR_GAME) {
        g_dead_ms += dt;
        /* The verdict opens its own window: a hero who dies mid-jump would
         * otherwise read the very next hop as "dismiss" and never see the
         * panel he is supposed to learn from. */
        if (g_dead_ms > 1200) { save_write(); g_scr = SCR_OVER; g_title_ms = 0; }
    }
    if (g_flash > dt) g_flash -= dt; else g_flash = 0;
    if (g_hit_stop_visual_ms > dt) g_hit_stop_visual_ms -= dt; else g_hit_stop_visual_ms = 0;
    if (g_msg_ms > dt) g_msg_ms -= dt; else g_msg_ms = 0;
    if (g_mend_ms > dt) g_mend_ms -= dt; else g_mend_ms = 0;
    if (!attract && vxpe_input_pressed(&g_in, ACT_PAUSE)) {
        g_prev_scr = SCR_GAME;
        g_scr = SCR_PAUSE;
        vxpe_input_consume(&g_in, ACT_PAUSE);
    }

    /* Both the hunt and the attract demo frame the hunter, so the title screen
     * pans exactly like play. */
    vxpe_cam_set_lookahead(&g_cam, g_body[0].facing ? 28 : -28);
    vxpe_cam_follow(&g_cam, hero_x(), hero_y(), dt);
    vxpe_cam_update(&g_cam, dt);
    reveal_around();
    hud_update(dt);
}

/* The court: the Warden wakes once the hero crosses the gate column, and the
 * name plate arrives with it. Dead slots stay dead - the hunt is one pass. */
static void warden_gate(void) {
    if (g_alive[WARDEN_SLOT] || hero_x() < BOSS_GATE_COL * TS) return;
    enemy_spawn(WARDEN_SLOT, EN_WARDEN, 122, PLANE_ROW - 3);
    vxpe_hud_boss_show(&g_boss, "STONE WARDEN", WARDEN_HP);
    vxpe_cam_shake(&g_cam, 6, 700);
    fx_burst(VV_SP_SPARK, 122 * TS + 8, (PLANE_ROW - 2) * TS, 10, 7, 22);
    msg("THE STONE WARDEN WAKES", 2600);
}

/* __PART3__ */

/* --- rendering ------------------------------------------------------------ */
#define FAR_Y  22                      /* band tops on screen; the bands carry */
#define MID_Y  58                      /* their own sky gradient, so only the  */
#define NEAR_Y (PLANE_ROW * TS - 64)   /* slivers above and between need fills  */
#define PLANE_Y (PLANE_ROW * TS)

static VxpeFontStyle st_title, st_ui, st_gold, st_hint;

static void fonts_init(void) {
    vxpe_font_style_default(&st_ui);
    st_ui.color565 = C_IVORY;
    vxpe_font_style_default(&st_gold);
    st_gold.color565 = C_GOLD;
    vxpe_font_style_default(&st_hint);
    st_hint.color565 = C_DIM;
    st_hint.spacing = 0;
    vxpe_font_style_default(&st_title);
    st_title.font_id = VXPE_FONT_DISPLAY;
    st_title.scale = 2;
    st_title.effects = VXPE_FONT_OUTLINE | VXPE_FONT_SHADOW;
    st_title.color565 = vxpe2d_rgb565(242, 236, 208);
    st_title.outline565 = vxpe2d_rgb565(5, 2, 4);
    st_title.shadow565 = vxpe2d_rgb565(110, 0, 22);
}

static VxpeRectI screen_clip(void) {
    VxpeRectI r;
    r.x = 0; r.y = 0; r.w = (int16_t)SW; r.h = (int16_t)SH;
    return r;
}

static void sky_and_bands(void) {
    uint32_t camx_q8 = (uint32_t)(g_cam.x_q8 + g_cam.shake_x_q8);
    int camx = vxpe_cam_x(&g_cam);
    int camy = vxpe_cam_y(&g_cam);
    VxpeTileDraw2D view;

    vxpe2d_gradient_vertical_dithered(FB, SW, SH, 0, 0, SW, FAR_Y,
        vxpe2d_rgb565(0xCE, 0xF0, 0xEC), vxpe2d_rgb565(0x6F, 0xDA, 0xF2));
    vxpe2d_gradient_vertical_dithered(FB, SW, SH, 0, MID_Y + 56, SW,
        NEAR_Y - (MID_Y + 56), vxpe2d_rgb565(0x0E, 0x1E, 0x60),
        vxpe2d_rgb565(0x18, 0x1B, 0x3A));

    vxpe2d_blit_parallax_x(FB, SW, SH, &VV_BAND_FAR_SPRITE, (int32_t)camx_q8, 56, FAR_Y, 0, 4);
    vxpe2d_blit_parallax_x(FB, SW, SH, &VV_BAND_MID_SPRITE, (int32_t)camx_q8, 118, MID_Y, 0, 4);

    /* The moon is a sprite, not band art: it must not tile across the sky. */
    blit(150 - (camx >> 3), 30 - (camy >> 4), VV_SP_MOON, 0, WHITE565, 0);

    vxpe2d_blit_parallax_x(FB, SW, SH, &VV_BAND_NEAR_SPRITE, (int32_t)camx_q8, 186, NEAR_Y, 0, 4);

    vxpe_tile_view(&view, -camx, -camy);
    vxpe_tilemap_draw(FB, SW, SH, &g_map_g, &view);
}

/* Holes in the forest floor: the near band stops at PLANE_Y, so the air below
 * it gets a void fill and a cold lip instead of showing flat sky. */
static void draw_voids(void) {
    int c = 0;
    int camx = vxpe_cam_x(&g_cam), camy = vxpe_cam_y(&g_cam);
    while (c < MAP_W) {
        int x0, depth, c1;
        if (g_surf[c] <= PLANE_ROW) { c++; continue; }
        depth = g_surf[c] - PLANE_ROW;
        c1 = c + 1;
        while (c1 < MAP_W && g_surf[c1] > PLANE_ROW) c1++;
        x0 = c * TS - camx;
        vxpe2d_fill_rect(FB, SW, SH, x0, PLANE_Y - camy, (c1 - c) * TS,
                         depth * TS, C_VOID);
        vxpe2d_fill_rect(FB, SW, SH, x0, PLANE_Y - camy, (c1 - c) * TS, 1, C_PIT_LIP);
        c = c1;
    }
}

static void draw_ladders(void) {
    int i, camx = vxpe_cam_x(&g_cam), camy = vxpe_cam_y(&g_cam);
    uint16_t wood = vxpe2d_rgb565(138, 95, 56);
    uint16_t wood_lo = vxpe2d_rgb565(78, 51, 30);
    for (i = 0; i < N_LADDER; ++i) {
        int x = LADDERS[i].col * TS - camx + 3;
        int y = LADDERS[i].r0 * TS - camy;
        int h = (LADDERS[i].r1 - LADDERS[i].r0 + 1) * TS;
        int r;
        if (x < -TS || x > SW) continue;
        vxpe2d_fill_rect(FB, SW, SH, x, y, 1, h, wood_lo);
        vxpe2d_fill_rect(FB, SW, SH, x + 9, y, 1, h, wood_lo);
        for (r = 2; r < h; r += 5)
            vxpe2d_fill_rect(FB, SW, SH, x, y + r, 10, 1, wood);
    }
}

static void draw_props(void) {
    int i;
    for (i = 0; i < N_PROP; ++i) {
        int col = PROPS[i].col;
        int feet = surf_at(col) * TS;
        int wx = col * TS + TS / 2;
        const VxpeSprite565* s = SP(PROPS[i].spr);
        if (!vxpe_cam_visible(&g_cam, wx - s->width / 2, feet - s->height,
                              s->width, s->height)) continue;
        blit_feet(wx, feet, PROPS[i].spr, 0, WHITE565, 0);
    }
    /* The villager is an entity too: it anchors the save point at the gate. */
    {
        int wx = VILLAGE_COL * TS + TS / 2;
        blit_feet(wx, surf_at(VILLAGE_COL) * TS, VV_SP_VILLAGER,
                  hero_x() < wx ? 1 : 0, WHITE565, 0);
    }
}

static int ent_flash(int i) {
    if (g_com[i].flash_ms > 0) return (g_anim & 1) ? vxpe2d_rgb565(255, 130, 130) : (int)WHITE565;
    if (i == 0 && g_flash > 0) return (g_anim & 1) ? vxpe2d_rgb565(255, 90, 90) : (int)WHITE565;
    return (int)WHITE565;
}

static int hero_frame(void) {
    if (!g_com[0].alive) return VV_SP_HERO_HURT;
    if (vxpe_combat_attacking(&g_com[0])) return VV_SP_HERO_ATTACK0;
    if (g_com[0].stun_ms > 0) return VV_SP_HERO_HURT;
    if (!g_body[0].on_ground && !g_body[0].on_ladder)
        return g_body[0].vy_q8 < 0 ? VV_SP_HERO_JUMP : VV_SP_HERO_FALL;
    if (absi(g_body[0].vx_q8) > (6 << 8))
        return VV_SP_HERO_RUN0 + ((g_anim >> 2) & 3);
    return VV_SP_HERO_IDLE0 + ((g_anim >> 4) & 1);
}

static int enemy_frame(int i) {
    int base = g_kind[i] == EN_BAT ? VV_SP_BAT0
             : g_kind[i] == EN_IMP ? VV_SP_IMP0
             : g_kind[i] == EN_OWL ? VV_SP_OWL0 : VV_SP_STATUE;
    if (g_kind[i] == EN_WARDEN) return VV_SP_STATUE;
    return base + (((g_anim + i * 3) >> (g_kind[i] == EN_BAT ? 1 : 3)) & 1);
}

static void draw_entities(void) {
    int i, camx = vxpe_cam_x(&g_cam), camy = vxpe_cam_y(&g_cam);
    VxpeRectI hb;

    for (i = 0; i < MAX_ITEM; ++i) {
        Item* it = &g_item[i];
        const VxpeSprite565* s;
        if (!it->alive) continue;
        s = SP(it->spr);
        if (!vxpe_cam_visible(&g_cam, it->x, it->y - s->height, s->width, s->height)) continue;
        blit_feet(it->x, it->y + (tri16(it->age * 33, 3, 2) >> 1), it->spr, 0, WHITE565, 0);
    }

    for (i = 1; i < MAX_ACT; ++i) {
        const VxpeSprite565* s;
        int bx, by, flip, tint;
        if (!g_alive[i] || !g_com[i].alive) continue;
        s = SP(enemy_frame(i));
        bx = (int)(g_body[i].x_q8 >> 8);
        by = (int)(g_body[i].y_q8 >> 8);
        if (!vxpe_cam_visible(&g_cam, bx - 4, by - 4, g_body[i].w + 8, g_body[i].h + 8)) continue;
        flip = g_body[i].facing ? 0 : 1;
        /* The Warden is carved from the same block as the yard statues, and at
         * 240x320 an identical silhouette means the player cannot pick the boss
         * out of the scenery. A permanent curse tint costs nothing and does. */
        tint = ent_flash(i);
        if (g_kind[i] == EN_WARDEN && tint == (int)WHITE565)
            tint = vxpe2d_rgb565(255, 148, 168);
        blit(bx - camx + g_body[i].w / 2 - s->width / 2,
             by - camy + g_body[i].h - s->height, enemy_frame(i), flip,
             (uint16_t)tint, 0);
    }

    if (g_alive[0]) {
        const VxpeSprite565* s = SP(hero_frame());
        int bx = (int)(g_body[0].x_q8 >> 8), by = (int)(g_body[0].y_q8 >> 8);
        int hf = hero_frame();
        /* Blink during i-frames: the invulnerability has to be legible or the
         * player reads a fair hit as a bug. */
        uint8_t alpha = g_com[0].invuln_ms > 0 && (g_anim & 1) ? 120 : 0;
        blit(bx - camx + g_body[0].w / 2 - s->width / 2,
             by - camy + g_body[0].h - s->height, hf,
             g_body[0].facing ? 0 : 1, (uint16_t)ent_flash(0), alpha);

        if (vxpe_combat_hitbox(&g_com[0], &hb)) {
            /* 3 frames across the 130 ms active window; the window starts after
             * the 70 ms windup and the divide-free form uses a 128 ms span. */
            int phase = clampi((int)(((g_com[0].atk_ms - 70u) * 3u) >> 7), 0, 2);
            int id = VV_SP_WHIP0 + phase;
            const VxpeSprite565* ws = SP(id);
            int facing = g_body[0].facing;
            /* The crescent is authored around a pivot 4 px inside the sprite,
             * on the hand row - and a flipped sprite puts that pivot on the
             * other edge. Anchoring the sprite box instead buried phase 0
             * inside the hero and left the last frame short of the hitbox. */
            int pivot = facing ? bx + g_body[0].w + phase * 2
                               : bx - 1 - phase * 2;
            (void)hb;
            blit(pivot - (facing ? 4 : ws->width - 5) - camx,
                 by + 11 - (int)ws->height / 2 - camy, id, facing ? 0 : 1,
                 WHITE565, 0);
        }
    }

    for (i = 0; i < g_proj.count; ++i) {
        const VxpeProjectile2D* p = &g_proj.items[i];
        if (!p->active) continue;
        blit((int)(p->x_q8 >> 8) - camx, (int)(p->y_q8 >> 8) - camy,
             g_proj_spr[i], 0, WHITE565, 0);
    }

    for (i = 0; i < MAX_FX; ++i) {
        const Fx* p = &g_fx[i];
        const VxpeSprite565* s;
        VxpeBlit565 op;
        if (!p->alive) continue;
        s = SP(p->spr);
        memset(&op, 0, sizeof op);
        op.dst_x = (int16_t)(p->x - camx - s->width / 2);
        op.dst_y = (int16_t)(p->y - camy - s->height / 2);
        op.dst_w = (uint16_t)(s->width * p->scale / 2);
        op.dst_h = (uint16_t)(s->height * p->scale / 2);
        op.tint565 = WHITE565;
        op.alpha = (uint8_t)(40 + p->life * 8);
        op.blend = VXPE_BLEND_ADD;
        vxpe2d_blit(FB, SW, SH, s, &op);
    }
}

static void hud_update(uint16_t dt) {
    vxpe_hud_gauge_update(&g_mpbar, dt);
    vxpe_hud_boss_update(&g_boss, dt);
    vxpe_hud_icon_row_set(&g_hearts, g_com[0].hp);
}

static void draw_hud(void) {
    VxpeRectI plate;
    char buf[24];
    int rx, ry;

    plate.x = 2; plate.y = 2; plate.w = 34; plate.h = 34;
    vxpe_hud_plate_draw(FB, SW, SH, plate, &g_plate);
    vxpe_hud_portrait_draw(FB, SW, SH, plate, SP(VV_SP_PORTRAIT), &g_plate,
                           g_flash > 0 && (g_anim & 1) ? vxpe2d_rgb565(255, 110, 110) : WHITE565,
                           0);
    vxpe_hud_icon_row_draw(FB, SW, SH, &g_hearts);
    vxpe_hud_gauge_draw(FB, SW, SH, &g_mpbar);
    /* The label sits past the gauge, not under it: the strip below the gauge is
     * the sky, and a two-glyph word there reads as level art. */
    vxpe_font_draw(FB, SW, SH, 102, 22, "MP", &st_hint, screen_clip());
    vxpe_hud_format_int(buf, sizeof buf, g_score, 4);
    vxpe_hud_text_right(FB, SW, SH, SW - 4, 26, buf, &st_gold);

    rx = clampi(hero_x() / (ROOM_CX * TS), 0, ROOMS_W - 1);
    ry = clampi((int)(g_body[0].y_q8 >> 8) / (ROOM_CY * TS), 0, ROOMS_H - 1);
    /* A bevel behind the corner map: an unrevealed map is a black rectangle, and
     * without the frame it reads as a hole punched in the HUD. */
    plate.x = (int16_t)(g_mm.x - 2);
    plate.y = (int16_t)(g_mm.y - 2);
    plate.w = (int16_t)(g_mm.width * g_mm.cell + 4);
    plate.h = (int16_t)(g_mm.height * g_mm.cell + 4);
    vxpe_hud_plate_draw(FB, SW, SH, plate, &g_plate);
    vxpe_hud_minimap_draw(FB, SW, SH, &g_mm, rx, ry);
    vxpe_hud_boss_draw(FB, SW, SH, &g_boss, NULL);
    /* Paint cost, in the one corner the world never draws status into. */
    {
        char ms[8] = "MS ";
        vxpe_hud_format_int(ms + 3, sizeof ms - 3, g_frame_ms, 2);
        vxpe_font_draw(FB, SW, SH, 2, 306, ms, &st_hint, screen_clip());
    }

    if (g_msg_ms > 0) {
        VxpeHudPlate2D p2;
        VxpeRectI box;
        int w = vxpe_font_measure(g_msg, &st_ui) + 14;
        vxpe_hud_plate_default(&p2);
        p2.inner = vxpe2d_rgb565(20, 8, 40);
        box.x = (int16_t)((SW - w) / 2);
        box.y = 246;
        box.w = (int16_t)w;
        box.h = 18;
        vxpe_hud_plate_draw(FB, SW, SH, box, &p2);
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 251, g_msg, &st_ui);
    }
}

/* The world, camera-relative and with no status layer over it, so a menu can
 * put the same frame under a scrim. */
static void draw_world(void) {
    VxpeTileDraw2D view;
    sky_and_bands();          /* sky, three bands, moon, opaque ground layer */
    draw_voids();             /* air under the forest floor where it breaks */
    draw_ladders();
    /* Second view of the same flags array, masked atlas, same camera. */
    vxpe_tilemap_draw(FB, SW, SH, &g_map_p,
                      vxpe_tile_view(&view, -vxpe_cam_x(&g_cam),
                                     -vxpe_cam_y(&g_cam)));
    draw_props();
    draw_entities();
}

/* --- screens and the app shell --------------------------------------------
 * Navigation lives in menu_update, pixels in draw_screens, and the stage keeps
 * living behind every panel: the title screen runs the world with an autopilot
 * hunter and a pause is a freeze rather than a blackout. Nothing here knows the
 * handset - the shell below is the only place the SDK callbacks touch the game.
 */
enum { MI_HUNT, MI_HELP, MI_QUIT, MI_N };
static const char* const MENU_LABELS[MI_N] = {
    "NIGHT HUNT", "HOW TO PLAY", "LEAVE THE VEIL"
};
#define MENU_X 40
#define MENU_W 160
#define MENU_Y0 176
#define MENU_STEP 26

static int g_booted;
static void stop(void);

static void pen_release(void) {
    if (g_pen_action >= 0) {
        vxpe_input_release(&g_in, (int16_t)g_pen_action);
        g_pen_action = -1;
    }
}

/* Virtual pad. The pen has no codes of its own, so a region answers with the
 * synthetic code bound to the matching action and the game sees a key press.
 * Top third leaps, the middle row runs and whips, the bottom row climbs and
 * spends MP - a thumb can reach all eight without covering the play area. */
static int pen_code(int x, int y) {
    if (x < 0 || y < 0 || x >= SW || y >= SH) return -1;
    if (y < SH / 3) return PEN_JUMP;
    if (y < (SH * 2) / 3) {
        if (x < SW / 3) return PEN_LEFT;
        if (x >= (SW * 2) / 3) return PEN_RIGHT;
        return PEN_ATK;
    }
    if (x < SW / 3) return PEN_UP;
    if (x >= (SW * 2) / 3) return PEN_DOWN;
    return PEN_BURST;
}

static int menu_row_at(int y) {
    int i;
    for (i = 0; i < MI_N; ++i) {
        int ry = MENU_Y0 + i * MENU_STEP;
        if (y >= ry - 5 && y < ry + MENU_STEP - 7) return i;
    }
    return -1;
}

static int nav_moved(int act) {
    return vxpe_input_pressed(&g_in, act) || vxpe_input_repeated(&g_in, act);
}
static int nav_confirm(void) {
    return vxpe_input_pressed(&g_in, ACT_OK) || vxpe_input_pressed(&g_in, ACT_JUMP);
}

static void to_menu(void) {
    pen_release();
    start_run();          /* a fresh stage for the attract view */
    g_scr = SCR_MENU;
    g_title_ms = 0;
    g_menu = 0;
    g_attract_dir = 1;
}

static void menu_pick(int i) {
    if (i == MI_HUNT) {
        start_run();
        pen_release();
    } else if (i == MI_HELP) {
        g_scr = SCR_HELP;
        g_title_ms = 0;
    } else {
        stop();
        vm_exit_app();
    }
}

static void menu_update(uint16_t dt) {
    int back = vxpe_input_pressed(&g_in, ACT_BACK);
    g_title_ms += dt;

    /* Only the attract screens keep simulating; a pause or a verdict holds the
     * last frame so the player can read what killed them. */
    if (g_scr == SCR_SPLASH || g_scr == SCR_MENU || g_scr == SCR_HELP)
        sim_update(dt, 1);

    switch (g_scr) {
    case SCR_SPLASH:
        if (g_title_ms > 2400 || nav_confirm() || vxpe_input_pressed(&g_in, ACT_ATTACK)) {
            g_scr = SCR_MENU;
            g_title_ms = 0;
            g_menu = 0;
        }
        break;
    case SCR_MENU:
        if (nav_moved(ACT_UP)) g_menu = (g_menu + MI_N - 1) % MI_N;
        else if (nav_moved(ACT_DOWN)) g_menu = (g_menu + 1) % MI_N;
        if (nav_confirm() || vxpe_input_pressed(&g_in, ACT_ATTACK)) {
            vxpe_input_consume(&g_in, ACT_OK);
            vxpe_input_consume(&g_in, ACT_JUMP);
            menu_pick(g_menu);
        }
        break;
    case SCR_HELP:
        if (nav_confirm() || back) { g_scr = SCR_MENU; g_title_ms = 0; }
        break;
    case SCR_PAUSE:
        if (nav_confirm() || vxpe_input_pressed(&g_in, ACT_PAUSE)) {
            vxpe_input_consume(&g_in, ACT_OK);
            vxpe_input_consume(&g_in, ACT_JUMP);
            g_scr = SCR_GAME;
        } else if (back) {
            to_menu();
        }
        break;
    default:                       /* SCR_OVER, SCR_WIN */
        if (g_title_ms > 400 &&
            (nav_confirm() || back || vxpe_input_pressed(&g_in, ACT_MENU))) to_menu();
        break;
    }
}

/* --- panel drawing -------------------------------------------------------- */
static void scrim(uint8_t a) {
    vxpe2d_overlay_rect(FB, SW, SH, 0, 0, SW, SH, vxpe2d_rgb565(4, 2, 12), a,
                        VXPE_BLEND_ALPHA);
}

static void panel(int x, int y, int w, int h) {
    VxpeHudPlate2D p;
    VxpeRectI r;
    vxpe_hud_plate_default(&p);
    p.inner = vxpe2d_rgb565(18, 8, 34);
    r.x = (int16_t)x; r.y = (int16_t)y; r.w = (int16_t)w; r.h = (int16_t)h;
    vxpe_hud_plate_draw(FB, SW, SH, r, &p);
}

/* One "label .... value" line inside a panel. */
static void stat_line(int y, const char* label, int32_t value, int digits) {
    char buf[16];
    vxpe_font_draw(FB, SW, SH, MENU_X + 6, y, label, &st_hint, screen_clip());
    vxpe_hud_format_int(buf, sizeof buf, value, digits);
    vxpe_hud_text_right(FB, SW, SH, MENU_X + MENU_W - 6, y, buf, &st_gold);
}

static void draw_screens(void) {
    char buf[24];
    int i;

    switch (g_scr) {
    case SCR_GAME:
        draw_world();
        draw_hud();
        return;

    case SCR_SPLASH:
    case SCR_MENU:
        draw_world();
        scrim(96);
        blit((SW - SP(VV_SP_EMBLEM)->width) / 2, g_scr == SCR_SPLASH ? 74 : 34,
             VV_SP_EMBLEM, 0, WHITE565, 0);
        vxpe_hud_text_center(FB, SW, SH, SW / 2,
                             g_scr == SCR_SPLASH ? 112 : 62, "VAMPIRE VEIL",
                             &st_title);
        if (g_scr == SCR_SPLASH) {
            vxpe_hud_text_center(FB, SW, SH, SW / 2, 148, "NIGHT HUNT", &st_gold);
            if (((g_title_ms >> 7) & 1) == 0)
                vxpe_hud_text_center(FB, SW, SH, SW / 2, 274, "PRESS OK", &st_hint);
            return;
        }
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 92, "NIGHT HUNT", &st_gold);
        panel(MENU_X, MENU_Y0 - 10, MENU_W, MI_N * MENU_STEP + 44);
        for (i = 0; i < MI_N; ++i) {
            int y = MENU_Y0 + i * MENU_STEP;
            const VxpeFontStyle* st = i == g_menu ? &st_gold : &st_ui;
            if (i == g_menu)
                vxpe_font_draw(FB, SW, SH, MENU_X + 4, y + 1, ">", &st_gold,
                               screen_clip());
            vxpe_font_draw(FB, SW, SH, MENU_X + 18, y + 1, MENU_LABELS[i], st,
                           screen_clip());
        }
        stat_line(MENU_Y0 + MI_N * MENU_STEP + 6, "BEST SOULS", g_save.best, 5);
        stat_line(MENU_Y0 + MI_N * MENU_STEP + 20, "SOULS TAKEN", g_save.kills, 5);
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 300, "OK picks   9 pauses", &st_hint);
        return;

    case SCR_HELP:
        draw_world();
        scrim(170);
        panel(12, 28, SW - 24, 262);
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 36, "HOW TO PLAY", &st_gold);
        {
            static const char* const LINES[] = {
                "ARROWS or 2 4 6 8",
                "  run, climb, crouch",
                "OK or 7",
                "  leap - hold it for height",
                "L.SK or 5",
                "  crack the whip",
                "R.SK or 3",
                "  soul burst, 50 MP",
                "9 pause   1 back",
                "",
                "PEN: tap the sky to leap,",
                "the middle to whip, the",
                "bottom row to run, climb",
                "or burst.",
                "",
                "Souls fill MP. The villager",
                "mends and saves. The Warden",
                "waits in the east court."
            };
            /* 18 lines at a 12 px pitch end at y 268, inside the plate. The
             * body font is 8 px tall, so the last row still has 6 px of lip. */
            int y = 52;
            for (i = 0; i < (int)(sizeof LINES / sizeof LINES[0]); ++i, y += 12)
                vxpe_font_draw(FB, SW, SH, 22, y, LINES[i], &st_ui, screen_clip());
        }
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 296, "OK to go back", &st_hint);
        return;

    case SCR_PAUSE:
        draw_world();
        draw_hud();
        scrim(150);
        panel(40, 120, SW - 80, 74);
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 132, "PAUSED", &st_title);
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 168, "OK resumes", &st_hint);
        return;

    default:
        draw_world();
        draw_hud();
        scrim(160);
        panel(34, 104, SW - 68, 116);
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 114,
                             g_scr == SCR_WIN ? "THE VEIL LIFTS" : "A SOUL TAKEN",
                             &st_title);
        stat_line(154, "SOULS", g_score, 5);
        stat_line(168, "BEST", g_save.best, 5);
        buf[0] = 0;
        vxpe_hud_format_int(buf, sizeof buf, g_save.clears, 2);
        {
            char line[40];
            int n = 0;
            const char* s = "COURTS CLEARED ";
            while (*s) line[n++] = *s++;
            for (i = 0; buf[i]; ++i) line[n++] = buf[i];
            line[n] = 0;
            vxpe_hud_text_center(FB, SW, SH, SW / 2, 186, line, &st_ui);
        }
        vxpe_hud_text_center(FB, SW, SH, SW / 2, 236, "OK to return", &st_hint);
        return;
    }
}

/* --- the app shell -------------------------------------------------------- */
static void draw(void) {
    uint32_t t0;
    if (g_layer < 0) return;
    FB = (uint16_t*)vm_graphic_get_layer_buffer(g_layer);
    if (!FB) return;
    t0 = vm_get_tick_count();
    draw_screens();
    vm_graphic_flush_layer(&g_layer, 1);
    g_frame_ms = (int)(vm_get_tick_count() - t0);
}

static void frame(uint16_t dt) {
    /* One update per step: the map turns the raw codes the callbacks queued into
     * this step's edges, so a press can never be read twice. */
    vxpe_input_update(&g_in, dt);
    if (g_scr == SCR_GAME) sim_update(dt, 0);
    else menu_update(dt);
}

/* VXPEmu fires the app timer at whatever rate it can paint, so the sim steps on
 * wall-clock time and plays the same speed on a handset as on the host. */
static void tick(VMINT tid) {
    static uint32_t last_ms;
    static int acc;
    uint32_t now = vm_get_tick_count();
    int32_t d = (int32_t)(now - last_ms);
    (void)tid;
    if (!last_ms || d > 300) d = DT_MS;
    last_ms = now;
    acc += (int)d;
    if (acc > 3 * DT_MS) acc = 3 * DT_MS;   /* three steps is as far as we chase */
    for (; acc >= DT_MS; acc -= DT_MS) frame(DT_MS);
    draw();
}

static void start(void) {
    if (g_layer < 0) g_layer = vm_graphic_create_layer(0, 0, SW, SH, -1);
    if (!g_booted) {
        g_booted = 1;
        g_pen_action = -1;
        level_build();
        sprites_init();
        input_init();
        physics_init();
        fonts_init();
        memset(&g_save, 0, sizeof g_save);
        g_save.magic = 0x56534C31u;
        vxpe_cache_init();
        if (!vxpe_cache_load(&g_save, (uint32_t)sizeof g_save) ||
            g_save.magic != 0x56534C31u) {
            memset(&g_save, 0, sizeof g_save);
            g_save.magic = 0x56534C31u;
        }
        g_rng = (uint32_t)vm_get_tick_count() ^ 0x9E3779B9u;
        if (!g_rng) g_rng = 1u;
        to_menu();
        g_scr = SCR_SPLASH;
        g_title_ms = 0;
    }
    if (g_timer < 0) g_timer = vm_create_timer(DT_MS, tick);
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
        start();
        break;
    case VM_MSG_ACTIVE:
        start();
        break;
    case VM_MSG_PAINT:
        draw();
        break;
    case VM_MSG_INACTIVE:
        if (g_scr == SCR_GAME) g_scr = SCR_PAUSE;
        if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }
        break;
    case VM_MSG_QUIT:
        if (g_booted && g_scr != SCR_SPLASH && g_scr != SCR_MENU) save_write();
        stop();
        vm_exit_app();
        break;
    default:
        break;
    }
}

void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN || event == VM_KEY_EVENT_LONG_PRESS ||
        event == VM_KEY_EVENT_REPEAT)
        vxpe_input_press(&g_in, (int16_t)keycode);
    else if (event == VM_KEY_EVENT_UP)
        vxpe_input_release(&g_in, (int16_t)keycode);
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    int code;
    if (g_scr != SCR_GAME) {
        if (event != VM_PEN_EVENT_TAP) return;
        if (g_scr == SCR_SPLASH) { g_scr = SCR_MENU; g_title_ms = 0; g_menu = 0; }
        else if (g_scr == SCR_HELP) { g_scr = SCR_MENU; g_title_ms = 0; }
        else if (g_scr == SCR_MENU) {
            int row = menu_row_at((int)y);
            if (row >= 0) { g_menu = row; menu_pick(row); }
        } else if (g_scr == SCR_PAUSE) g_scr = SCR_GAME;
        else if (g_title_ms > 400) to_menu();
        return;
    }
    if (event == VM_PEN_EVENT_RELEASE || event == VM_PEN_EVENT_ABORT) {
        pen_release();
        return;
    }
    code = pen_code((int)x, (int)y);
    if (code < 0) { pen_release(); return; }
    if (code != g_pen_action) {
        pen_release();
        g_pen_action = code;
        vxpe_input_press(&g_in, (int16_t)code);
    }
}

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
