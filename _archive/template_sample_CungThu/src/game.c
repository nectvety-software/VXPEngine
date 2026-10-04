/* game.c - CungThuBongDen gameplay: wave arena, archer vs ogres & dragons */
#include "vmgraph.h"
#include "vmio.h"
#include "vmchset.h"
#include "vmstdlib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "game.h"
#include "gfx.h"
#include "res.h"

game_t G;
int g_ox = 0, g_oy = 0;
static char g_grid_saved[ROWS][COLS + 1];

/* ------------------------------------------------------------------ map */
static char tile(int cx, int cy) {
    if (cx < 0 || cx >= COLS || cy < 0 || cy >= ROWS) return '#';
    return G.grid[cy][cx];
}

static int solid_cell(char c) { return c == '#'; }
static int plat_cell(char c)  { return c == '=' || c == 'B'; } /* one-way */

static int solid_at(float x, float y) { return solid_cell(tile((int)(x / TILE), (int)(y / TILE))); }
static int plat_at(float x, float y)  { return plat_cell(tile((int)(x / TILE), (int)(y / TILE))); }
static int ladder_at(float x, float y) {
    char c = tile((int)(x / TILE), (int)(y / TILE));
    return c == 'L';
}

/* ------------------------------------------------------------------ fx */
static fx_t* fx_free(void) {
    int i;
    for (i = 0; i < MAX_FX; i++) if (!G.fx[i].active) return &G.fx[i];
    return 0;
}

static void fx_add(int kind, int x, int y) {
    fx_t* f = fx_free();
    if (!f) return;
    f->active = 1; f->kind = kind; f->x = x; f->y = y; f->t = 0;
}

static pickup_t* pk_free(void) {
    int i;
    for (i = 0; i < MAX_PICKUPS; i++) if (!G.pk[i].active) return &G.pk[i];
    return 0;
}

static void pk_add(int kind, float x, float y) {
    pickup_t* p = pk_free();
    if (!p) return;
    p->active = 1; p->kind = kind; p->x = x; p->y = y; p->vy = -1.5f; p->t = 0;
}

static void set_msg(const char* s) {
    strncpy(G.msg, s, sizeof(G.msg) - 1);
    G.msg[sizeof(G.msg) - 1] = 0;
    G.msg_t = 120; /* 6 s */
}

/* ------------------------------------------------------------------ combat */
static void hurt_player(int dmg) {
    player_t* p = &G.pl;
    if (p->invuln > 0 || G.state != ST_PLAY) return;
    p->hp -= dmg;
    p->hurt_cd = 20;
    p->invuln = 50;
    G.shake_t = 6;
    sfx_play(1);
    if (p->hp <= 0) {
        p->hp = 0;
        G.state = ST_OVER;
        if (p->score >= G.hi_score) { G.hi_score = p->score; save_write(G.hi_score); }
    }
}

static void drop_loot(enemy_t* e) {
    int i, n;
    switch (e->type) {
    case ET_OGRE:  n = 2 + (rand() % 3); for (i = 0; i < n; i++) pk_add(PK_COIN, e->x + e->w / 2, e->y + 6);
                   if (rand() % 100 < 22) pk_add(PK_QUIVER, e->x + e->w / 2, e->y);
                   if (rand() % 100 < 10) pk_add(PK_POTION, e->x + e->w / 2, e->y);
                   if (rand() % 100 < 35) pk_add(PK_METAL, e->x + 4 + rand() % 20, e->y);
                   if (rand() % 100 < 30) pk_add(PK_WOOD, e->x + 4 + rand() % 20, e->y);
                   if (rand() % 100 < 12) pk_add(PK_FUR, e->x + 4 + rand() % 20, e->y);
                   break;
    case ET_DRAGON: n = 1 + (rand() % 2); for (i = 0; i < n; i++) pk_add(PK_COIN, e->x + e->w / 2, e->y);
                    if (rand() % 100 < 40) pk_add(PK_GEM, e->x + e->w / 2, e->y);
                    if (rand() % 100 < 25) pk_add(PK_METAL, e->x + 8 + rand() % 24, e->y);
                    break;
    case ET_BOSS:  for (i = 0; i < 8 + rand() % 5; i++) pk_add(PK_COIN, e->x + 8 + rand() % 40, e->y + 4);
                   pk_add(PK_GEM, e->x + e->w / 2 - 14, e->y);
                   pk_add(PK_GEM, e->x + e->w / 2 + 14, e->y);
                   pk_add(PK_POTION, e->x + e->w / 2 - 10, e->y);
                   pk_add(PK_QUIVER, e->x + e->w / 2 + 10, e->y);
                   pk_add(PK_METAL, e->x + 4, e->y);
                   pk_add(PK_METAL, e->x + 40, e->y);
                   pk_add(PK_FUR, e->x + e->w / 2, e->y);
                   if (rand() % 100 < 60) pk_add(PK_WOOD, e->x + 22 + rand() % 12, e->y);
                   break;
    }
}

