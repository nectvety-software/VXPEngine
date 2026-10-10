#pragma once
#include <stdint.h>

struct PocketPitch {
    enum { WIDTH=240, HEIGHT=320, BUMPER_COUNT=5, FX_COUNT=12, MATCH_TICKS=1350 };
    struct Bumper { int16_t x,y,r; uint8_t kind; };
    struct Particle { int16_t x,y,vx,vy; uint8_t life; uint16_t color; };
    int mode, tick, score, best, goals, seconds, serveTicks;
    int ballX, ballY, ballVx, ballVy, spin, keeperX, keeperDir;
    int leftKick, rightKick, flash, skillLeft, skillRight, skillCooldown, aim, combo;
    bool exiting, loadedBest;
    Bumper bumpers[BUMPER_COUNT];
    Particle particles[FX_COUNT];
    PocketPitch();
    void loadBest(int value);
    void input(int key);
    void touch(int x, int y);
    void update();
    void draw(uint16_t* pixels) const;
private:
    void newMatch();
    void serve();
    void shoot(int side);
    void goal();
    void emit(int x,int y,uint16_t color,int count);
};
