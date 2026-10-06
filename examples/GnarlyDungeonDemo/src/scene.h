#pragma once
#include <stdint.h>
struct DungeonEnemy {float x,z;int hp,cooldown;};
struct DungeonScene {
    float x,z,yaw;int tick,health,slash,keys,phase,selected;bool exiting;
    DungeonEnemy enemies[3];uint16_t depth[320*240];
    DungeonScene();void start();void input(int key);void update();void draw(uint16_t* fb);
    bool blocked(float px,float pz) const;void move(float direction);void attack();
};
