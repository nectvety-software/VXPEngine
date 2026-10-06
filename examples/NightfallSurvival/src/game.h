#pragma once
#include <stdint.h>

enum Action { FORWARD, REVERSE, TURN_LEFT, TURN_RIGHT, STRAFE_LEFT, STRAFE_RIGHT,
              FIRE, RELOAD, INTERACT, PAUSE, BACK };
enum Phase { TITLE, RUNNING, PAUSED, DEAD, GUIDE };
struct Zombie { float x,y; int hp,attack,frame; bool alive; };
struct Game {
    Phase phase;
    float x,y,angle;
    int tick,health,ammo,reserve,points,kills,wave,remaining,spawnTimer;
    int reloadTimer,fireTimer,hurtTimer,breakTimer,barrier,messageTimer,selected;
    unsigned held,random;
    bool exiting,gateOpen;
    Zombie zombies[18];
    float depth[240];
    const char* message;
    Game();
    void start();
    void action(Action key);
    void hold(Action key,bool down);
    void update();
    void draw(uint16_t* framebuffer);
    void move(float forward,float side);
    bool blocked(float px,float py) const;
    bool visible(float ax,float ay,float bx,float by) const;
    int cell(int cx,int cy) const;
    void spawn();
    void shoot();
    void interact();
};
