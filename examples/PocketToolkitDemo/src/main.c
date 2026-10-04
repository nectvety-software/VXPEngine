/* main.c - ứng dụng MRE VXP do VXPEngine sinh ra.
 *
 * Chế độ thiết kế: nếu màn Camera 2D có component (VXP_DESIGN_ACTIVE_COUNT > 0),
 * game nạp sprite .raw do IDE xuất từ màn thiết kế và vẽ đúng vị trí/kích thước
 * đã thiết kế — đồ họa build = Camera 2D = giả lập.
 * Nếu màn thiết kế trống, game chạy nội dung mặc định bên dưới ("chạy theo code").
 */
#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "vmres.h"
#include "vmmm.h"
#include <string.h>

#if defined(__has_include)
#  if __has_include("scene_bindings.h")
#    include "scene_bindings.h"
#  endif
#endif
#ifndef VXP_DESIGN_ACTIVE_COUNT
#  define VXP_DESIGN_ACTIVE_COUNT 0
#endif
#ifndef VXP_DESIGN_ACTIVE_HAS_DESIGN
#  define VXP_DESIGN_ACTIVE_HAS_DESIGN 0
#endif

static VMINT g_layer = -1;
static VMINT g_timer = -1;
static VMINT g_tick = 0;

#define RGB565(r, g, b) (VMUINT16)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3))

static VMUINT16* layer_fb(void) {
    return (VMUINT16*)vm_graphic_get_layer_buffer(g_layer);
}

static void fb_fill(VMUINT16* fb, int sw, int sh, int x, int y, int w, int h, VMUINT16 c) {
    int i, j, x0, y0, x1, y1;
    x0 = x < 0 ? 0 : x; y0 = y < 0 ? 0 : y;
    x1 = x + w > sw ? sw : x + w; y1 = y + h > sh ? sh : y + h;
    for (j = y0; j < y1; j++) {
        VMUINT16* row = fb + j * sw;
        for (i = x0; i < x1; i++) row[i] = c;
    }
}

static void fb_frame(VMUINT16* fb, int sw, int sh, int x, int y, int w, int h, VMUINT16 c) {
    fb_fill(fb, sw, sh, x, y, w, 1, c);
    fb_fill(fb, sw, sh, x, y + h - 1, w, 1, c);
    fb_fill(fb, sw, sh, x, y, 1, h, c);
    fb_fill(fb, sw, sh, x + w - 1, y, 1, h, c);
}

static void backdrop(VMUINT16* fb, int sw, int sh) {
    int x, y;
    for (y = 0; y < sh; y++) {
        VMUINT16 c = RGB565(10 + (y >> 4), 18 + (y >> 3), 32 + (y >> 3));
        for (x = 0; x < sw; x++) fb[y * sw + x] = c;
    }
}

#if VXP_DESIGN_ACTIVE_HAS_DESIGN

static VMUINT8* g_comp_data[VXP_DESIGN_ACTIVE_COUNT];

static void design_load(void) {
    int i;
    for (i = 0; i < VXP_DESIGN_ACTIVE_COUNT; i++) {
        VMINT size = 0;
        g_comp_data[i] = 0;
        if (VXP_DESIGN_ACTIVE_COMPONENTS[i].res[0] != 0) {
            g_comp_data[i] = vm_load_resource((VMSTR)VXP_DESIGN_ACTIVE_COMPONENTS[i].res, &size);
            if (size <= 8) {
                if (g_comp_data[i]) vm_free(g_comp_data[i]);
                g_comp_data[i] = 0;
            }
        }
    }
}

static void design_free(void) {
    int i;
    for (i = 0; i < VXP_DESIGN_ACTIVE_COUNT; i++) {
        if (g_comp_data[i]) { vm_free(g_comp_data[i]); g_comp_data[i] = 0; }
    }
}

/* Blit sprite .raw (header 8 byte + RGB565 + mask 1-bit) với tâm tại (cx, cy). */
static void design_blit(VMUINT16* fb, int sw, int sh, VMUINT8* data, int cx, int cy) {
    int w = data[0] | (data[1] << 8);
    int h = data[2] | (data[3] << 8);
    int opaque = data[4];
    VMUINT16* px = (VMUINT16*)(data + 8);
    VMUINT8* mask = data + 8 + w * h * 2;
    int x0 = cx - w / 2, y0 = cy - h / 2;
    int i, j;
    for (j = 0; j < h; j++) {
        int dy = y0 + j;
        if (dy < 0 || dy >= sh) continue;
        for (i = 0; i < w; i++) {
            int dx = x0 + i, o = j * w + i;
            if (dx < 0 || dx >= sw) continue;
            if (opaque || (mask[o >> 3] & (0x80 >> (o & 7)))) {
                fb[dy * sw + dx] = px[o];
            }
        }
    }
}