static void hurt_enemy(enemy_t* e, int dmg) {
    e->hp -= dmg;
    e->hurt_t = 8;
    fx_add(FX_SPARK, (int)e->x + e->w / 2, (int)e->y + e->h / 2);
    sfx_play(1);
    if (e->hp <= 0) {
        e->active = 0;
        fx_add(FX_BURST, (int)e->x + e->w / 2, (int)e->y + e->h / 2);
        sfx_play(3);
        G.pl.score += (e->type == ET_BOSS ? 200 : e->type == ET_DRAGON ? 30 : 20);
        drop_loot(e);
    }
}

static enemy_t* en_free(void) {
    int i;
    for (i = 0; i < MAX_ENEMIES; i++) if (!G.en[i].active) return &G.en[i];
    return 0;
}

static void spawn_enemy(int type) {
    enemy_t* e = en_free();
    player_t* p = &G.pl;
    /* endless floors: floor 1 -> monster level 0, +1 per floor */
    int lv = G.wave - 1;
    if (lv < 0) lv = 0;
    if (!e) return;
    memset(e, 0, sizeof(*e));
    e->type = type; e->active = 1; e->dir = -1;
    if (type == ET_DRAGON) {
        float sp = 0.8f + lv * 0.04f; if (sp > 1.6f) sp = 1.6f;
        e->w = 42; e->h = 22;
        e->x = CANVAS_W + 10;
        e->y = 60 + rand() % 50;
        e->vx = -sp;
        e->hp = e->max_hp = 18 + lv * 6;
    } else {
        int boss = (type == ET_BOSS);
        float sp;
        e->w = boss ? 56 : 34; e->h = boss ? 40 : 40;
        /* spawn on the right, on top of the ground or a platform */
        e->x = CANVAS_W - e->w - 2;
        e->y = 11 * TILE - e->h;
        sp = boss ? 0.5f : (0.55f + lv * 0.03f);
        if (sp > 1.3f) sp = 1.3f;
        e->vx = -sp;
        e->hp = e->max_hp = boss ? (160 + lv * 25) : (26 + lv * 8);
        e->atk_cd = 90;
    }
    (void)p;
}

/* ------------------------------------------------------------------ waves */
static void wave_start(int n) {
    G.wave = n;
    G.pend_ogre = 2 + n / 2;
    G.pend_dragon = (n >= 2) ? n / 3 : 0;
    G.pend_boss = (n % 5 == 0) ? 1 : 0;
    G.spawn_cd = 30;
    G.state = ST_PLAY;
    sprintf(G.msg, "TANG %d (LV %d)%s", n, n - 1, G.pend_boss ? " BOSS!" : "");
    G.msg_t = 100;
}

static int alive_enemies(void) {
    int i, n = 0;
    for (i = 0; i < MAX_ENEMIES; i++) if (G.en[i].active) n++;
    return n;
}

/* ------------------------------------------------------------------ player */
static void player_shoot(int multi) {
    player_t* p = &G.pl;
    arrow_t* a;
    int i, n = multi ? 3 : 1;
    float angs[3] = { 0.0f, -0.26f, 0.26f };
    if (p->shoot_cd > 0) return;
    if (p->arrows <= 0) { set_msg("OUT OF ARROWS!"); return; }
    p->arrows -= 1;
    p->shoot_cd = multi ? 25 : 14;
    p->anim = 5; p->anim_t = 10; /* show bow pose */
    for (i = 0; i < n; i++) {
        int k;
        for (k = 0; k < MAX_ARROWS; k++) if (!G.ar[k].active) {
            a = &G.ar[k];
            a->active = 1;
            a->x = p->x + p->w / 2 + p->dir * 10;
            a->y = p->y + 10 + i * 3 - 3;
            a->vx = p->dir * 3.8f;
            a->vy = multi ? angs[i] * 3.8f : 0.0f;
            a->dmg = p->dmg;
            a->pierce = 0; a->power = 0;
            break;
        }
    }
    sfx_play(0);
}

