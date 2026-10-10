#pragma once
#include <stdint.h>

struct LostLatencyMall {
    enum { WIDTH=240, HEIGHT=320, WORLD_W=120, WORLD_H=160, MEMORY_COUNT=4 };
    struct Vec { int32_t x,y,z; };
    int mode,tick,worldX,worldZ,yaw,scanBits,scanFlash,nearest,walked;
    bool exiting;
    uint16_t worldPixels[WORLD_W*WORLD_H];
    uint16_t wallDepth[WORLD_W];
    LostLatencyMall();
    void restore(uint8_t saved);
    uint8_t progress() const;
    void input(int key);
    void touch(int x,int y);
    void update();
    void draw(uint16_t* framebuffer);
private:
    void scan();
    void renderWorld();
};
