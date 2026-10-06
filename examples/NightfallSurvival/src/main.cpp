#include "vmsys.h"
#include "vmio.h"
#include "vmgraph.h"
#include "vmtimer.h"
#include "game.h"

static Game game;
static VMINT layer=-1,timer=-1;
static void draw(){
    if(layer<0)return;uint16_t* fb=(uint16_t*)vm_graphic_get_layer_buffer(layer);if(!fb)return;
    if(vm_graphic_get_screen_width()!=240||vm_graphic_get_screen_height()!=320)return;
    game.draw(fb);vm_graphic_flush_layer(&layer,1);
}
static void tick(VMINT){game.update();draw();}
static void stop(){game.held=0;if(timer>=0){vm_delete_timer(timer);timer=-1;}if(layer>=0){vm_graphic_delete_layer(layer);layer=-1;}}
static void system_event(VMINT event,VMINT){
    if(event==VM_MSG_CREATE||event==VM_MSG_ACTIVE){if(layer<0)layer=vm_graphic_create_layer(0,0,vm_graphic_get_screen_width(),vm_graphic_get_screen_height(),-1);if(timer<0)timer=vm_create_timer(33,tick);draw();}
    if(event==VM_MSG_PAINT)draw();
    if(event==VM_MSG_INACTIVE)stop();
    if(event==VM_MSG_QUIT){stop();vm_exit_app();}
}
static Action key_action(int key){
    if(key==VM_KEY_UP||key==VM_KEY_NUM2)return FORWARD;
    if(key==VM_KEY_DOWN||key==VM_KEY_NUM8)return REVERSE;
    if(key==VM_KEY_LEFT||key==VM_KEY_NUM4)return TURN_LEFT;
    if(key==VM_KEY_RIGHT||key==VM_KEY_NUM6)return TURN_RIGHT;
    if(key==VM_KEY_NUM1)return STRAFE_LEFT;if(key==VM_KEY_NUM3)return STRAFE_RIGHT;
    if(key==VM_KEY_NUM0)return RELOAD;if(key==VM_KEY_NUM7)return INTERACT;
    if(key==VM_KEY_NUM9)return PAUSE;
    if(key==VM_KEY_OK||key==VM_KEY_NUM5||key==VM_KEY_LEFT_SOFTKEY)return FIRE;
    if(key==VM_KEY_BACK||key==VM_KEY_CLEAR||key==VM_KEY_RIGHT_SOFTKEY)return BACK;
    return (Action)-1;
}
static void key_event(VMINT event,VMINT key){
    Action a=key_action(key);
    if((int)a<0)return;
    if(event==VM_KEY_EVENT_UP){game.hold(a,false);return;}
    if(event!=VM_KEY_EVENT_DOWN&&event!=VM_KEY_EVENT_REPEAT)return;
    if(a<=STRAFE_RIGHT&&game.phase==RUNNING)game.hold(a,true);
    else if(event==VM_KEY_EVENT_DOWN||(a<=TURN_RIGHT&&game.phase==TITLE))game.action(a);
    if(game.exiting){stop();vm_exit_app();return;}draw();
}
static void pen_event(VMINT event,VMINT px,VMINT py){
    if(event==VM_PEN_EVENT_RELEASE||event==VM_PEN_EVENT_ABORT){game.held=0;return;}
    if(event!=VM_PEN_EVENT_TAP&&event!=VM_PEN_EVENT_MOVE)return;
    if(game.phase==TITLE&&event==VM_PEN_EVENT_TAP){if(py>=148&&py<220){game.selected=(py-148)/24;game.action(FIRE);}}
    else if(game.phase==DEAD||game.phase==GUIDE){if(event==VM_PEN_EVENT_TAP)game.action(FIRE);}
    else if(game.phase==PAUSED){if(event==VM_PEN_EVENT_TAP)game.action(PAUSE);}
    else if(py<18&&event==VM_PEN_EVENT_TAP)game.action(PAUSE);
    else if(py>=298&&event==VM_PEN_EVENT_TAP){if(px<80)game.action(INTERACT);else if(px>170)game.action(RELOAD);else game.action(FIRE);}
    else if(px<70){game.held=0;if(py<130)game.hold(FORWARD,true);else if(py>200)game.hold(REVERSE,true);else game.hold(TURN_LEFT,true);}
    else if(px>185){game.held=0;game.hold(TURN_RIGHT,true);}
    else if(event==VM_PEN_EVENT_TAP)game.action(FIRE);
    if(game.exiting){stop();vm_exit_app();return;}draw();
}
extern "C" void vm_main(void){vm_reg_sysevt_callback(system_event);vm_reg_keyboard_callback(key_event);vm_reg_pen_callback(pen_event);}
