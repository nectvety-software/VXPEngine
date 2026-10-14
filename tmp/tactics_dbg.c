/* Reads the battle state the screen harness can only show as 16-px sprites, so
 * the auto-played stalemate can be diagnosed from text instead of by squinting
 * at contact sheets: every unit's class, tile, HP and done flag, plus the phase
 * and round. main.c is included rather than linked so its statics are visible.
 * Build and run with tmp/make_tactics_dbg.sh. */
#include "main.c"
#include <stdio.h>

void advance(int ms);
extern int g_exited;

static const char* const PH_NAME[BP_RESULT + 1] = {
    "SELECT", "RANGE", "WALK", "ACTION", "TARGET", "CUTIN", "HIT", "ENEMY",
    "RESULT" };

static void dump_state(const char* tag) {
    int i;
    printf("%-12s R%-2d ph=%-8s act=%d res=%d cur=(%d,%d)\n", tag, g_round,
           PH_NAME[g_phase], g_active_side, g_result, g_cur_x, g_cur_y);
    for (i = 0; i < g_nu; ++i) {
        const Unit* u = &g_u[i];
        if (!u->alive) {
            printf("               %-9s side%d DEAD\n", u->name, u->side);
            continue;
        }
        printf("               %-9s side%d %-6s (%2d,%2d) hp%3d/%3d %s r%d-%d\n",
               u->name, u->side, CLS_TAG[u->cls], u->x, u->y, u->hp,
               hp_max(u), u->done ? "done" : "    ",
               CLS[u->cls].rmin, CLS[u->cls].rmax);
    }
    fflush(stdout);
}

static void tap(int key) {
    handle_keyevt(VM_KEY_EVENT_DOWN, key);
    handle_keyevt(VM_KEY_EVENT_UP, key);
}

int main(void) {
    int i;
    handle_sysevt(VM_MSG_CREATE, 0);
    tap(VM_KEY_OK);                    /* skip the splash */
    advance(200);
    tap(VM_KEY_OK);                    /* row 0 of the menu is BEGIN BATTLE */
    advance(200);
    dump_state("round1");

    /* Round 1: Caedric walks up the road column and holds the bridge approach. */
    tap(VM_KEY_OK);                    /* select CAEDRIC under the cursor */
    for (i = 0; i < 5; ++i) tap(VM_KEY_NUM2);
    tap(VM_KEY_OK);                    /* confirm the walk */
    advance(1200);
    tap(VM_KEY_OK);                    /* ATTACK, nothing in reach -> wait */
    advance(120);
    tap(VM_KEY_NUM9);                  /* end the player phase */
    dump_state("r1_end");
    advance(20000);
    dump_state("round2");

    for (i = 0; i < 18; ++i) {
        char tag[16];
        tap(VM_KEY_NUM9);
        advance(4200);
        if (i % 3) continue;
        sprintf(tag, "auto%d", i + 1);
        dump_state(tag);
    }
    printf("exited=%d\n", g_exited);
    return 0;
}
