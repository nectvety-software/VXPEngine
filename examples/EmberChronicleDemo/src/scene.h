#pragma once
#include "graphics/VxpStory2D.h"
#include "graphics/particles/VxpParticlePool.h"

enum EmberArea { EMBER_LIBRARY, EMBER_TERRACE, EMBER_VILLAGE };
struct EmberBolt { int16_t x,y,vx,vy; uint16_t age; uint8_t active, hostile; };

class EmberScene {
public:
    void init();
    void update(uint16_t dt=33);
    void draw(uint16_t* fb);
    void input(int key);
    void hold(int key, bool down);
    void enter(int area);
    void cast();
    int hero_x=115, hero_y=278, facing=0, area=EMBER_LIBRARY;
    int duel_hp=3, wards=0, quest=0, dialogue_step=0;
    int cast_ms=0, cooldown=0, walk_ms=0, hurt_ms=0;
    uint32_t time_ms=0, rng=0xE6BE2026u;
    uint8_t initialized=0, paused=0, exiting=0, held=0;
    uint8_t ward_done[3]={};
    VxpeStoryDialogue dialogue={};
    EmberBolt bolts[12]={};
    VxpeParticlePool particles={};
private:
    VxpeSpriteA8 backgrounds[3]={}, characters={}, fire={};
    VxpeSpriteBatch batch={};
    VxpeStoryStage2D stage={};
    uint16_t fire_pixels[4*24*32]={};
    uint8_t fire_alpha[4*24*32]={};
    int walk_left=0, rain_ms=0;
    uint32_t random();
    void sparkle(int x,int y,uint16_t color,int count);
    void actor(int index,int x,int y,int lift=0,int flip=0);
    void flame(uint16_t* fb,int x,int y,int size,int frame);
    void talk();
    void action();
};
