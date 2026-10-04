/* draw.c - all rendering: parallax backdrop, arena, entities, HUD, screens */
#include "vmgraph.h"
#include <stdio.h>
#include <string.h>

#include "game.h"
#include "gfx.h"
#include "res.h"

static int arch_frame(int anim) {
    switch (anim) {
    case 1: return SPR_ARCH_B;
    case 2: return SPR_ARCH_D;
    case 3: return SPR_ARCH_C;  /* climb */
    case 4: return SPR_ARCH_C;  /* jump */
    case 5: return SPR_ARCH_SHOOT;
    case 6: return SPR_ARCH_HIT;
    case 7: return SPR_ARCH_A;
    default: return SPR_ARCH_B;
    }
}

static int ogre_frame(enemy_t* e) {
    if (e->hurt_t > 0) return e->type == ET_BOSS ? SPR_BOSS_OGRE : SPR_OGRE_HIT;
    if (e->state == 1) return SPR_OGRE_C;
    return (e->anim_t / 10) % 2 ? SPR_OGRE_B : SPR_OGRE_A;
}

static int dragon_frame(enemy_t* e) {
    int f = (e->anim_t / 6) % 4;
    switch (f) { case 0: return SPR_DRAGON_A; case 1: return SPR_DRAGON_B; case 2: return SPR_DRAGON_C; default: return SPR_DRAGON_B; }
}

/* material icons drawn procedurally: no sprites exist for them */
static void mat_icon(int x, int y, int mat) {
    switch (mat) {
    case MAT_METAL: /* steel ingot */
        gfx_fill(x, y, 9, 7, RGB(150, 155, 165));
        gfx_fill(x + 1, y + 1, 7, 2, RGB(205, 210, 220));
        gfx_frame(x, y, 9, 7, RGB(55, 55, 65));
        break;
    case MAT_WOOD: /* planks */
        gfx_fill(x, y, 9, 7, RGB(145, 95, 48));
        gfx_fill(x, y + 2, 9, 1, RGB(100, 62, 28));
        gfx_fill(x, y + 4, 9, 1, RGB(100, 62, 28));
        gfx_frame(x, y, 9, 7, RGB(66, 42, 18));
        break;
    default: /* beast fur pelt */
        gfx_fill(x + 1, y, 7, 7, RGB(192, 160, 108));
        gfx_fill(x, y + 1, 9, 5, RGB(176, 142, 92));
        gfx_fill(x + 2, y + 2, 2, 2, RGB(230, 205, 160));
        gfx_frame(x, y, 9, 7, RGB(105, 80, 45));
        break;
    }
}

static const char* mat_name(int mat) {
    switch (mat) {
    case MAT_GEM:   return "NGOC";
    case MAT_METAL: return "KIM LOAI";
    case MAT_WOOD:  return "GO";
    default:        return "LONG THU";
    }
}

static void draw_backdrop(void) {
    int y, x, r, c;
    /* sky + far spires + mid clouds */
    gfx_fill(0, 0, CANVAS_W, CANVAS_H, RGB(14, 16, 34));
    gfx_blit_op(SPR_BG_MID, 0, 30);
    gfx_blit_op(SPR_BG_FAR, 0, 58);
    /* ruined architecture strip fills the lower backdrop, tiled */
    for (y = 100; y < CANVAS_H; y += 46) gfx_blit_op(SPR_BG_NEAR, 0, y);
    /* dark overlay so platforms read clearly */
    for (y = 100; y < CANVAS_H; y += 2) gfx_fill(0, y, CANVAS_W, 1, RGB(10, 10, 22));
    /* brick texture behind cells marked 'W' (wall) */
    for (r = 0; r < ROWS; r++)
        for (c = 0; c < COLS; c++)
            if (G.grid[r][c] == 'W')
                gfx_blit_op(SPR_TEX_BRICK, c * TILE, r * TILE);
}

