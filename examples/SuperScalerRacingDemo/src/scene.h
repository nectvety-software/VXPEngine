#pragma once
#include <stdint.h>

struct SuperScalerGame {
    struct Rival { int16_t lane_q8; uint16_t depth; uint8_t color; };
    int16_t player_x;
    uint16_t speed, phase, tick, distance, score, bestScore;
    uint8_t mode;
    bool exiting;
    Rival rivals[3];
    SuperScalerGame();
    void input(int key);
    void loadBest(uint16_t value);
    void update();
    void draw(uint16_t* pixels) const;
};