static void use_power_shot(void) {
    player_t* p = &G.pl;
    int k;
    if (p->cd_power > 0 || p->mp < 30 || p->arrows <= 0) return;
    p->mp -= 30; p->cd_power = 160; p->arrows--;
    for (k = 0; k < MAX_ARROWS; k++) if (!G.ar[k].active) {
        G.ar[k].active = 1;
        G.ar[k].x = p->x + p->w / 2 + p->dir * 10;
        G.ar[k].y = p->y + 10;
        G.ar[k].vx = p->dir * 4.6f; G.ar[k].vy = 0;
        G.ar[k].dmg = p->dmg * 3; G.ar[k].pierce = 1; G.ar[k].power = 1;
        break;
    }
    p->anim = 5; p->anim_t = 10;
    sfx_play(0);
}

static void use_multi_shot(void) {
    player_t* p = &G.pl;
    if (p->cd_multi > 0 || p->mp < 40 || p->arrows < 3) return;
    p->mp -= 40; p->cd_multi = 200;
    player_shoot(1);
}

static void use_dash(void) {
    player_t* p = &G.pl;
    if (p->cd_dash > 0 || p->mp < 20) return;
    p->mp -= 20; p->cd_dash = 120;
    p->dash_t = 14;
    p->invuln = 20;
    p->vx = p->dir * 5.0f;
}

static void use_potion(void) {
    player_t* p = &G.pl;
    if (p->potions <= 0 || p->hp >= p->max_hp) return;
    p->potions--;
    p->hp += 50;
    if (p->hp > p->max_hp) p->hp = p->max_hp;
    fx_add(FX_PICK, (int)p->x + p->w / 2, (int)p->y);
    sfx_play(2);
    set_msg("+50 HP");
}

/* ------------------------------------------------------------------ update */
static void phys_move(player_t* p) {
    int i;
    float nx, ny;

    /* horizontal */
    nx = p->x + p->vx;
    if (p->vx > 0) {
        if (!solid_at(nx + p->w, p->y + 4) && !solid_at(nx + p->w, p->y + p->h - 2)) p->x = nx;
    } else if (p->vx < 0) {
        if (!solid_at(nx, p->y + 4) && !solid_at(nx, p->y + p->h - 2)) p->x = nx;
    }
    if (p->x < 2) p->x = 2;
    if (p->x > CANVAS_W - p->w - 2) p->x = CANVAS_W - p->w - 2;

    /* vertical */
    ny = p->y + p->vy;
    if (p->vy > 0) { /* falling: full solids + one-way platforms */
        for (i = 0; i < 2; i++) {
            float fx_ = p->x + (i ? p->w - 3 : 3);
            float fy = ny + p->h;
            if (solid_at(fx_, fy) || (plat_at(fx_, fy) && p->y + p->h <= (int)(fy / TILE) * TILE + 6)) {
                ny = (int)(fy / TILE) * TILE - p->h;
                p->vy = 0; p->on_ground = 1;
                goto done_v;
            }
        }
        p->on_ground = 0;
    } else if (p->vy < 0) { /* rising: only full solids */
        for (i = 0; i < 2; i++) {
            float fx_ = p->x + (i ? p->w - 3 : 3);
            if (solid_at(fx_, ny)) { ny = p->y; p->vy = 0; break; }
        }
    }
done_v:
    p->y = ny;
    if (p->y > CANVAS_H) { p->y = CANVAS_H - p->h; p->vy = 0; }
}