static void draw_decor(void) {
    int r, c;
    int tf = (G.tick / 8) % 4;
    for (r = 0; r < ROWS; r++)
        for (c = 0; c < COLS; c++) {
            char t = G.grid[r][c];
            int x = c * TILE, y = r * TILE;
            switch (t) {
            case 'w': gfx_blit(SPR_WINDOW, x + 1, y - 6, 0); break;
            case 's': gfx_blit(SPR_SHOPDOOR, x - 8, y - 12, 0); break;
            case 'a': gfx_blit(SPR_ARCHWAY, x - 12, y - 10, 0); break;
            case 'r': gfx_blit(SPR_RUBBLE, x, y + 9, 0); break;
            case 'n': gfx_blit(SPR_BANNER, x + 5, y, 0); break;
            case 'i': gfx_blit(SPR_PILLAR, x + 6, y - 6, 0); break;
            case 'b': gfx_blit(SPR_BARREL, x + 4, y + 7, 0); break;
            case 'k': gfx_blit(SPR_CRATE, x + 4, y + 7, 0); break;
            case 'h': gfx_blit(SPR_CHAIN1, x + 10, y, 0); break;
            case 'T': gfx_blit(SPR_TORCH1 + tf, x + 6, y - 4, 0); break;
            }
        }
}

static void draw_arena(void) {
    int r, c;
    for (r = 0; r < ROWS; r++) {
        for (c = 0; c < COLS; c++) {
            char t = G.grid[r][c];
            int x = c * TILE, y = r * TILE;
            if (t == '#') {
                int v = (r * 7 + c * 13) % 4;
                gfx_blit_bright(SPR_GROUND1 + v, x, y, 0, 3);
            } else if (t == '=') {
                gfx_blit_bright(SPR_GH1 + (c % 3), x, y + 2, 0, 2);
            } else if (t == 'B') { /* solid brick block */
                gfx_blit(SPR_BLOCK, x, y, 0);
            } else if (t == 'H') {
                /* one stretched sprite per horizontal run */
                if (c == 0 || G.grid[r][c - 1] != 'H') {
                    int n = 1;
                    while (c + n < COLS && G.grid[r][c + n] == 'H') n++;
                    gfx_blit_scaled(SPR_SPIKES, x, y + 2, n * TILE, 22, 0);
                }
            } else if (t == 'L') {
                /* ladder drawn per run in draw_ladders */
            }
        }
    }
    /* ladders: one stretched sprite per vertical run */
    {
        int c2, r2;
        for (c2 = 0; c2 < COLS; c2++) {
            int run_start = -1;
            for (r2 = 0; r2 <= ROWS; r2++) {
                int is_l = r2 < ROWS && G.grid[r2][c2] == 'L';
                if (is_l && run_start < 0) run_start = r2;
                if (!is_l && run_start >= 0) {
                    gfx_blit_scaled_bright(SPR_LADDER, c2 * TILE + 3, run_start * TILE, 18, (r2 - run_start) * TILE, 0, 4);
                    run_start = -1;
                }
            }
        }
    }
}

