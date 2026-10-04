/* game.h - CungThuBongDen (Archer of Darkness) - MRE .vxp game
 * 240x320 pixel-art side-view wave arena.
 */
#ifndef CTBD_GAME_H
#define CTBD_GAME_H

#include "vmsys.h"

#define CANVAS_W 240
#define CANVAS_H 320
#define TICK_MS  50 /* 20 fps */

/* arena grid */
#define TILE 24
#define COLS 10
#define ROWS 13

/* entity limits */
#define MAX_ENEMIES 8
#define MAX_ARROWS  16
#define MAX_EPROJ   8
#define MAX_PICKUPS 24
#define MAX_FX      16

/* game states */
enum { ST_TITLE, ST_PLAY, ST_SHOP, ST_PAUSE, ST_OVER };

typedef struct {
    float x, y, vx, vy;
    int w, h;
    int dir;          /* 1 right, -1 left */
    int on_ground, climbing;
    int hp, max_hp, mp, max_mp;
    int level, arrows, gold, gems, potions, score;
    int dmg;          /* arrow damage */
    int crit;         /* crit chance percent */
    int enh_atk, enh_hp, enh_crit; /* enhancement levels (weapon/armor/crit) */
    int mat_metal, mat_wood, mat_fur; /* crafting mats; gems double as "ngoc" */
    int shoot_cd, hurt_cd, invuln, dash_t;
    int cd_power, cd_multi, cd_dash; /* cooldown ticks */
    int anim, anim_t; /* sprite frame selector */
} player_t;

enum { ET_OGRE, ET_DRAGON, ET_BOSS };

typedef struct {
    int type, active;
    float x, y, vx, vy;
    int w, h, hp, max_hp;
    int dir, state, hurt_t, atk_cd, anim_t;
} enemy_t;

typedef struct { int active; float x, y, vx, vy; int dmg, pierce, power; } arrow_t;
typedef struct { int active, kind; float x, y, vx, vy; int dmg; } eproj_t; /* 0 fireball 1 rock */
typedef struct { int active, kind; float x, y, vy; int t; } pickup_t;      /* PK_* */
typedef struct { int active, kind, t, x, y; } fx_t;                        /* FX_* */

enum { PK_COIN, PK_GEM, PK_QUIVER, PK_POTION, PK_METAL, PK_WOOD, PK_FUR };
enum { MAT_GEM, MAT_METAL, MAT_WOOD, MAT_FUR };
enum { FX_SPARK, FX_BURST, FX_PICK, FX_CRIT };

typedef struct {
    int state, tick;
    player_t pl;
    enemy_t en[MAX_ENEMIES];
    arrow_t ar[MAX_ARROWS];
    eproj_t ep[MAX_EPROJ];
    pickup_t pk[MAX_PICKUPS];
    fx_t fx[MAX_FX];
    int wave;
    int pend_ogre, pend_dragon, pend_boss; /* unspawned this wave */
    int spawn_cd, wave_clear_t, msg_t;
    char msg[48];
    int shop_sel, shop_tab; /* shop_tab: 0 mua, 1 cuong hoa, 2 ban */
    int hi_score;      /* loaded from save */
    int blink;         /* ui blink counter */
    int shake_t;
    int key_left, key_right, key_up, key_down, key_jump; /* held keys */
    char grid[ROWS][COLS + 1];
} game_t;

extern game_t G;
extern int g_ox, g_oy; /* canvas offset inside real screen */

/* called from main.c */
void game_init(void);      /* load resources + storage, then reset */
void game_reset(void);     /* reset run state (retry) */
void game_shutdown(void);
void game_tick(void);      /* one timer tick: update + draw */
void game_key(int keycode);        /* VM_KEY_* */
void game_pen(int x, int y);       /* pen tap in screen coords */
int shop_cost(int item);   /* gold price of shop item 0..3 (draw.c reads it) */
/* materials + enhancement api (draw.c reads these) */
int mat_count(int mat);    /* MAT_* -> units in the shared bag */
int sell_price(int mat);   /* gold per unit when selling */
void shop_sell(int mat);
int enh_lv(int which);     /* 0 atk, 1 hp, 2 crit */
int enh_gold(int which);
int enh_need(int which, int mat); /* mats required by recipe */
int enh_ok(int which);     /* can afford right now */
void shop_enhance(int which);
int enh_maxed(int which);
int player_level(void);    /* 1 + total enhancement levels */
void game_draw(void);      /* render whole frame into the layer buffer */

/* provided by main.c */
extern VMUINT8* g_buf;
void gfx_present(void);            /* flush layer */

#endif