static void update_player(void) {
    player_t* p = &G.pl;
    float cx = p->x + p->w / 2;

    if (p->hurt_cd > 0) p->hurt_cd--;
    if (p->invuln > 0) p->invuln--;
    if (p->shoot_cd > 0) p->shoot_cd--;
    if (p->cd_power > 0) p->cd_power--;
    if (p->cd_multi > 0) p->cd_multi--;
    if (p->cd_dash > 0) p->cd_dash--;
    if (p->anim_t > 0) p->anim_t--;
    if (G.tick % 30 == 0 && p->mp < p->max_mp) p->mp++;
    if (G.tick % 200 == 0 && p->arrows < 5) p->arrows++;

    if (p->dash_t > 0) {
        p->dash_t--;
        if (p->dash_t == 0) p->vx = 0;
    }

    /* ladder climbing */
    if (!p->climbing && (G.key_up || G.key_down) && ladder_at(cx, p->y + p->h / 2)) {
        p->climbing = 1; p->vy = 0; p->vx = 0;
        G.key_jump = 0; /* NUM2 sets jump+up together; don't let it abort the climb */
    }
    if (p->climbing) {
        if (!ladder_at(cx, p->y + p->h / 2) && !ladder_at(cx, p->y + p->h - 2)) p->climbing = 0;
        else if (G.key_left || G.key_right) { /* step off sideways */
            p->climbing = 0; p->vy = 0;
        } else {
            if (G.key_up) p->y -= 1.2f;
            if (G.key_down) p->y += 1.2f;
            if (G.key_jump) { p->climbing = 0; p->vy = -3.0f; G.key_jump = 0; }
            else { p->on_ground = 0; goto clamp_y; }
        }
    }

    /* walking input */
    if (p->dash_t <= 0) {
        if (G.key_left) { p->vx = -1.7f; p->dir = -1; }
        else if (G.key_right) { p->vx = 1.7f; p->dir = 1; }
        else p->vx = 0;
    }
    if (G.key_jump && p->on_ground && !p->climbing) { p->vy = -3.6f; p->on_ground = 0; G.key_jump = 0; }

    if (!p->on_ground || p->vy > 0) p->vy += 0.14f;
    if (p->vy > 4.5f) p->vy = 4.5f;
    phys_move(p);

    /* floor spikes hurt while standing on them: the spike cell is the one
       holding the feet (row 10), not the floor below it (row 11) */
    if (p->on_ground && tile((int)(cx / TILE), (int)((p->y + p->h - 1) / TILE)) == 'H')
        hurt_player(10);

clamp_y:
    if (p->y < 40) p->y = 40;
    /* animation state */
    if (p->anim_t > 0) p->anim = 5;                 /* bow pose */
    else if (p->hurt_cd > 10) p->anim = 6;          /* hit */
    else if (p->climbing) p->anim = 3;
    else if (!p->on_ground) p->anim = 4;            /* jump */
    else if (G.key_left || G.key_right || p->dash_t > 0) {
        if (G.tick % 12 == 0) p->anim = (p->anim == 1 ? 2 : 1);
    } else {
        if (G.tick % 40 == 0) p->anim = (p->anim == 7 ? 8 : 7); /* idle */
    }
}

static void update_arrows(void) {
    int i, j;
    player_t* p = &G.pl;
    for (i = 0; i < MAX_ARROWS; i++) {
        arrow_t* a = &G.ar[i];
        if (!a->active) continue;
        a->x += a->vx; a->y += a->vy;
        if (a->x < -20 || a->x > CANVAS_W + 20 || a->y < 0 || a->y > CANVAS_H) { a->active = 0; continue; }
        if (solid_at(a->x, a->y)) { fx_add(FX_SPARK, (int)a->x, (int)a->y); a->active = 0; continue; }
        for (j = 0; j < MAX_ENEMIES; j++) {
            enemy_t* e = &G.en[j];
            if (!e->active) continue;
            if (a->x >= e->x && a->x <= e->x + e->w && a->y >= e->y && a->y <= e->y + e->h) {
                int crit = (rand() % 100 < p->crit); /* crit chance, x2 damage */
                hurt_enemy(e, a->dmg * (crit ? 2 : 1));
                if (crit) fx_add(FX_CRIT, (int)e->x + e->w / 2, (int)e->y - 4);
                if (a->pierce) { a->dmg = a->dmg * 2 / 3; }
                else { a->active = 0; }
                break;
            }
        }
        (void)p;
    }
}

