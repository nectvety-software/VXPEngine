/* main.c - MRE application glue: events, layer, timer */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmchset.h"
#include "vmstdlib.h"
#include "vmtimer.h"

#include "game.h"
#include "gfx.h"

VMINT  g_layer = -1;
VMUINT8* g_buf = 0;
static VMINT g_timer = -1;
static VMINT g_started = 0;

void handle_sysevt(VMINT message, VMINT param);
void handle_keyevt(VMINT event, VMINT keycode);
void handle_penevt(VMINT event, VMINT x, VMINT y);

static void timer_tick(VMINT tid) {
    (void)tid;
    game_tick();
}

void gfx_present(void) {
    if (g_layer >= 0) vm_graphic_flush_layer(&g_layer, 1);
}

void vm_main(void) {
    g_layer = -1;
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}

static void start(void) {
    g_layer = vm_graphic_create_layer(0, 0,
        vm_graphic_get_screen_width(), vm_graphic_get_screen_height(), -1);
    g_buf = vm_graphic_get_layer_buffer(g_layer);
    vm_graphic_set_clip(0, 0,
        vm_graphic_get_screen_width(), vm_graphic_get_screen_height());
    if (!g_started) {
        game_init();
        g_started = 1;
    }
    if (g_timer < 0) g_timer = vm_create_timer(TICK_MS, timer_tick);
}

static void stop(void) {
    if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }
    if (g_layer >= 0) { vm_graphic_delete_layer(g_layer); g_layer = -1; }
    g_buf = 0;
}

void handle_sysevt(VMINT message, VMINT param) {
    (void)param;
    switch (message) {
    case VM_MSG_CREATE:
    case VM_MSG_ACTIVE:
        start();
        break;
    case VM_MSG_PAINT:
        if (g_buf) game_draw();
        break;
    case VM_MSG_INACTIVE:
    case VM_MSG_QUIT:
        stop();
        if (message == VM_MSG_QUIT && g_started) {
            game_shutdown();
            g_started = 0;
            vm_exit_app();
        }
        break;
    }
}

static void set_held(int keycode, int down) {
    switch (keycode) {
    case VM_KEY_LEFT: case VM_KEY_NUM4: G.key_left = down; break;
    case VM_KEY_RIGHT: case VM_KEY_NUM6: G.key_right = down; break;
    case VM_KEY_UP: case VM_KEY_NUM2: G.key_up = down; if (down) G.key_jump = 1; break;
    case VM_KEY_DOWN: case VM_KEY_NUM8: G.key_down = down; break;
    }
}

void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN) {
        set_held(keycode, 1);
        if (keycode == VM_KEY_RIGHT_SOFTKEY || keycode == VM_KEY_CLEAR || keycode == VM_KEY_BACK) {
            if (G.state == ST_PLAY) { G.state = ST_PAUSE; return; }
            if (G.state == ST_SHOP) { G.state = ST_PLAY; return; } /* close, keep playing */
            /* ST_PAUSE falls through to game_key: RSK there saves and exits */
            if (G.state != ST_PAUSE) { game_shutdown(); vm_exit_app(); return; }
        }
        game_key(keycode);
    } else if (event == VM_KEY_EVENT_UP) {
        set_held(keycode, 0);
        if (keycode == VM_KEY_UP || keycode == VM_KEY_NUM2) G.key_jump = 0;
    }
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    if (event == VM_PEN_EVENT_TAP) game_pen(x, y);
}