static void draw_entities(void) {
    int i;
    /* pickups */
    for (i = 0; i < MAX_PICKUPS; i++) {
        pickup_t* k = &G.pk[i];
        if (!k->active) continue;
        switch (k->kind) {
        case PK_COIN:   gfx_blit(SPR_COIN, (int)k->x - 5, (int)k->y - 6, 0); break;
        case PK_GEM:    gfx_blit(SPR_GEM, (int)k->x - 7, (int)k->y - 10, 0); break;
        case PK_QUIVER: gfx_blit(SPR_IC_QUIVER, (int)k->x - 6, (int)k->y - 8, 0); break;
        case PK_POTION: gfx_blit(SPR_IC_HPOTION, (int)k->x - 5, (int)k->y - 8, 0); break;
        case PK_METAL:  mat_icon((int)k->x - 4, (int)k->y - 3, MAT_METAL); break;
        case PK_WOOD:   mat_icon((int)k->x - 4, (int)k->y - 3, MAT_WOOD); break;
        case PK_FUR:    mat_icon((int)k->x - 4, (int)k->y - 3, MAT_FUR); break;
        }
    }
    /* enemies */
    for (i = 0; i < MAX_ENEMIES; i++) {
        enemy_t* e = &G.en[i];
        int img, flip;
        if (!e->active) continue;
        if (e->type == ET_DRAGON) { img = dragon_frame(e); flip = e->vx > 0; }
        else {
            img = ogre_frame(e);
            flip = e->dir > 0;
        }
        if (e->hurt_t > 0 && (e->hurt_t & 2)) { /* flicker when hurt */
            ;
        } else if (e->type == ET_DRAGON) {
            gfx_blit_bright(img, (int)e->x, (int)e->y, flip, 4); /* dark sprite needs a lift vs night sky */
        } else {
            gfx_blit(img, (int)e->x, (int)e->y, flip);
        }
        /* small hp bar over damaged enemies */
        if (e->hp < e->max_hp) {
            int bw = e->w;
            gfx_fill((int)e->x, (int)e->y - 5, bw, 3, C_DKRED);
            gfx_fill((int)e->x, (int)e->y - 5, bw * e->hp / e->max_hp, 3, C_RED);
        }
    }
    /* player */
    if (G.state == ST_PLAY || G.state == ST_PAUSE) {
        player_t* p = &G.pl;
        if (!(p->invuln > 0 && (G.tick & 2))) {
            gfx_blit_bright(arch_frame(p->anim), (int)p->x, (int)p->y, p->dir < 0, 5);
        }
    }
    /* arrows */
    for (i = 0; i < MAX_ARROWS; i++) {
        arrow_t* a = &G.ar[i];
        int img, flip;
        if (!a->active) continue;
        img = a->power ? SPR_ARROW3 : ((G.tick / 4) % 2 ? SPR_ARROW1 : SPR_ARROW2);
        flip = a->vx < 0;
        if (a->vy > 0.5f) { /* angled down */
            gfx_blit_scaled(img, (int)a->x - 9, (int)a->y - 2, 18, 5, flip);
        } else if (a->vy < -0.5f) {
            gfx_blit_scaled(img, (int)a->x - 9, (int)a->y - 4, 18, 5, flip);
        } else {
            gfx_blit(img, (int)a->x - 9, (int)a->y - 4, flip);
        }
    }
    /* enemy projectiles */
    for (i = 0; i < MAX_EPROJ; i++) {
        eproj_t* e = &G.ep[i];
        if (!e->active) continue;
        if (e->kind == 0) { /* fireball */
            VMUINT16 c = (G.tick & 4) ? C_ORANGE : RGB(255, 210, 60);
            gfx_fill((int)e->x - 3, (int)e->y - 3, 6, 6, c);
            gfx_fill((int)e->x - 1, (int)e->y - 1, 2, 2, C_WHITE);
        } else { /* rock */
            gfx_fill((int)e->x - 4, (int)e->y - 4, 8, 8, RGB(110, 100, 95));
            gfx_fill((int)e->x - 2, (int)e->y - 3, 3, 2, RGB(160, 150, 140));
        }
    }
    /* fx */
    for (i = 0; i < MAX_FX; i++) {
        fx_t* f = &G.fx[i];
        if (!f->active) continue;
        if (f->kind == FX_SPARK) {
            if (f->t < 6) gfx_blit(SPR_SPARK_S, f->x - 6, f->y - 5, 0);
        } else if (f->kind == FX_BURST) {
            if (f->t < 10) gfx_blit(SPR_SPARK_B, f->x - 10, f->y - 9, 0);
            else gfx_blit(SPR_SPARK_S, f->x - 6, f->y - 5, 0);
        } else { /* FX_PICK: rising sparkle */
            gfx_blit(SPR_SPARK_S, f->x - 6, f->y - 5 - f->t, 0);
        }
        if (f->kind == FX_CRIT && f->t < 26)
            gfx_text_c(f->x, f->y - f->t / 2, "CHI MANG!", (f->t & 8) ? C_GOLD : C_WHITE);
    }
}