static void update_enemies(void) {
    int i;
    player_t* p = &G.pl;
    int lv = G.wave - 1; if (lv < 0) lv = 0;
    for (i = 0; i < MAX_ENEMIES; i++) {
        enemy_t* e = &G.en[i];
        if (!e->active) continue;
        if (e->hurt_t > 0) e->hurt_t--;
        if (e->atk_cd > 0) e->atk_cd--;

        if (e->type == ET_DRAGON) {
            e->x += e->vx;
            e->y += sinf((float)G.tick * 0.06f + i) * 0.8f;
            /* patrol back and forth across the sky */
            if (e->x < 4) { e->vx = (float)fabs((double)e->vx); e->dir = 1; }
            if (e->x > CANVAS_W - e->w - 4) { e->vx = -(float)fabs((double)e->vx); e->dir = -1; }
            e->anim_t++;
            if (e->atk_cd <= 0 && G.state == ST_PLAY) {
                e->atk_cd = 150 - (lv >= 7 ? 40 : 0);
                {
                    int k;
                    float dx2 = (p->x + p->w / 2) - (e->x + e->w / 2);
                    float dy2 = (p->y + p->h / 2) - (e->y + e->h);
                    float len = (float)sqrt(dx2 * dx2 + dy2 * dy2);
                    for (k = 0; k < MAX_EPROJ; k++) if (!G.ep[k].active) {
                        G.ep[k].active = 1; G.ep[k].kind = 0;
                        G.ep[k].x = e->x + e->w / 2; G.ep[k].y = e->y + e->h;
                        G.ep[k].vx = dx2 / len * 2.0f; G.ep[k].vy = dy2 / len * 2.0f;
                        G.ep[k].dmg = 10 + lv;
                        break;
                    }
                }
            }
        } else { /* ogre / boss walker */
            float dx = (p->x + p->w / 2) - (e->x + e->w / 2);
            float adx = (float)fabs((double)dx);
            if (adx > (e->type == ET_BOSS ? 34 : 26)) {
                e->x += (dx > 0 ? 1 : -1) * (float)fabs((double)e->vx);
                e->dir = dx > 0 ? 1 : -1;
                e->anim_t++;
            } else if (e->atk_cd <= 0) {
                e->atk_cd = e->type == ET_BOSS ? 110 : 90;
                e->state = 1; /* attack pose */
                hurt_player(e->type == ET_BOSS ? 16 + lv / 2 : 8 + lv / 2);
            }
            if (e->state == 1 && e->atk_cd < 70) e->state = 0;
            /* boss throws rocks */
            if (e->type == ET_BOSS && e->atk_cd == 55 && G.state == ST_PLAY) {
                int k;
                for (k = 0; k < MAX_EPROJ; k++) if (!G.ep[k].active) {
                    G.ep[k].active = 1; G.ep[k].kind = 1;
                    G.ep[k].x = e->x + e->w / 2; G.ep[k].y = e->y;
                    G.ep[k].vx = (p->x - e->x) / 60.0f;
                    G.ep[k].vy = -3.2f;
                    G.ep[k].dmg = 18 + lv / 2;
                    break;
                }
            }
        }
        /* contact damage for boss */
        if (e->type == ET_BOSS && p->x + p->w > e->x + 6 && p->x < e->x + e->w - 6 &&
            p->y + p->h > e->y && p->y < e->y + e->h)
            hurt_player(12 + lv / 3);
    }
}

static void update_eproj(void) {
    int i;
    player_t* p = &G.pl;
    for (i = 0; i < MAX_EPROJ; i++) {
        eproj_t* e = &G.ep[i];
        if (!e->active) continue;
        if (e->kind == 1) e->vy += 0.12f; /* rock gravity */
        e->x += e->vx; e->y += e->vy;
        if (e->x < -20 || e->x > CANVAS_W + 20 || e->y > CANVAS_H + 20) { e->active = 0; continue; }
        if (solid_at(e->x, e->y)) { fx_add(FX_BURST, (int)e->x, (int)e->y); e->active = 0; continue; }
        if (e->x > p->x && e->x < p->x + p->w && e->y > p->y && e->y < p->y + p->h) {
            hurt_player(e->dmg);
            fx_add(FX_BURST, (int)e->x, (int)e->y);
            e->active = 0;
        }
    }
}

static void update_pickups(void) {
    int i;
    player_t* p = &G.pl;
    for (i = 0; i < MAX_PICKUPS; i++) {
        pickup_t* k = &G.pk[i];
        if (!k->active) continue;
        k->t++;
        if (k->t > 4 || k->y < 11 * TILE - 12) { k->vy += 0.12f; k->y += k->vy; }
        if (k->y > 11 * TILE - 12) { k->y = 11 * TILE - 12; k->vy = 0; }
        if (k->t > 600) { k->active = 0; continue; } /* despawn */
        if (p->x + p->w > k->x - 6 && p->x < k->x + 6 && p->y + p->h > k->y - 8 && p->y < k->y + 8) {
            k->active = 0;
            fx_add(FX_PICK, (int)k->x, (int)k->y);
            sfx_play(2);
            switch (k->kind) {
            case PK_COIN:  { int g = 1 + rand() % 3; p->gold += g; p->score += g; } break;
            case PK_GEM:   p->gems++; p->mp += 15; if (p->mp > p->max_mp) p->mp = p->max_mp; p->score += 15; break;
            case PK_QUIVER: p->arrows += 5; set_msg("+5 ARROWS"); break;
            case PK_POTION: if (p->potions < 3) p->potions++; else p->hp += 20; if (p->hp > p->max_hp) p->hp = p->max_hp; break;
            case PK_METAL: p->mat_metal++; p->score += 5; set_msg("+KIM LOAI"); break;
            case PK_WOOD:  p->mat_wood++; p->score += 5; set_msg("+GO"); break;
            case PK_FUR:   p->mat_fur++; p->score += 5; set_msg("+LONG THU"); break;
            }
        }
    }
}

