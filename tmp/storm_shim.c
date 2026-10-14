/* Host shim for the StormArena25D screen shots (tmp/storm_shots.c).
 *
 * StormArena25D touches eight MRE runtime entry points. Implementing them over a
 * static RGB565 buffer lets the real main.c run on the desktop, which is the
 * only way to look at the splash/menu/help layout in a second instead of an ARM
 * build plus an emulator session. The ARM build stays the final gate. */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include <stdio.h>
#include <string.h>

#define SW 240
#define SH 320

unsigned short g_fb[SW * SH];
unsigned int g_now_ms;
int g_exited;
static VM_TIMERPROC_T g_timer_proc;
static VMINT g_timer_id = -1;
static int g_frame;

/* Frames are written as raw RGB565; the Python side turns them into PNGs. */
void dump_frame(const char* tag) {
    char path[128];
    FILE* f;
    sprintf(path, "tmp/shots/%s.%02d.565", tag, g_frame++);
    f = fopen(path, "wb");
    if (!f) return;
    fwrite(g_fb, 2, SW * SH, f);
    fclose(f);
}

VMINT vm_get_tick_count(void) { return (VMINT)g_now_ms; }
VMINT vm_graphic_create_layer(VMINT x, VMINT y, VMINT w, VMINT h,
                              VMINT trans) {
    (void)x; (void)y; (void)w; (void)h; (void)trans;
    return 0;
}
VMINT vm_graphic_delete_layer(VMINT handle) { (void)handle; return 0; }
VMUINT8* vm_graphic_get_layer_buffer(VMINT handle) {
    (void)handle;
    return (VMUINT8*)g_fb;
}
VMINT vm_graphic_flush_layer(VMINT* handles, VMINT count) {
    (void)handles; (void)count;
    return 0;
}
VMINT vm_create_timer(VMUINT32 ms, VM_TIMERPROC_T proc) {
    (void)ms;
    g_timer_proc = proc;
    g_timer_id = 1;
    return 1;
}
VMINT vm_delete_timer(VMINT id) { (void)id; g_timer_id = -1; return 0; }
void vm_exit_app(void) { g_exited = 1; }
void vm_reg_sysevt_callback(void (*f)(VMINT, VMINT)) { (void)f; }
void vm_reg_keyboard_callback(vm_key_handler_t h) { (void)h; }
void vm_reg_pen_callback(vm_pen_handler_t h) { (void)h; }

/* Pump the app timer for `ms` of virtual time at the emulator's 50 ms cadence. */
void advance(int ms) {
    int i, n = ms / 50;
    for (i = 0; i < n; ++i) {
        g_now_ms += 50;
        if (g_timer_id > 0 && g_timer_proc) g_timer_proc(g_timer_id);
    }
}