static void draw_hud(void) {
    player_t* p = &G.pl;
    char buf[32];

    /* portrait + level (grows with enhancements) */
    gfx_blit(SPR_PORTRAIT, 2, 2, 0);
    sprintf(buf, "LV.%d", player_level());
    gfx_text_c(17, 34, buf, C_GOLD);

    /* hp / mp bars */
    gfx_bar(36, 4, 100, 9, p->hp * 100 / p->max_hp, C_RED, C_DKRED);
    sprintf(buf, "%d/%d", p->hp, p->max_hp);
    gfx_text(88, 5, buf, C_WHITE);
    gfx_bar(36, 16, 100, 8, p->mp * 100 / p->max_mp, C_BLUE, C_DKBLUE);
    sprintf(buf, "%d/%d", p->mp, p->max_mp);
    gfx_text(88, 16, buf, C_WHITE);

    /* right side resources */
    gfx_blit(SPR_IC_GOLD, 168, 4, 0);
    sprintf(buf, "%d", p->gold);
    gfx_text(184, 6, buf, C_GOLD);
    gfx_blit(SPR_IC_GEM, 168, 20, 0);
    sprintf(buf, "%d", p->gems);
    gfx_text(184, 21, buf, C_PURPLE);
    gfx_blit(SPR_IC_QUIVER, 168, 36, 0);
    sprintf(buf, "%d", p->arrows);
    gfx_text(184, 38, buf, C_WHITE);
    gfx_blit(SPR_IC_HPOTION, 206, 34, 0);
    sprintf(buf, "x%d", p->potions);
    gfx_text(220, 38, buf, C_WHITE);

    /* shared bag: crafting materials (ngoc sits in the gem slot above) */
    mat_icon(163, 54, MAT_METAL);
    sprintf(buf, "%d", p->mat_metal);
    gfx_text(173, 53, buf, C_WHITE);
    mat_icon(188, 54, MAT_WOOD);
    sprintf(buf, "%d", p->mat_wood);
    gfx_text(198, 53, buf, C_WHITE);
    mat_icon(213, 54, MAT_FUR);
    sprintf(buf, "%d", p->mat_fur);
    gfx_text(223, 53, buf, C_WHITE);

    /* floor */
    sprintf(buf, "TANG %d", G.wave > 0 ? G.wave : 1);
    gfx_text_c(CANVAS_W / 2, 4, buf, C_WHITE);

    /* boss bar */
    {
        int i;
        for (i = 0; i < MAX_ENEMIES; i++) {
            enemy_t* e = &G.en[i];
            if (e->active && e->type == ET_BOSS) {
                gfx_text_c(CANVAS_W / 2, 30, "BOSS", C_RED);
                gfx_bar(60, 40, 120, 7, e->hp * 100 / e->max_hp, C_RED, C_DKRED);
            }
        }
    }

    /* skill buttons with cooldown overlay */
    {
        struct { int btn, badge, cd, max, key; } b[3] = {
            { SPR_BTN_POWER, SPR_BADGE_POWER, p->cd_power, 160, '7' },
            { SPR_BTN_MULTI, SPR_BADGE_MULTI, p->cd_multi, 200, '9' },
            { SPR_BTN_DASH,  SPR_BADGE_DASH,  p->cd_dash,  120, '0' },
        };
        int k, bx = 44;
        for (k = 0; k < 3; k++) {
            int x = bx + k * 52, y = CANVAS_H - 34;
            gfx_blit(b[k].btn, x, y, 0);
            gfx_blit_scaled(b[k].badge, x + 4, y + 4, 16, 16, 0);
            if (b[k].cd > 0) {
                /* darken remaining cooldown portion (top-down) */
                int hh = 22 * b[k].cd / b[k].max;
                gfx_fill(x + 2, y + 2, 20, hh, RGB(20, 20, 30));
            }
            {
                char kb[2] = { b[k].key, 0 };
                gfx_text_c(x + 12, y + 24, kb, C_GOLD);
            }
        }
    }

    /* center message */
    if (G.msg_t > 0 && (G.msg_t & 16))
        gfx_text_c(CANVAS_W / 2, 66, G.msg, C_GOLD);
}

static void draw_title(void) {
    char buf[48];
    gfx_blit_op(SPR_SPLASH, 0, 0);
    if (G.blink & 16) gfx_text_c(CANVAS_W / 2, 262, "BAM 5 DE CHOI", C_WHITE);
    sprintf(buf, "HIGH SCORE %d", G.hi_score);
    gfx_text_c(CANVAS_W / 2, 280, buf, C_GOLD);
    gfx_text_c(CANVAS_W / 2, 296, "4-6:DI 2:NHAY 5:BAN *:HP", RGB(190, 190, 210));
    gfx_text_c(CANVAS_W / 2, 308, "7:MANH 9:X3 0:LUA # SHOP", RGB(190, 190, 210));
}