static void update_fx(void) {
    int i;
    for (i = 0; i < MAX_FX; i++) {
        fx_t* f = &G.fx[i];
        if (!f->active) continue;
        f->t++;
        if ((f->kind == FX_SPARK && f->t > 10) || (f->kind == FX_BURST && f->t > 14) ||
            (f->kind == FX_PICK && f->t > 12) || (f->kind == FX_CRIT && f->t > 30))
            f->active = 0;
    }
}

static void update_spawns(void) {
    if (G.pend_ogre + G.pend_dragon + G.pend_boss > 0) {
        /* gate 5: keep one slot free so dragons are not starved by ogres */
        if (--G.spawn_cd <= 0 && alive_enemies() < 5) {
            if (G.pend_boss) { spawn_enemy(ET_BOSS); G.pend_boss--; }
            else if (G.pend_ogre) { spawn_enemy(ET_OGRE); G.pend_ogre--; }
            else if (G.pend_dragon) { spawn_enemy(ET_DRAGON); G.pend_dragon--; }
            G.spawn_cd = 55;
        }
    } else if (alive_enemies() == 0) {
        /* endless floors: clear -> short pause -> next floor, no forced shop */
        if (G.wave_clear_t == 0) {
            int gb = 5 + G.wave;
            G.wave_clear_t = 1;
            G.pl.score += 10 * G.wave;
            G.pl.arrows += 5;
            G.pl.gold += gb;
            sprintf(G.msg, "TANG CLEAR! +%d GOLD +5 ARROW", gb);
            G.msg_t = 100;
        }
        if (G.wave_clear_t > 0 && ++G.wave_clear_t > 90) {
            G.wave_clear_t = 0;
            wave_start(G.wave + 1);
        }
    }
}

/* ------------------------------------------------------------------ shop */
int shop_cost(int item) {
    switch (item) {
    case 0: return 60 + (G.pl.dmg - 10) / 2 * 30;   /* damage */
    case 1: return 80 + (G.pl.max_hp - 100) / 20 * 40; /* max hp */
    case 2: return 30;                               /* arrows */
    case 3: return 70 + (G.pl.max_mp - 60) / 10 * 35; /* max mp */
    }
    return 0;
}

static void shop_buy(int item) {
    player_t* p = &G.pl;
    int cost = shop_cost(item);
    if (p->gold < cost) { set_msg("NOT ENOUGH GOLD"); return; }
    p->gold -= cost;
    switch (item) {
    case 0: p->dmg += 2; set_msg("DAMAGE UP!"); break;
    case 1: p->max_hp += 20; p->hp = p->max_hp; set_msg("MAX HP UP!"); break;
    case 2: p->arrows += 10; set_msg("+10 ARROWS"); break;
    case 3: p->max_mp += 10; p->mp = p->max_mp; set_msg("MAX MP UP!"); break;
    }
    sfx_play(2);
}

/* ------------------------------------------------------- materials + enhance */
int mat_count(int mat) {
    switch (mat) {
    case MAT_GEM:   return G.pl.gems;
    case MAT_METAL: return G.pl.mat_metal;
    case MAT_WOOD:  return G.pl.mat_wood;
    default:        return G.pl.mat_fur;
    }
}

static void mat_add(int mat, int n) {
    switch (mat) {
    case MAT_GEM:   G.pl.gems += n; break;
    case MAT_METAL: G.pl.mat_metal += n; break;
    case MAT_WOOD:  G.pl.mat_wood += n; break;
    default:        G.pl.mat_fur += n; break;
    }
}

int sell_price(int mat) {
    switch (mat) {
    case MAT_GEM:   return 20;
    case MAT_METAL: return 12;
    case MAT_WOOD:  return 8;
    default:        return 15;
    }
}

void shop_sell(int mat) {
    if (mat_count(mat) <= 0) { set_msg("KHONG DU NGUYEN LIEU"); return; }
    mat_add(mat, -1);
    G.pl.gold += sell_price(mat);
    sfx_play(2);
    set_msg("DA BAN");
}

