#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "scene.h"
#include <string.h>

static FoxScene scene;
static VMINT layer=-1,timer=-1;
static VMINT base_layer=-1;
static int layer_w=0,layer_h=0;

static void resize_layers(int w,int h) {
    if(layer>=0 && w==layer_w && h==layer_h) return;
    if(layer>=0) { vm_graphic_delete_layer(layer); layer=-1; }
    if(base_layer>=0) { vm_graphic_delete_layer(base_layer); base_layer=-1; }
    base_layer=vm_graphic_create_layer(0,0,w,h,-1);
    if(base_layer<0) return;
    // The drawing layer owns a current-size canvas stride for the native portrait display.
    layer=vm_graphic_create_layer(0,0,w,h,-1);
    layer_w=w; layer_h=h;
}

static void draw() {
    const int w=vm_graphic_get_screen_width(), h=vm_graphic_get_screen_height();
    if(w!=240 || h!=320) return;
    resize_layers(w,h);
    if(layer<0) return;
    uint16_t* fb=(uint16_t*)vm_graphic_get_layer_buffer(layer);
    if(!fb) return;
    scene.draw(fb);
    vm_graphic_flush_layer(&layer,1);
}
static void tick(VMINT) { scene.update(); draw(); }
static void stop() {
    scene.held=0;
    if(timer>=0) { vm_delete_timer(timer); timer=-1; }
    if(layer>=0) { vm_graphic_delete_layer(layer); layer=-1; }
    if(base_layer>=0) { vm_graphic_delete_layer(base_layer); base_layer=-1; }
    layer_w=layer_h=0;
}
static void system_event(VMINT e,VMINT) {
    if(e==VM_MSG_CREATE || e==VM_MSG_ACTIVE) {
        scene.init();
        if(timer<0) timer=vm_create_timer(33,tick);
        draw();
    }
    if(e==VM_MSG_PAINT) draw();
    if(e==VM_MSG_INACTIVE) stop();
    if(e==VM_MSG_QUIT) { stop(); vm_exit_app(); }
}
static void key_event(VMINT e,VMINT key) {
    int k=-2;
    if(key==VM_KEY_UP || key==VM_KEY_NUM2) k=2;
    if(key==VM_KEY_DOWN || key==VM_KEY_NUM8) k=8;
    if(key==VM_KEY_LEFT || key==VM_KEY_NUM4) k=4;
    if(key==VM_KEY_RIGHT || key==VM_KEY_NUM6) k=6;
    if(k>0) {
        if(e==VM_KEY_EVENT_UP) scene.hold(k,false);
        if(e==VM_KEY_EVENT_DOWN || e==VM_KEY_EVENT_REPEAT) scene.hold(k,true);
    } else if(e==VM_KEY_EVENT_DOWN) {
        if(key==VM_KEY_OK || key==VM_KEY_NUM5) k=5;
        if(key==VM_KEY_NUM7) k=7;
        if(key==VM_KEY_NUM9) k=9;
        if(key==VM_KEY_NUM0) k=0;
        if(key==VM_KEY_NUM1) k=1;
        if(key==VM_KEY_NUM3) k=3;
        if(key==VM_KEY_STAR) k=10;
        if(key==VM_KEY_BACK || key==VM_KEY_CLEAR || key==VM_KEY_RIGHT_SOFTKEY) k=-1;
        if(k!=-2) scene.input(k);
    }
    if(scene.exiting) { stop(); vm_exit_app(); return; }
    draw();
}
extern "C" void vm_main() {
    vm_reg_sysevt_callback(system_event);
    vm_reg_keyboard_callback(key_event);
}
