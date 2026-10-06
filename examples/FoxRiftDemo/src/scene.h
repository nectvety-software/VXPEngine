#pragma once
#include "graphics/VxpStory2D.h"
#include "graphics/particles/VxpParticlePool.h"
enum DuelScreen { DUEL_SPLASH, DUEL_SELECT, DUEL_MATCH, DUEL_RESULT };
struct HeroDef {
    const char* name; const char* role; const char* passive;
    const char* skills[4]; int max_hp,max_mana,speed,attack,attack_range,attack_cd;
    int cost[4],cd[4]; unsigned short color;
};
extern const HeroDef duel_heroes[3];
struct DuelFighter {
    int hero,x,y,hp,mana,shield,cooldown[4],attack_ms,stun_ms,slow_ms;
    int respawn_ms,skin; int cast_ms,heal_ms,facing,skill_count,damage_dealt,casts,healing,moving;
};
struct DuelProjectile { int x,y,vx,vy,life,damage,stun,slow,owner; unsigned char active; };
struct DuelStructure { int owner,y,hp,max_hp,attack_ms; };
struct DuelEffect { int x,y,life,hero,skill,owner; };
class FoxScene {
public:
    void init(); void update(unsigned short dt=33); void draw(unsigned short* fb);
    void input(int key); void hold(int key,bool down); void cast(int skill);
    void start_match(); void restart(); void select_hero(int index);
    void cast_for(int owner,int skill); void hit(int owner,int amount,int stun=0,int slow=0);
    int screen=DUEL_SPLASH,selected=0,bot_selected=1,held=0,paused=0,exiting=0;
    int result=0,time_ms=0,ui_ms=0,initialized=0,help=0,regen_ms=0,bot_think_ms=0;
    int bot_decisions=0,bot_retreats=0;
    int selected_skin=0,bot_skin=0,camera_y=0;
    DuelStructure structures[6]={}; DuelEffect effects[12]={};
    void damage_structure(int owner,int index,int amount);
    void lane_update(unsigned short dt);
    DuelFighter fighters[2]={}; DuelProjectile projectiles[16]={};
private:
    VxpeSpriteA8 background={},heroes={},logo={},structure_art={},skill_art={}; VxpeParticlePool particles={};
    void sparks(int x,int y,unsigned short color,int count);
    void bot_update(unsigned short dt); void heal(int owner);
    void move(int owner,int dx,int dy); void finish();
    void sprite(unsigned short* fb,int hero,int row,int x,int y,int w,int h,int flip=0,int skin=0);
    void bar(unsigned short* fb,int x,int y,int w,int value,int maximum,unsigned short color);
    void text(unsigned short* fb,int x,int y,const char* text,unsigned short color);
    void centered(unsigned short* fb,int y,const char* text,unsigned short color);
    void title(unsigned short* fb,int y,const char* text,int scale=0);
    void numbers(unsigned short* fb,int x,int y,const char* text);
    void hero_text(unsigned short* fb,int x,int y,const char* text,unsigned short color);
    void skill_icon(unsigned short* fb,int hero,int skill,int x,int y,int size);
    void draw_menu(unsigned short* fb); void draw_match(unsigned short* fb);
};
