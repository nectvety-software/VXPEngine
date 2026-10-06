#pragma once
#include <stdint.h>
#include "graphics/VxpActorSprite2D.h"
enum Screen { SPLASH, MENU, PLAY, LANGUAGE, HELP, ABOUT, SETTINGS, EXIT_CONFIRM };
enum Input { UP, DOWN, LEFT, RIGHT, OK, BACK };
struct Game {
    Screen screen = SPLASH;
    int selected = 0, language = 0, tick = 0;
    int x = 130, y = 200, fish = 0, cast = 0, cast_tick = 0;
    int facing = 1, walk = 0, last_move_tick = -99, reel_ticks = 0;
    VxpeActorState2D actor = {0,0,VXPE_ACTOR_EAST,VXPE_ACTOR_IDLE,0};
    int effects = 1, speed = 1;
    bool exiting = false;
    void input(Input key);
    void update();
    void draw(uint16_t* fb);
};
