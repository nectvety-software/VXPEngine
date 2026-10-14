/* Drives the real StormArena25D main.c on the host and dumps every screen.
 * Build: tmp/make_shots.sh */
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

int main(void) {
    handle_sysevt(VM_MSG_CREATE, 0);
    advance(400);
    dump_frame("splash_early");
    advance(1200);
    dump_frame("splash_mid");
    advance(1400);
    dump_frame("menu_top");            /* the card auto-advances at 2.6 s */
    tap(VM_KEY_NUM8);
    tap(VM_KEY_NUM8);
    tap(VM_KEY_NUM8);                  /* cursor on HOW TO PLAY */
    advance(200);
    dump_frame("menu_help_row");
    tap(VM_KEY_OK);
    advance(200);
    dump_frame("help");
    tap(VM_KEY_CLEAR);
    advance(200);
    dump_frame("menu_after_help");
    tap(VM_KEY_NUM2);
    tap(VM_KEY_NUM2);
    tap(VM_KEY_NUM2);
    tap(VM_KEY_NUM2);                  /* wraps back to FIGHT A CPU */
    tap(VM_KEY_NUM6);                  /* P1 SIDE shortcut only on its row */
    advance(200);
    dump_frame("menu_row0");
    tap(VM_KEY_NUM8);                  /* WATCH DEMO */
    tap(VM_KEY_OK);
    advance(300);
    dump_frame("demo_start");
    advance(5000);
    dump_frame("demo_late");           /* both sides must be boxing */
    advance(8000);
    dump_frame("demo_mid");
    advance(9000);
    dump_frame("demo_end");            /* expect a K.O. overlay by now */
    advance(9000);
    dump_frame("demo_after");
    tap(VM_KEY_CLEAR);
    advance(300);
    dump_frame("menu_from_fight");
    handle_penevt(VM_PEN_EVENT_TAP, 120, 234);   /* P1 SIDE row */
    advance(200);
    dump_frame("menu_pen_side");
    handle_penevt(VM_PEN_EVENT_TAP, 8, 234);     /* outside the card: no-op */
    handle_penevt(VM_PEN_EVENT_TAP, 120, 278);   /* EXIT */
    advance(100);
    printf("exited=%d\n", g_exited);
    return 0;
}