int enh_lv(int which) {
    return which == 0 ? G.pl.enh_atk : which == 1 ? G.pl.enh_hp : G.pl.enh_crit;
}

int enh_maxed(int which) {
    return which == 2 ? G.pl.enh_crit >= 6 : 0; /* crit caps at 10%+6x5%=40% */
}

int enh_gold(int which) {
    int lv = enh_lv(which);
    return which == 2 ? 40 + lv * 40 : 30 + lv * 30;
}

int enh_need(int which, int mat) {
    if (which == 0) return mat == MAT_METAL ? 2 : mat == MAT_WOOD ? 1 : 0; /* vu khi */
    if (which == 1) return mat == MAT_WOOD ? 2 : mat == MAT_FUR ? 1 : 0;   /* giap */
    return mat == MAT_GEM ? 2 : mat == MAT_FUR ? 1 : 0;                    /* xa thu */
}

int enh_ok(int which) {
    int m;
    if (enh_maxed(which)) return 0;
    if (G.pl.gold < enh_gold(which)) return 0;
    for (m = 0; m < 4; m++) if (mat_count(m) < enh_need(which, m)) return 0;
    return 1;
}

void shop_enhance(int which) {
    player_t* p = &G.pl;
    int m;
    if (!enh_ok(which)) { set_msg("THIEU GOLD / NGUYEN LIEU"); return; }
    p->gold -= enh_gold(which);
    for (m = 0; m < 3; m++) if (enh_need(which, m)) mat_add(m, -enh_need(which, m));
    if (which == 0) { p->enh_atk++; p->dmg += 2; set_msg("VU KHI +2 DMG!"); }
    else if (which == 1) { p->enh_hp++; p->max_hp += 20; p->hp = p->max_hp; set_msg("GIAP +20 HP!"); }
    else { p->enh_crit++; p->crit = 10 + p->enh_crit * 5; set_msg("XA THU +5% CHI MANG!"); }
    sfx_play(2);
}

int player_level(void) {
    return 1 + G.pl.enh_atk + G.pl.enh_hp + G.pl.enh_crit;
}

/* ------------------------------------------------------------------ api */
void game_reset(void) {
    int r, c;
    player_t* p = &G.pl;

    /* keep hi_score, wipe the rest */
    {
        int hi = G.hi_score;
        memset(&G, 0, sizeof(G));
        G.hi_score = hi;
    }

    /* re-parse arena grid saved at init */
    for (r = 0; r < ROWS; r++) memcpy(G.grid[r], g_grid_saved[r], COLS + 1);

    p->w = 24; p->h = 30;
    p->x = 3 * TILE; p->y = 11 * TILE - p->h;
    for (r = 0; r < ROWS; r++) for (c = 0; c < COLS; c++) {
        if (G.grid[r][c] == 'P') { p->x = c * TILE; p->y = r * TILE + TILE - p->h; }
    }
    p->dir = 1;
    p->max_hp = 100; p->hp = 100;
    p->max_mp = 60; p->mp = 60;
    p->arrows = 30; p->gold = 0; p->potions = 1;
    p->dmg = 10; p->level = 1;
    p->crit = 10; /* base crit chance 10% */
    G.state = ST_TITLE;
}

void game_init(void) {
    VMINT size = 0;
    VMUINT8* res;
    int r, c;

    memset(&G, 0, sizeof(G));
    res_init();
    res_prepare_storage();
    G.hi_score = save_read();

    /* load arena map from packed resource: one grid row per text line */
    for (r = 0; r < ROWS; r++) {
        for (c = 0; c < COLS; c++) G.grid[r][c] = '.';
        G.grid[r][COLS] = 0;
    }
    res = vm_load_resource("arena1.txt", &size);
    if (res) {
        int ri = 0;
        for (r = 0; r < ROWS && ri < size; r++) {
            for (c = 0; c < COLS && ri < size; c++) {
                char ch = res[ri++];
                if (ch == '\r' || ch == '\n') break;
                G.grid[r][c] = (ch == ' ') ? '.' : ch;
            }
            while (ri < size && res[ri] != '\n') ri++;
            if (ri < size) ri++; /* line break */
        }
        vm_free(res);
    } else {
        for (r = 0; r < ROWS; r++)
            for (c = 0; c < COLS; c++)
                G.grid[r][c] = (r >= 11) ? '#' : '.';
    }
    memcpy(g_grid_saved, G.grid, sizeof(g_grid_saved));
    game_reset();
    G.state = ST_TITLE;
}