static VMUINT16 design_type_color(const char* type) {
    if (strstr(type, "Text")) return RGB565(255, 214, 102);
    if (strstr(type, "Circle")) return RGB565(122, 198, 255);
    if (strstr(type, "Rectangle")) return RGB565(150, 168, 200);
    return RGB565(96, 200, 140);
}

static void draw_design(int sw, int sh) {
    VMUINT16* fb = layer_fb();
    int i;
    if (!fb) return;
    backdrop(fb, sw, sh);
    for (i = 0; i < VXP_DESIGN_ACTIVE_COUNT; i++) {
        const VxpDesignComponent* comp = &VXP_DESIGN_ACTIVE_COMPONENTS[i];
        int cx = (int)(comp->x + sw / 2);
        int cy = (int)(comp->y + sh / 2);
        int w = (int)comp->width;
        int h = (int)comp->height;
        if (!comp->visible) continue;
        if (g_comp_data[i]) {
            design_blit(fb, sw, sh, g_comp_data[i], cx, cy);
        } else if (w > 0 && h > 0) {
            VMUINT16 c = design_type_color(comp->type);
            fb_fill(fb, sw, sh, cx - w / 2, cy - h / 2, w, h, c);
            fb_frame(fb, sw, sh, cx - w / 2, cy - h / 2, w, h, RGB565(230, 238, 250));
        }
    }
}

#endif /* VXP_DESIGN_ACTIVE_HAS_DESIGN */

static void draw_default(int sw, int sh) {
    VMUINT16* fb = layer_fb();
    int x, y, bar;
    if (!fb) return;
    backdrop(fb, sw, sh);
    for (y = 40; y < 120; y++) {
        for (x = 20; x < sw - 20; x++) {
            int edge = (x <= 21 || x >= sw - 22 || y <= 41 || y >= 118);
            fb[y * sw + x] = edge ? RGB565(120, 160, 220) : RGB565(8, 12, 20);
        }
    }
    bar = (g_tick * 2) % (sw + 40) - 20;
    for (y = 150; y < 162; y++) {
        for (x = bar; x < bar + 24; x++) {
            if (x >= 4 && x < sw - 4) fb[y * sw + x] = RGB565(255, 200, 60);
        }
    }
}

static void draw(void) {
    VMINT sw, sh;
    if (g_layer < 0) return;
    sw = vm_graphic_get_screen_width();
    sh = vm_graphic_get_screen_height();
#if VXP_DESIGN_ACTIVE_HAS_DESIGN
    if (VXP_DESIGN_ACTIVE_COUNT > 0) {
        draw_design(sw, sh);
    } else {
        draw_default(sw, sh);
    }
#else
    draw_default(sw, sh);
#endif
    vm_graphic_flush_layer(&g_layer, 1);
}

static void tick(VMINT tid) {
    (void)tid;
    g_tick++;
    draw();
}

static void start(void) {
    if (g_layer < 0) {
        g_layer = vm_graphic_create_layer(0, 0,
            vm_graphic_get_screen_width(), vm_graphic_get_screen_height(), -1);
    }
#if VXP_DESIGN_ACTIVE_HAS_DESIGN
    design_load();
#endif
    if (g_timer < 0) g_timer = vm_create_timer(50, tick);
    draw();
}

static void stop(void) {
    if (g_timer >= 0) { vm_delete_timer(g_timer); g_timer = -1; }
#if VXP_DESIGN_ACTIVE_HAS_DESIGN
    design_free();
#endif
    if (g_layer >= 0) { vm_graphic_delete_layer(g_layer); g_layer = -1; }
}

void handle_sysevt(VMINT message, VMINT param) {
    (void)param;
    switch (message) {
    case VM_MSG_CREATE:
    case VM_MSG_ACTIVE:
        start();
        break;
    case VM_MSG_PAINT:
        draw();
        break;
    case VM_MSG_INACTIVE:
    case VM_MSG_QUIT:
        stop();
        if (message == VM_MSG_QUIT) vm_exit_app();
        break;
    }
}

void handle_keyevt(VMINT event, VMINT keycode) {
    if (event == VM_KEY_EVENT_DOWN &&
        (keycode == VM_KEY_RIGHT_SOFTKEY || keycode == VM_KEY_CLEAR || keycode == VM_KEY_BACK)) {
        vm_exit_app();
    }
}

void handle_penevt(VMINT event, VMINT x, VMINT y) {
    (void)event; (void)x; (void)y;
}

void vm_main(void) {
    vm_reg_sysevt_callback(handle_sysevt);
    vm_reg_keyboard_callback(handle_keyevt);
    vm_reg_pen_callback(handle_penevt);
}
