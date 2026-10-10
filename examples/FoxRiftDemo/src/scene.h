#pragma once
#include "graphics/VxpStory2D.h"
enum DuelScreen { DUEL_SPLASH, DUEL_SELECT, DUEL_MATCH, DUEL_RESULT };
enum DuelBotPlan { BOT_FARM, BOT_DUEL, BOT_DEFEND, BOT_PUSH, BOT_RECOVER, BOT_WAIT };
struct HeroDef {
    const char* name; const char* role; const char* passive;
    const char* skills[4]; int max_hp,max_mana,speed,attack,attack_range,attack_cd;
    int cost[4],cd[4]; unsigned short color;
};
extern const HeroDef duel_heroes[3];
struct DuelFighter {
    int hero,x,y,hp,mana,shield,cooldown[4],attack_ms,stun_ms,slow_ms;
    int gold,items,last_hits,kills,last_skill,basic_ms; int respawn_ms,skin; int cast_ms,heal_ms,facing,skill_count,damage_dealt,casts,healing,moving;
    int direction,basic_x,basic_y;
};
struct DuelProjectile { int x,y,vx,vy,life,damage,stun,slow,owner,hero,skill; unsigned char active; };
struct DuelStructure { int owner,y,hp,max_hp,attack_ms,aggro_ms; int shot_ms,shot_x,shot_y,hero_shots; };
struct DuelEffect { int x,y,life,hero,skill,owner,x2,y2,duration,impact; };
struct DuelMinion { int active,owner,kind,x,y,hp,max_hp,attack_ms,shot_ms,moving; };
struct DuelItem { const char* name;const char* description;int cost; };
extern const DuelItem duel_items[6];
class FoxScene {
public:
    void init(); void update(unsigned short dt=33); void draw(unsigned short* fb);
    void input(int key); void hold(int key,bool down); void cast(int skill);
    bool basic_attack(int owner);
    void start_match(); void restart(); void select_hero(int index);
    void cast_for(int owner,int skill); void hit(int owner,int amount,int stun=0,int slow=0);
    int screen=DUEL_SPLASH,selected=0,bot_selected=1,held=0,paused=0,exiting=0;
    int result=0,time_ms=0,ui_ms=0,initialized=0,help=0,regen_ms=0,bot_think_ms=0;
    int bot_decisions=0,bot_retreats=0;
    int bot_plan=BOT_PUSH,bot_goal_x=120,bot_goal_y=610;
    int selected_skin=0,bot_skin=0,camera_y=0;
    DuelStructure structures[6]={}; DuelEffect effects[24]={};
    void damage_structure(int owner,int index,int amount);
    void lane_update(unsigned short dt);
    bool walkable(int x,int y) const;
    int max_hp(int owner) const;int max_mana(int owner) const;
    int attack_power(int owner) const;int skill_power(int owner) const;
    int attack_delay(int owner) const;int move_speed(int owner) const;
    int take_damage(int owner,int amount);bool buy_item(int owner,int item);
    void spawn_wave();void hurt_minion(int owner,int index,int damage);
    void army_update(unsigned short dt);void farm_cast(int owner,int skill);
    int nearest_minion(int owner,int x,int y,int range) const;
    int shop_open=0,shop_selected=0,shop_notice=0,wave_ms=3000,wave_count=0,army_ms=0,gold_ms=0;
    DuelMinion minions[48]={};
    DuelFighter fighters[2]={}; DuelProjectile projectiles[16]={};
private:
    VxpeSpriteA8 background={},heroes={},logo={},structure_art={},skill_art={},environment_art={},action_art={},army_art={},direction_art={};
    void spawn_effect(int owner,int hero,int skill,int x,int y,int x2,int y2,int impact=0);
    void draw_skill_effects(unsigned short* fb);
    void bot_update(unsigned short dt); void heal(int owner);
    void translate(int owner,int dx,int dy); void bot_move(int dx,int dy);
    void draw_shop(unsigned short* fb);void draw_minion(unsigned short* fb,int index);
    void draw_action(unsigned short* fb,int owner,int x,int y);
    void draw_map_object(unsigned short* fb,int index);
    void draw_structure(unsigned short* fb,int index);
    void draw_fighter(unsigned short* fb,int index);
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