void game_shutdown(void) {
    if (G.pl.score > G.hi_score) { G.hi_score = G.pl.score; save_write(G.hi_score); }
    res_free();
}

void game_key(int keycode) {
    player_t* p = &G.pl;
    switch (G.state) {
    case ST_TITLE:
        if (keycode == VM_KEY_NUM5 || keycode == VM_KEY_OK) { wave_start(1); }
        break;
    case ST_PLAY:
        switch (keycode) {
        case VM_KEY_NUM5: player_shoot(0); break;
        case VM_KEY_NUM7: use_power_shot(); break;
        case VM_KEY_NUM9: use_multi_shot(); break;
        case VM_KEY_NUM0: use_dash(); break;
        case VM_KEY_STAR: use_potion(); break;
        case VM_KEY_POUND: /* open the shop by hand, mid-floor allowed */
            G.state = ST_SHOP; G.shop_tab = 0;
            break;
        case VM_KEY_LEFT_SOFTKEY: G.state = ST_PAUSE; break;
#ifdef TEST_CHEAT
        case VM_KEY_NUM1: /* test build only: full restore + resources */
            p->hp = p->max_hp; p->mp = p->max_mp;
            p->arrows += 30; p->gold += 200; p->potions += 5;
            p->gems += 3; p->mat_metal += 3; p->mat_wood += 3; p->mat_fur += 3;
            sprintf(G.msg, "CHEAT +HP +GOLD +MAT");
            G.msg_t = 90;
            break;
        case VM_KEY_NUM3: { /* test build only: clear wave instantly */
            int i;
            for (i = 0; i < MAX_ENEMIES; i++)
                if (G.en[i].active) hurt_enemy(&G.en[i], 9999);
            G.pend_ogre = G.pend_dragon = G.pend_boss = 0;
            break;
        }
#endif
        }
        break;
    case ST_PAUSE:
        if (keycode == VM_KEY_NUM5 || keycode == VM_KEY_OK || keycode == VM_KEY_LEFT_SOFTKEY) G.state = ST_PLAY;
        else if (keycode == VM_KEY_RIGHT_SOFTKEY) {
            save_write(p->score > G.hi_score ? p->score : G.hi_score);
            vm_exit_app();
        }
        break;
    case ST_SHOP:
        /* 5/OK/# close and resume the same floor; 6/7/8 switch tabs */
        if (keycode == VM_KEY_NUM5 || keycode == VM_KEY_OK ||
            keycode == VM_KEY_POUND || keycode == VM_KEY_RIGHT_SOFTKEY)
            G.state = ST_PLAY;
        else if (keycode == VM_KEY_NUM6) G.shop_tab = 0;
        else if (keycode == VM_KEY_NUM7) G.shop_tab = 1;
        else if (keycode == VM_KEY_NUM8) G.shop_tab = 2;
        else if (keycode >= VM_KEY_NUM1 && keycode <= VM_KEY_NUM4) {
            int idx = keycode - VM_KEY_NUM1;
            if (G.shop_tab == 0) shop_buy(idx);
            else if (G.shop_tab == 1) { if (idx < 3) shop_enhance(idx); }
            else shop_sell(idx);
        }
        break;
    case ST_OVER:
        if (keycode == VM_KEY_NUM5 || keycode == VM_KEY_OK) {
            game_reset();
            wave_start(1);
        } else if (keycode == VM_KEY_RIGHT_SOFTKEY) vm_exit_app();
        break;
    }
}

void game_pen(int x, int y) {
    /* bottom skill buttons are tappable */
    if (G.state != ST_PLAY) { game_key(VM_KEY_NUM5); return; }
    if (y > CANVAS_H - 36) {
        if (x > 40 && x < 90) game_key(VM_KEY_NUM7);
        else if (x > 95 && x < 145) game_key(VM_KEY_NUM9);
        else if (x > 150 && x < 200) game_key(VM_KEY_NUM0);
    }
}

void game_tick(void) {
    G.tick++;
    G.blink++;
    if (G.msg_t > 0) G.msg_t--;
    if (G.shake_t > 0) G.shake_t--;

    if (G.state == ST_PLAY) {
        update_player();
        update_enemies();
        update_arrows();
        update_eproj();
        update_pickups();
        update_fx();
        update_spawns();
    } else if (G.state == ST_SHOP || G.state == ST_OVER || G.state == ST_TITLE) {
        update_fx();
    }

    game_draw();
}