static void draw_shop(void) {
    player_t* p = &G.pl;
    char buf[64];
    int i;
    gfx_fill(0, 0, CANVAS_W, CANVAS_H, RGB(10, 10, 20));
    gfx_blit_op(SPR_BG_NEAR, 0, 130);
    gfx_text_c(CANVAS_W / 2, 8, "== CUA HANG ==", C_GOLD);
    sprintf(buf, "GOLD:%d   TANG %d", p->gold, G.wave > 0 ? G.wave : 1);
    gfx_text_c(CANVAS_W / 2, 26, buf, C_WHITE);

    /* tab bar: 6 mua / 7 cuong hoa / 8 ban */
    {
        static const char* tabs[3] = { "MUA", "CUONG HOA", "BAN" };
        for (i = 0; i < 3; i++) {
            int cx = 48 + i * 72;
            if (G.shop_tab == i) {
                gfx_fill(cx - 34, 42, 68, 15, RGB(46, 38, 18));
                gfx_text_c(cx, 44, tabs[i], C_GOLD);
            } else {
                gfx_text_c(cx, 44, tabs[i], C_GREY);
            }
        }
    }

    if (G.shop_tab == 0) { /* gold shop */
        static const char* items[4] = { "DAMAGE+2", "MAX HP+20", "ARROWS+10", "MAX MP+10" };
        for (i = 0; i < 4; i++) {
            int cost = shop_cost(i);
            sprintf(buf, "%d. %-11s %4d G", i + 1, items[i], cost);
            gfx_text(24, 70 + i * 20, buf, p->gold >= cost ? C_WHITE : C_GREY);
        }
        sprintf(buf, "HP %d/%d  ARROW %d  DMG %d", p->hp, p->max_hp, p->arrows, p->dmg);
        gfx_text(24, 154, buf, RGB(190, 190, 210));
        sprintf(buf, "CHI MANG %d%%", p->crit);
        gfx_text(24, 170, buf, RGB(190, 190, 210));
    } else if (G.shop_tab == 1) { /* enhancement recipes */
        static const char* ename[3] = { "VU KHI +2DMG", "GIAP +20HP", "XA THU +5%CM" };
        for (i = 0; i < 3; i++) {
            int y = 66 + i * 32;
            int ok = enh_ok(i), maxed = enh_maxed(i);
            sprintf(buf, "%d. %-13s Lv%d", i + 1, ename[i], enh_lv(i));
            gfx_text(20, y, buf, maxed ? C_GOLD : ok ? C_WHITE : C_GREY);
            if (maxed) {
                gfx_text(40, y + 13, "TOI DA - MAX", C_GOLD);
            } else {
                sprintf(buf, "%dKL %dGO %dLT %dNG   %dG",
                        enh_need(i, MAT_METAL), enh_need(i, MAT_WOOD),
                        enh_need(i, MAT_FUR), enh_need(i, MAT_GEM), enh_gold(i));
                gfx_text(40, y + 13, buf, ok ? C_ORANGE : C_DKGREY);
            }
        }
        sprintf(buf, "DMG %d  CM %d%%  MAXHP %d", p->dmg, p->crit, p->max_hp);
        gfx_text(20, 168, buf, RGB(190, 190, 210));
    } else { /* sell materials */
        for (i = 0; i < 4; i++) {
            sprintf(buf, "%d. %-9s x%-3d %d G/cai", i + 1, mat_name(i),
                    mat_count(i), sell_price(i));
            gfx_text(20, 70 + i * 22, buf, mat_count(i) > 0 ? C_WHITE : C_GREY);
        }
    }

    /* shared bag strip */
    gfx_fill(8, 196, CANVAS_W - 16, 40, RGB(18, 18, 30));
    gfx_frame(8, 196, CANVAS_W - 16, 40, C_DKGREY);
    gfx_blit(SPR_IC_GEM, 14, 201, 0);
    sprintf(buf, "%d", mat_count(MAT_GEM));
    gfx_text(27, 203, buf, C_PURPLE);
    mat_icon(58, 204, MAT_METAL);
    sprintf(buf, "%d", mat_count(MAT_METAL));
    gfx_text(69, 203, buf, C_WHITE);
    mat_icon(96, 204, MAT_WOOD);
    sprintf(buf, "%d", mat_count(MAT_WOOD));
    gfx_text(107, 203, buf, C_WHITE);
    mat_icon(134, 204, MAT_FUR);
    sprintf(buf, "%d", mat_count(MAT_FUR));
    gfx_text(145, 203, buf, C_WHITE);
    gfx_text(150, 218, "TUI CHUNG", C_GREY);

    if (G.blink & 16) gfx_text_c(CANVAS_W / 2, 254, "BAM 5: DONG, CHOITIEP", C_GOLD);
    gfx_text_c(CANVAS_W / 2, 274, "6:MUA  7:CUONG HOA  8:BAN", RGB(190, 190, 210));
    gfx_text_c(CANVAS_W / 2, 290, "1-4: CHON", RGB(150, 150, 170));
}

