#pragma once
/* Vampire Veil: Night Hunt — game state (fixed-capacity, zero heap per frame).
 * S30+ MRE 240x320 portrait. Sinh ton nhip nhanh: dan doi hut mau,
 * tha rang hut linh hon, en quai doi dan doi. */
#include "vmsys.h"

#define VV_W 240
#define VV_H 320

/* Screens */
#define VV_SCR_TITLE 0
#define VV_SCR_GAME  1
#define VV_SCR_OVER  2
#define VV_SCR_WIN   3

/* Tunables (tick = 50ms) */
#define VV_MAX_BATS   24
#define VV_MAX_FANGS  12
#define VV_MAX_SOULS  30
#define VV_MAX_BOLTS  8
#define VV_HUNT_MS    90000   /* song 90s → WIN */
#define VV_TICK_MS    50

typedef struct { int16_t x, y, vx, vy; uint8_t active, kind; int16_t hp; } VvBat;
typedef struct { int16_t x, y, vx, vy; uint8_t active; } VvFang;
typedef struct { int16_t x, y, vx, vy; uint8_t active; } VvSoul;
typedef struct { int16_t x, y, vx, vy; uint8_t active; uint16_t age; } VvBolt;

typedef struct {
    uint8_t scr;
    uint8_t paused;
    uint8_t held;          /* bit0 L, bit1 R, bit2 U, bit3 D */
    uint8_t facing;        /* 0 phai, 1 trai */
    int16_t px, py;
    int16_t hp, max_hp;
    int16_t fangs;         /* dan nang luong tha rang */
    int32_t souls;         /* diem linh hon */
    int32_t kills;
    uint32_t time_ms;
    uint32_t rng;
    uint16_t spawn_ms;
    uint16_t bolt_ms;
    uint16_t hurt_ms;
    uint16_t frame;
    VvBat bats[VV_MAX_BATS];
    VvFang fangs[VV_MAX_FANGS];
    VvSoul souls_arr[VV_MAX_SOULS];
    VvBolt bolts[VV_MAX_BOLTS];
} VvState;

extern VvState VV;

void vv_init(void);
void vv_reset_run(void);
void vv_update(void);              /* 1 tick 50ms */
void vv_hold(int key, int down);   /* 2/4/6/8 */
void vv_input(int key);            /* 5/0/9/1/-1 */
void vv_draw(uint16_t *fb);
uint32_t vv_rand(void);
