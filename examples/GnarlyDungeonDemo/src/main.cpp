#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "scene.h"
static DungeonScene scene;
static VMINT layer=-1,timer=-1;
static void draw(){if(layer<0)return;uint16_t* fb=(uint16_t*)vm_graphic_get_layer_buffer(layer);if(!fb)return;
    if(vm_graphic_get_screen_width()!=240||vm_graphic_get_screen_height()!=320)return;
    scene.draw(fb);vm_graphic_flush_layer(&layer,1);
}
static void tick(VMINT){scene.update();draw();}
static void stop(){if(timer>=0){vm_delete_timer(timer);timer=-1;}if(layer>=0){vm_graphic_delete_layer(layer);layer=-1;}}
static void system_event(VMINT e,VMINT){if(e==VM_MSG_CREATE||e==VM_MSG_ACTIVE){if(layer<0)layer=vm_graphic_create_layer(0,0,vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);if(timer<0)timer=vm_create_timer(33,tick);draw();}if(e==VM_MSG_PAINT)draw();if(e==VM_MSG_INACTIVE)stop();if(e==VM_MSG_QUIT){stop();vm_exit_app();}}
static void key_event(VMINT e,VMINT key){if(e!=VM_KEY_EVENT_DOWN&&e!=VM_KEY_EVENT_REPEAT)return;int k=-2;
    if(key==VM_KEY_UP||key==VM_KEY_NUM2)k=2;if(key==VM_KEY_DOWN||key==VM_KEY_NUM8)k=8;
    if(key==VM_KEY_LEFT||key==VM_KEY_NUM4)k=4;if(key==VM_KEY_RIGHT||key==VM_KEY_NUM6)k=6;
    if(e==VM_KEY_EVENT_DOWN){if(key==VM_KEY_OK||key==VM_KEY_NUM5)k=5;if(key==VM_KEY_NUM7)k=7;if(key==VM_KEY_NUM0)k=0;if(key==VM_KEY_NUM9)k=9;if(key==VM_KEY_BACK||key==VM_KEY_CLEAR||key==VM_KEY_RIGHT_SOFTKEY)k=-1;}
    if(k!=-2)scene.input(k);if(scene.exiting){stop();vm_exit_app();return;}draw();}
extern "C" void vm_main(void){vm_reg_sysevt_callback(system_event);vm_reg_keyboard_callback(key_event);}