static void draw_pause(void) {
    gfx_fill(70, 112, 100, 96, RGB(20, 20, 34));
    gfx_frame(70, 112, 100, 96, C_GOLD);
    gfx_text_c(CANVAS_W / 2, 122, "PAUSE", C_GOLD);
    gfx_text_c(CANVAS_W / 2, 142, "5: TIEP TUC", C_WHITE);
    gfx_text_c(CANVAS_W / 2, 158, "#: CUA HANG", RGB(190, 190, 210));
    gfx_text_c(CANVAS_W / 2, 176, "RSK: THOAT", C_GREY);
}

static void draw_over(void) {
    char buf[48];
    gfx_fill(0, 90, CANVAS_W, 130, RGB(12, 8, 10));
    gfx_frame(0, 90, CANVAS_W, 130, C_DKRED);
    gfx_text_c(CANVAS_W / 2, 104, "GAME OVER", C_RED);
    sprintf(buf, "SCORE: %d", G.pl.score);
    gfx_text_c(CANVAS_W / 2, 130, buf, C_WHITE);
    sprintf(buf, "TANG: %d   GOLD: %d", G.wave > 0 ? G.wave : 1, G.pl.gold);
    gfx_text_c(CANVAS_W / 2, 148, buf, C_WHITE);
    sprintf(buf, "HIGH SCORE: %d", G.hi_score);
    gfx_text_c(CANVAS_W / 2, 166, buf, C_GOLD);
    if (G.blink & 16) gfx_text_c(CANVAS_W / 2, 194, "BAM 5: CHOI LAI", C_WHITE);
}

void game_draw(void) {
    int sw = vm_graphic_get_screen_width(), sh = vm_graphic_get_screen_height();
    int bx = (sw - CANVAS_W) / 2, by = (sh - CANVAS_H) / 2;
    if (bx < 0) bx = 0;
    if (by < 0) by = 0;
    gfx_set_fb(g_buf, sw, sh);
    gfx_clear(RGB(8, 8, 14));

    g_ox = bx; g_oy = by;
    if (G.shake_t > 0) g_ox += (G.shake_t & 1) ? 2 : -2;

    switch (G.state) {
    case ST_TITLE:
        draw_title();
        break;
    default:
        draw_backdrop();
        draw_decor();
        draw_arena();
        draw_entities();
        draw_hud();
        if (G.state == ST_SHOP) draw_shop();
        if (G.state == ST_PAUSE) draw_pause();
        if (G.state == ST_OVER) draw_over();
        break;
    }
#ifdef TEST_CHEAT
    {
        char db[96];
        sprintf(db, "x%d y%d vy%d og%d cl%d t%c", (int)G.pl.x, (int)G.pl.y,
                (int)(G.pl.vy * 100), G.pl.on_ground, G.pl.climbing,
                G.grid[(int)((G.pl.y + G.pl.h + 1) / TILE)][(int)(G.pl.x / TILE)]);
        gfx_text(2, 40, db, RGB(255, 255, 0));
    }
#endif
    g_ox = 0; g_oy = 0;
    gfx_present();
}
