/* Drives the real TacticsVanguard2D main.c on the host and dumps every screen:
 * splash timings, the four menu rows, the briefing page, move range, path
 * arrow, walk animation, parchment action card, attack targeting, the cut-in
 * band, damage pops, and an auto-played tail that should reach the result
 * screen. Build and run with tmp/make_tactics_shots.sh.
 *
 * The run is deterministic: the map, roster and RNG seed are fixed and the
 * harness is the only input, so the same shot list comes back every time. */
#include "vmsys.h"
#include "vmio.h"
#include <stdio.h>

void dump_frame(const char* tag);
void advance(int ms);
extern int g_exited;

void handle_sysevt(VMINT message, VMINT param);
void handle_keyevt(VMINT event, VMINT keycode);
void handle_penevt(VMINT event, VMINT x, VMINT y);

static void tap(int key) {
    handle_keyevt(VM_KEY_EVENT_DOWN, key);
    handle_keyevt(VM_KEY_EVENT_UP, key);
}
static void step(const char* tag, int ms) {
    advance(ms);
    dump_frame(tag);
}
static void key(const char* tag, int k) {
    tap(k);
    advance(40);
    dump_frame(tag);
}
/* One tap on a tile aims the cursor; the second tap on the same tile confirms. */
static void pen(const char* tag, int x, int y, int twice) {
    handle_penevt(VM_PEN_EVENT_TAP, x, y);
    if (twice) handle_penevt(VM_PEN_EVENT_TAP, x, y);
    advance(40);
    dump_frame(tag);
}

#define TILE_X(i) ((i) * 16 + 8)
#define TILE_Y(i) (24 + (i) * 16 + 8)

/* Stay put and attack, without moving the unit: a pen tap on the unit's own
 * tile drops the range field straight into the action card (BP_RANGE has an
 * explicit same-tile branch), OK picks ATTACK, then the aim cursor is walked
 * over all four neighbours. A tap on the attacker's own tile in BP_TARGET only
 * resets the cursor and an OK on an empty tile is a no-op, so the whole sweep
 * is safe to run blind -- which tile actually connected is read off the sheet. */
static void stay_and_attack(int n, int tx, int ty) {
    static const int dirs[4] = { VM_KEY_NUM2, VM_KEY_NUM4, VM_KEY_NUM6, VM_KEY_NUM8 };
    char tag[32];
    int i;
    sprintf(tag, "atk%02d_sel", n);
    pen(tag, TILE_X(tx), TILE_Y(ty), 0);
    sprintf(tag, "atk%02d_card", n);
    pen(tag, TILE_X(tx), TILE_Y(ty), 1);
    sprintf(tag, "atk%02d_go", n);
    key(tag, VM_KEY_OK);
    for (i = 0; i < 4; ++i) {
        handle_penevt(VM_PEN_EVENT_TAP, TILE_X(tx), TILE_Y(ty));
        tap(dirs[i]);
        advance(40);
        tap(VM_KEY_OK);
        advance(130);
        sprintf(tag, "atk%02d_dir%d", n, i);
        dump_frame(tag);
    }
    for (i = 0; i < 3; ++i) {
        advance(130);
        sprintf(tag, "atk%02d_band%d", n, i);
        dump_frame(tag);
    }
    for (i = 0; i < 3; ++i) {
        advance(i == 2 ? 260 : 130);
        sprintf(tag, "atk%02d_hit%d", n, i);
        dump_frame(tag);
    }
    advance(700);
    sprintf(tag, "atk%02d_after", n);
    dump_frame(tag);
}

int main(void) {
    int i;
    handle_sysevt(VM_MSG_CREATE, 0);
    dump_frame("splash_t00");           /* nothing drawn yet: no bar, no prompt */
    step("splash_t14", 460);
    step("splash_t32", 600);            /* bar appears at t=31, 5 px wide */
    step("splash_t48", 530);            /* prompt blink, on-state */
    step("splash_t54", 200);            /* n=120 here before the bar was clamped */
    step("splash_t64", 530);
    step("splash_last", 470);           /* still the splash: t is under 78 */
    step("menu_top", 400);              /* the card auto-advances at t=78 */

    key("menu_side_row", VM_KEY_NUM8);
    key("menu_crimson", VM_KEY_NUM6);   /* crest + every accent must flip */
    key("menu_azure", VM_KEY_NUM4);
    key("menu_help_row", VM_KEY_NUM8);
    key("help", VM_KEY_OK);
    key("menu_from_help", VM_KEY_OK);
    tap(VM_KEY_NUM2); tap(VM_KEY_NUM2);
    key("battle_start", VM_KEY_OK);     /* begin_battle: 13 units on the field */

    /* Cursor starts on CAEDRIC (7,14): select, then walk the road column north. */
    key("range_caedric", VM_KEY_OK);
    key("path_1", VM_KEY_NUM2);
    key("path_3", VM_KEY_NUM2); tap(VM_KEY_NUM2);
    key("path_5", VM_KEY_NUM2); tap(VM_KEY_NUM2);
    key("walk_start", VM_KEY_OK);       /* confirm: the walk begins */
    step("walk_mid", 150);              /* mid-path, unit off its tile */
    step("card_rows", 900);             /* BP_ACTION: parchment card opens */
    key("card_row_wait", VM_KEY_NUM8);
    key("attack_no_target", VM_KEY_NUM2); tap(VM_KEY_OK);

    /* Enemy phase: the AI walks the bridges and attacks, which is the other
     * route into the cut-in band and the damage pops. */
    tap(VM_KEY_NUM9);
    for (i = 0; i < 26; ++i) {
        char tag[24];
        sprintf(tag, "ai_%02d", i);
        step(tag, 150);
    }
    advance(9000);                              /* finish the enemy phase */
    step("round2_start", 40);

    /* Round 2 by pen: CAEDRIC held (7,9) through the enemy phase, so the
     * attacker that reached him is on one of the four neighbours. Trying to
     * walk him north is not an option -- the AI has taken that tile. */
    stay_and_attack(0, 7, 9);

    /* Auto-play the rest of the field to reach the result screen. Only the
     * phase-end key is sent: a stray OK on BP_RESULT would restart the battle
     * and wipe the screen this loop is waiting for. */
    for (i = 0; i < 12; ++i) {
        tap(VM_KEY_NUM9);
        advance(4200);
        if (i % 2) {
            char tag[24];
            sprintf(tag, "play_%02d", i / 2);
            dump_frame(tag);
        }
        if (g_exited) break;
    }
    step("play_last", 40);
    /* The result screen's two exits: CLEAR backs out to the menu, and the menu
     * row the harness lands on is BEGIN BATTLE, so one OK replays the field. */
    key("result_menu", VM_KEY_CLEAR);
    key("fight_again", VM_KEY_OK);
    /* The replay is deliberately left unplayed, which is the other outcome: the
     * vanguard's commander falls and the same result screen reads DEFEAT. */
    for (i = 0; i < 28; ++i) {
        tap(VM_KEY_NUM9);
        advance(4200);
        if ((i % 4) == 3) {
            char tag[24];
            sprintf(tag, "lose_%02d", i / 4);
            dump_frame(tag);
        }
    }
    step("lose_last", 40);
    printf("shots done, exited=%d\n", g_exited);
    return 0;
}
