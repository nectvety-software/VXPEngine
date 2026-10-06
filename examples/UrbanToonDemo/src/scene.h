#pragma once
#include <stdint.h>
struct UrbanScene {
    int tick,px,pz,speed,jump,grind,cameraMode,points,lean;
    bool paused,exiting;
    enum { WIDTH=240,HEIGHT=320,RENDER_WIDTH=120,RENDER_HEIGHT=160 };
    uint16_t depth[RENDER_WIDTH*RENDER_HEIGHT];
    uint16_t worldPixels[RENDER_WIDTH*RENDER_HEIGHT];
    UrbanScene();
    void input(int key); // keypad 2/8 speed, 4/6 steer, 5 jump, 7 grind, 0 camera, 9 pause
    void update();
    void draw(uint16_t* pixels);
};
