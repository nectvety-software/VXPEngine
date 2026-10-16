/* Vampire Veil: Night Hunt — logic sinh ton nhip nhanh (fixed-capacity).
 * Dieu khien: 2/4/6/8 (mui ten) di chuyen, 5/OK ban tia rang,
 * 0 tam dung/doi man, 9 pause, 1 choi lai, Back thoat. */
#include "vv_game.h"

VvState VV;

uint32_t vv_rand(void) { VV.rng = VV.rng * 1664525u + 1013904223u; return VV.rng; }

void vv_init(void) {
    VV.rng = 0xB16B00B5u;
    VV.max_hp = 100;
    vv_reset_run();
    VV.scr = VV_SCR_TITLE;
}

void vv_reset_run(void) {
    int i;
    VV.px = 120; VV.py = 250;
    VV.hp = VV.max_hp;
    VV.fangs = 3;
    VV.souls = 0; VV.kills = 0;
    VV.time_ms = 0; VV.spawn_ms = 0; VV.bolt_ms = 0; VV.hurt_ms = 0;
    VV.paused = 0; VV.facing = 0; VV.held = 0; VV.frame = 0;
    for (i = 0; i < VV_MAX_BATS; i++) VV.bats[i].active = 0;
    for (i = 0; i < VV_MAX_FANGS; i++) VV.fangs[i].active = 0;
    for (i = 0; i < VV_MAX_SOULS; i++) VV.souls_arr[i].active = 0;
    for (i = 0; i < VV_MAX_BOLTS; i++) VV.bolts[i].active = 0;
}

/* __PART2__ */
