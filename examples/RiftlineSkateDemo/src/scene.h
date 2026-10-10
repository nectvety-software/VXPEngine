#pragma once
#include <stdint.h>

struct RiftlineScene {
    int tick, px, pz, speed, jump, grind, cameraMode, points, lean;
    int trick, combo, comboTicks, bestCombo;
    bool paused, exiting, started, crashed;
    enum { WIDTH=240, HEIGHT=320, RENDER_WIDTH=120, RENDER_HEIGHT=160 };
    uint16_t depth[RENDER_WIDTH*RENDER_HEIGHT];
    uint16_t worldPixels[RENDER_WIDTH*RENDER_HEIGHT];
    RiftlineScene();
    void input(int key); // 4/6 steer, 2/8 speed, 5 ollie, 1/3 tricks, 7 grind, 0 camera, 9 pause
    void update();
    void draw(uint16_t* pixels);
};
