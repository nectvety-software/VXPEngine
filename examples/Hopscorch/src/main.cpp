#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "game.h"
static Game game;
static VMINT layer=-1,timer=-1;
static uint16_t portrait[320*240];
static void draw(){if(layer>=0){
    uint16_t* fb=(uint16_t*)vm_graphic_get_layer_buffer(layer);
    if(!fb)return;
    int w=vm_graphic_get_screen_width(),h=vm_graphic_get_screen_height();
    if(w==240&&h==320)game.draw(fb);
    else if(w==320&&h==240){game.draw(portrait);
        for(int y=0;y<240;++y)for(int x=0;x<320;++x)fb[y*320+x]=portrait[(319-x)*240+y];}
    vm_graphic_flush_layer(&layer,1);
}}
static void tick(VMINT){game.update();draw();}
static void stop(){if(timer>=0){vm_delete_timer(timer);timer=-1;}if(layer>=0){vm_graphic_delete_layer(layer);layer=-1;}}
static void system_event(VMINT event,VMINT){
    if(event==VM_MSG_CREATE||event==VM_MSG_ACTIVE){if(layer<0)layer=vm_graphic_create_layer(0,0,vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);if(timer<0)timer=vm_create_timer(33,tick);draw();}
    if(event==VM_MSG_PAINT)draw();
    if(event==VM_MSG_INACTIVE)stop();
    if(event==VM_MSG_QUIT){stop();vm_exit_app();}
}
static void key_event(VMINT event,VMINT key){
    if(event!=VM_KEY_EVENT_DOWN&&event!=VM_KEY_EVENT_REPEAT)return;
    if(event==VM_KEY_EVENT_REPEAT&&key!=VM_KEY_UP&&key!=VM_KEY_DOWN&&key!=VM_KEY_LEFT&&key!=VM_KEY_RIGHT&&key!=VM_KEY_NUM2&&key!=VM_KEY_NUM4&&key!=VM_KEY_NUM6&&key!=VM_KEY_NUM8)return;
    if(key==VM_KEY_UP||key==VM_KEY_NUM2)game.input(UP);
    if(key==VM_KEY_DOWN||key==VM_KEY_NUM8)game.input(DOWN);
    if(key==VM_KEY_LEFT||key==VM_KEY_NUM4)game.input(LEFT);
    if(key==VM_KEY_RIGHT||key==VM_KEY_NUM6)game.input(RIGHT);
    if(key==VM_KEY_OK||key==VM_KEY_NUM5||key==VM_KEY_LEFT_SOFTKEY)game.input(OK);
    if(key==VM_KEY_BACK||key==VM_KEY_CLEAR||key==VM_KEY_RIGHT_SOFTKEY)game.input(BACK);
    if(game.exiting){stop();vm_exit_app();return;}draw();
}
extern "C" void vm_main(void){vm_reg_sysevt_callback(system_event);vm_reg_keyboard_callback(key_event);}
