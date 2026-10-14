/* Balance probe: StormArena25D's pure combat loop (ai_control / physics /
 * step_attack / land_hit) copied out of src/main.c with the rendering and VFX
 * stripped, so the two AI controllers can be run head-to-head for hundreds of
 * matches in a second. Compile: gcc -O2 -o tmp/combat_sim tmp/combat_sim.c */
#include <stdio.h>
#include <string.h>

#define ARENA_HALF 110
#define STEP_MS 33

enum { ST_IDLE = 0, ST_WALK, ST_JUMP, ST_PUNCH, ST_KICK, ST_SUPER,
       ST_HIT, ST_KO };

typedef struct Atk { unsigned char startup, active, recover, dmg, range; } Atk;
static const Atk ATK_PUNCH = { 3, 2, 7, 6, 100 };
static const Atk ATK_KICK  = { 4, 3, 10, 10, 116 };
static const Atk ATK_SUPER = { 6, 4, 16, 25, 150 };

typedef struct Fighter {
    int x, vx, y10, vy10, hp, gauge, face, state, st_t, hit_done;
    int combo, combo_dmg, combo_t, flash, ai_cool;
    int hits_landed, supers, starts, hit_ticks;
} Fighter;

static unsigned int g_rng = 0xA26E5F01u;
static int g_over, g_slow, g_shake, g_input_t, g_tick;

static unsigned rnd32(void) {
    g_rng = g_rng * 1664525u + 1013904223u;
    return g_rng;
}
static Fighter g_f[2];

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
    f->starts++;
}
static void land_hit(Fighter* atk, Fighter* def, const Atk* a) {
    atk->hit_done = 1;
    def->hp -= a->dmg;
    def->gauge += a->dmg / 3;
    atk->gauge += a->dmg / 2 + 4;
    if (atk->gauge > 100) atk->gauge = 100;
    if (def->gauge > 100) def->gauge = 100;
    def->state = ST_HIT; def->st_t = 0;
    def->vx = atk->face * (a->dmg >= 20 ? 14 : (a->dmg >= 10 ? 9 : 6));
    def->flash = 12;
    atk->hits_landed++;
    atk->combo += 1;
    atk->combo_dmg += a->dmg;
    atk->combo_t = 60;
    if (def->hp <= 0) {
        def->hp = 0;
        def->state = ST_KO;
        def->vy10 = 180;
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
    if (f->state == ST_HIT) ++f->hit_ticks;
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
static int V_attract, V_order, V_p1off;

static void reset_match(void) {
    memset(g_f, 0, sizeof(g_f));
    g_f[0].hp = 100; g_f[0].x = -110; g_f[0].face = 1;
    g_f[1].hp = 100; g_f[1].x = 110;  g_f[1].face = -1;
    g_over = 0; g_slow = 0; g_shake = 0;
    g_input_t = V_attract ? g_tick - 999 : g_tick;
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
        int roll = (int)(rnd32() % 100);
        if (me->gauge >= 100 && roll < 26) { start_attack(me, ST_SUPER); me->supers++; }
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
    if (g_slow) --g_slow;
    else if (!g_over) {
        int attract = (int)g_tick - g_input_t > 150;
        if (!attract) p1->face = p2->x >= p1->x ? 1 : -1;
        if (attract && !V_p1off) ai_control(p1, p2);
        physics(p1, 0, 0);
        ai_control(p2, p1);
        physics(p2, 0, 0);
        if (V_order) {
            step_attack(p2, p1, ST_PUNCH, &ATK_PUNCH);
            step_attack(p2, p1, ST_KICK, &ATK_KICK);
            step_attack(p2, p1, ST_SUPER, &ATK_SUPER);
            step_attack(p1, p2, ST_PUNCH, &ATK_PUNCH);
            step_attack(p1, p2, ST_KICK, &ATK_KICK);
            step_attack(p1, p2, ST_SUPER, &ATK_SUPER);
        } else {
            step_attack(p1, p2, ST_PUNCH, &ATK_PUNCH);
            step_attack(p1, p2, ST_KICK, &ATK_KICK);
            step_attack(p1, p2, ST_SUPER, &ATK_SUPER);
            step_attack(p2, p1, ST_PUNCH, &ATK_PUNCH);
            step_attack(p2, p1, ST_KICK, &ATK_KICK);
            step_attack(p2, p1, ST_SUPER, &ATK_SUPER);
        }
    } else {
        physics(p1, 0, 0);
        physics(p2, 0, 0);
    }
    if (g_shake) --g_shake;
    (void)i;
}

int main(void) {
    int m, n = 400, v;
    for (v = 0; v < 8; ++v) {
        long h1 = 0, h2 = 0, d1 = 0, d2 = 0, s1 = 0, s2 = 0, k1 = 0, k2 = 0;
        long wins1 = 0, wins2 = 0, su1 = 0, su2 = 0, dur = 0;
        V_attract = v & 1;
        V_order = (v >> 1) & 1;
        V_p1off = (v >> 2) & 1;
        for (m = 0; m < n; ++m) {
            int t0 = g_tick;
            g_rng = 0xA26E5F01u + (unsigned)m * 7919u;
            reset_match();
            while (!g_over && g_tick - t0 < 30000) { ++g_tick; update(); }
            h1 += g_f[0].hits_landed; h2 += g_f[1].hits_landed;
            s1 += g_f[0].starts;      s2 += g_f[1].starts;
            k1 += g_f[0].hit_ticks;   k2 += g_f[1].hit_ticks;
            d1 += 100 - g_f[1].hp;    d2 += 100 - g_f[0].hp;
            su1 += g_f[0].supers;     su2 += g_f[1].supers;
            dur += g_tick - t0;
            if (g_f[1].hp <= 0) ++wins1; else if (g_f[0].hp <= 0) ++wins2;
        }
        printf("attract0=%d order2first=%d p1passive=%d\n", V_attract, V_order,
               V_p1off);
        printf("  P1: starts=%5.1f hits=%5.2f land=%.0f%% dmg=%5.1f hitstun=%5.1f "
               "supers=%.2f wins=%4.1f%%\n",
               (double)s1 / n, (double)h1 / n, s1 ? 100.0 * h1 / s1 : 0.0,
               (double)d1 / n, (double)k1 / n, (double)su1 / n, 100.0 * wins1 / n);
        printf("  P2: starts=%5.1f hits=%5.2f land=%.0f%% dmg=%5.1f hitstun=%5.1f "
               "supers=%.2f wins=%4.1f%%   avg dur=%.1f s\n\n",
               (double)s2 / n, (double)h2 / n, s2 ? 100.0 * h2 / s2 : 0.0,
               (double)d2 / n, (double)k2 / n, (double)su2 / n, 100.0 * wins2 / n,
               (double)dur / n * STEP_MS / 1000.0);
    }
    return 0;
}
