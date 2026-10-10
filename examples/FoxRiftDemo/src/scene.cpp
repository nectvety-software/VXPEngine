#include "scene.h"
#include "assets_generated.h"
#include "combat_assets_generated.h"
#include "environment_assets_generated.h"
#include "army_assets_generated.h"
#include "world_generated.h"
#include "font_styles_generated.h"
#include <string.h>
#include <stdio.h>
static int absi(int n){return n<0?-n:n;}
static int clampi(int v,int lo,int hi){return v<lo?lo:(v>hi?hi:v);}
static int dist(const DuelFighter& a,const DuelFighter& b){return absi(a.x-b.x)+absi(a.y-b.y);}
#include "hero_roster_generated.h"
void FoxScene::init(){
    if(initialized)return;
    initialized=1;
    vxpe2d_sprite_a8_from_vxa8(duel_lane_ground,sizeof(duel_lane_ground),&background);
    vxpe2d_sprite_a8_from_vxa8(duel_heroes_atlas,sizeof(duel_heroes_atlas),&heroes);
    vxpe2d_sprite_a8_from_vxa8(duel_logo,sizeof(duel_logo),&logo);
    vxpe2d_sprite_a8_from_vxa8(duel_structures,sizeof(duel_structures),&structure_art);
    vxpe2d_sprite_a8_from_vxa8(duel_skill_icons,sizeof(duel_skill_icons),&skill_art);
    vxpe2d_sprite_a8_from_vxa8(duel_environment,sizeof(duel_environment),&environment_art);
    vxpe2d_sprite_a8_from_vxa8(duel_action_poses,sizeof(duel_action_poses),&action_art);
    vxpe2d_sprite_a8_from_vxa8(duel_minion_units,sizeof(duel_minion_units),&army_art);
    vxpe2d_sprite_a8_from_vxa8(duel_directional_poses,sizeof(duel_directional_poses),&direction_art);
    screen=DUEL_SPLASH;
}
static const char* skin_names[3][2]={{"PRISM","FROST PRISM"},{"COPPER","OBSIDIAN"},{"WIND","SUNSET"}};
static const unsigned short skin_tints[3]={0x87FF,0xC5BF,0xFD30};
void FoxScene::select_hero(int index){selected=(index%3+3)%3;held=0;}
void FoxScene::start_match(){
    init();memset(fighters,0,sizeof(fighters));memset(projectiles,0,sizeof(projectiles));
    fighters[0].hero=selected;fighters[1].hero=bot_selected;
    fighters[0].skin=selected_skin;fighters[1].skin=bot_skin;
    memset(effects,0,sizeof(effects));memset(minions,0,sizeof(minions));
    shop_open=shop_selected=shop_notice=wave_count=army_ms=gold_ms=0;wave_ms=3000;
    bot_plan=BOT_PUSH;bot_goal_x=120;bot_goal_y=610;
    for(int i=0;i<6;++i){int owner=i/3;structures[i]={owner,owner?(90+(i%3)*130):(870-(i%3)*130),i%3?900:1800,i%3?900:1800,0,0,0,0,0,0};}
    for(int i=0;i<2;++i){auto& f=fighters[i];const auto& h=duel_heroes[f.hero];
        f.x=i?179:65;f.y=i?210:750;f.hp=h.max_hp;f.mana=h.max_mana;f.facing=i;f.direction=i?8:2;f.gold=120;}
    screen=DUEL_MATCH;held=paused=result=time_ms=regen_ms=bot_think_ms=bot_decisions=bot_retreats=0;
    camera_y=clampi(fighters[0].y-190,0,640);
}
void FoxScene::restart(){start_match();}
void FoxScene::hold(int key,bool down){
    if(screen==DUEL_SELECT){if(down){
        if(key==4)select_hero(selected-1);
        if(key==6)select_hero(selected+1);
        if(key==2)bot_selected=(bot_selected+2)%3;
        if(key==8)bot_selected=(bot_selected+1)%3;
    }return;}
    if(shop_open&&screen==DUEL_MATCH){if(down&&(key==2||key==8))shop_selected=(shop_selected+(key==2?5:1))%6;return;}
    if(screen!=DUEL_MATCH||paused||result)return;
    int b=key==12?16:(key==4?1:(key==6?2:(key==2?4:(key==8?8:0))));
    if(down)held|=b;else held&=~b;
}
void FoxScene::input(int key){
    init();
    if(screen==DUEL_SPLASH){if(key==-1){exiting=1;return;}screen=DUEL_SELECT;ui_ms=0;return;}
    if(screen==DUEL_SELECT){
        if(key==-1){exiting=1;return;}
        if(key==7){selected_skin^=1;return;}
        if(key==9){bot_skin^=1;return;}
        if(key==1){help=!help;return;}
        if(key==5){help=0;start_match();return;}
        return;
    }
    if(screen==DUEL_MATCH&&shop_open){
        if(key==-1||key==11)shop_open=0;
        else if(key==5)shop_notice=buy_item(0,shop_selected)?0:1800;
        return;
    }
    if(key==-1){screen=DUEL_SELECT;held=paused=0;return;}
    if(key==3 || (screen==DUEL_RESULT&&key==5)){start_match();return;}
    if(screen!=DUEL_MATCH)return;
    if(key==11){if(!paused&&!result){shop_open=1;held=0;}return;}
    if(key==10){paused=!paused;held=0;return;}
    if(paused||result)return;
    if(key==12)basic_attack(0);
    if(key==5)cast(0);
    if(key==7)cast(1);
    if(key==9)cast(2);
    if(key==0)cast(3);
    if(key==1)heal(0);
}
void FoxScene::finish(){
    if(screen!=DUEL_MATCH)return;
    if(structures[0].hp<=0||structures[3].hp<=0||time_ms>=300000){
        int a=structures[0].hp,b=structures[3].hp;
        result=a==b?2:(a>b?1:-1);screen=DUEL_RESULT;held=paused=shop_open=0;
    }
}
void FoxScene::damage_structure(int owner,int index,int amount){
    if(owner<0||owner>1||index<0||index>=6||amount<=0)return;
    auto& t=structures[index];if(t.owner==owner||t.hp<=0)return;
    int outer=t.owner*3+2,inner=t.owner*3+1;
    if(index!=outer&&structures[outer].hp>0)return;
    if(index%3==0&&structures[inner].hp>0)return;
    int old_hp=t.hp;t.hp=clampi(t.hp-amount,0,t.max_hp);
    if(old_hp>0&&t.hp==0)fighters[owner].gold+=index%3?100:200;
    finish();
}
void FoxScene::lane_update(unsigned short dt){
    for(auto& t:structures){
        if(t.hp<=0)continue;
        t.attack_ms=clampi(t.attack_ms-dt,0,1200);
        auto& enemy=fighters[1-t.owner];t.aggro_ms=clampi(t.aggro_ms-dt,0,2200);
        int target=nearest_minion(t.owner,120,t.y,105);
        bool hero_in=enemy.hp>0&&absi(enemy.y-t.y)+absi(enemy.x-120)<105;
        t.shot_ms=clampi(t.shot_ms-dt,0,240);
        if(!hero_in)t.hero_shots=0;
        if(!t.attack_ms&&(target>=0||hero_in)){
            t.attack_ms=1200;t.shot_ms=240;
            if(hero_in&&(t.aggro_ms||target<0)){
                t.shot_x=enemy.x;t.shot_y=enemy.y;
                int damage=(t.max_hp==1800?45:65)+t.hero_shots*20;
                t.hero_shots=clampi(t.hero_shots+1,0,3);
                take_damage(1-t.owner,damage);
            }else{
                t.hero_shots=0;t.shot_x=minions[target].x;t.shot_y=minions[target].y;
                hurt_minion(-1,target,minions[target].kind==2?55:75);
            }
        }
    }
    for(int i=0;i<2;++i){auto& f=fighters[i];
        if(f.hp<=0){
            if(!f.respawn_ms)f.respawn_ms=5000;
            else {f.respawn_ms=clampi(f.respawn_ms-dt,0,5000);if(!f.respawn_ms){
                f.hp=max_hp(i);f.mana=max_mana(i);
                f.shield=f.stun_ms=f.slow_ms=0;f.x=120;f.y=i?160:800;
            }}continue;
        }
        if(absi(f.y-structures[i*3].y)<65){f.hp=clampi(f.hp+3,0,max_hp(i));f.mana=clampi(f.mana+2,0,max_mana(i));}
        if(f.attack_ms||f.stun_ms)continue;
        const auto& enemy=fighters[1-i];int range=duel_heroes[f.hero].attack_range;
        if((enemy.hp>0&&dist(f,enemy)<=range)||nearest_minion(i,f.x,f.y,range)>=0)continue;
        for(int j=(1-i)*3+2;j>=(1-i)*3;--j){auto& t=structures[j];
            if(t.hp>0&&absi(f.y-t.y)+absi(f.x-120)<=duel_heroes[f.hero].attack_range+30){
                basic_attack(i);break;
            }
        }
    }
    camera_y=clampi(fighters[0].y-190,0,640);
}
void FoxScene::hit(int owner,int amount,int stun,int slow){
    if(owner<0||owner>1||amount<=0||screen!=DUEL_MATCH)return;
    auto& defender=fighters[1-owner];auto& attacker=fighters[owner];
    if(defender.hp<=0||attacker.hp<=0)return;
    int before=defender.hp;
    int actual=take_damage(1-owner,amount);
    if(before>0&&defender.hp==0){attacker.gold+=120;++attacker.kills;}
    for(auto& t:structures)if(t.owner==1-owner&&t.hp>0&&absi(attacker.x-120)+absi(attacker.y-t.y)<105)t.aggro_ms=2200;
    attacker.damage_dealt+=actual;
    if(stun>defender.stun_ms)defender.stun_ms=stun;
    if(slow>defender.slow_ms)defender.slow_ms=slow;
    finish();
}
bool FoxScene::walkable(int x,int y) const{
    if(x<26||x>214||y<80||y>880)return false;
    const int radius=7;
    for(const auto& o:duel_map_objects)if(o.solid){
        int left=o.x+o.cx,top=o.y+o.cy;
        if(x+radius>left&&x-radius<left+o.cw&&y+radius>top&&y-radius<top+o.ch)return false;
    }
    for(const auto& t:structures)if(t.hp>0){
        int half=t.max_hp==1800?26:22;
        if(x+radius>120-half&&x-radius<120+half&&y+radius>t.y-10&&y-radius<t.y+2)return false;
    }
    return true;
}
void FoxScene::translate(int owner,int dx,int dy){
    auto& f=fighters[owner];int old_x=f.x,old_y=f.y;
    int n=absi(dx)>absi(dy)?absi(dx):absi(dy);
    int previous_x=0,previous_y=0;
    for(int i=1;i<=n;++i){int sx=dx*i/n,sy=dy*i/n;
        int nx=clampi(f.x+sx-previous_x,26,214),ny=clampi(f.y+sy-previous_y,80,880);
        // Sweep one pixel at a time; resolve axes separately so walking slides along walls.
        if(walkable(nx,f.y))f.x=nx;
        if(walkable(f.x,ny))f.y=ny;
        previous_x=sx;previous_y=sy;
    }
    int actual_x=f.x-old_x,actual_y=f.y-old_y;
    if(actual_x||actual_y){
        if(absi(actual_y)>=absi(actual_x))f.direction=actual_y<0?2:8;
        else {f.direction=actual_x<0?4:6;f.facing=actual_x<0;}
    }
    f.moving|=old_x!=f.x||old_y!=f.y;
}
void FoxScene::move(int owner,int dx,int dy){
    auto& f=fighters[owner];if(f.stun_ms||f.hp<=0)return;
    int step=f.slow_ms?1:move_speed(owner);
    translate(owner,dx*step,dy*step);
}
void FoxScene::bot_move(int dx,int dy){
    auto& bot=fighters[1];int step=bot.slow_ms?1:move_speed(1);
    if(dy&&!walkable(bot.x+dx*step,bot.y+dy*step)){
        int side=bot.x<=120?-1:1;
        if(walkable(bot.x+side*step,bot.y))move(1,side,0);
        else move(1,-side,0);
    }else move(1,dx,dy);
}
void FoxScene::heal(int owner){
    auto& f=fighters[owner];
    if(f.hp<=0||f.heal_ms||f.stun_ms||screen!=DUEL_MATCH||paused)return;
    int before=f.hp;f.hp=clampi(f.hp+300,0,max_hp(owner));f.healing+=f.hp-before;
    f.mana=clampi(f.mana+120,0,max_mana(owner));f.heal_ms=15000;
}
void FoxScene::cast(int skill){cast_for(0,skill);}
void FoxScene::cast_for(int owner,int skill){
    if(owner<0||owner>1||skill<0||skill>3||screen!=DUEL_MATCH||paused||result)return;
    auto& a=fighters[owner];auto& b=fighters[1-owner];const auto& h=duel_heroes[a.hero];
    if(a.hp<=0||a.stun_ms||a.cooldown[skill]||a.mana<h.cost[skill])return;
    a.mana-=h.cost[skill];a.cooldown[skill]=h.cd[skill];a.cast_ms=300;a.last_skill=skill;++a.casts;++a.skill_count;
    if(a.hero==0&&a.skill_count%3==0)a.shield=clampi(a.shield+50,0,300);
    int aim_x=b.x,aim_y=b.y;
    int farm=nearest_minion(owner,a.x,a.y,180);
    if((b.hp<=0||dist(a,b)>180)&&farm>=0){aim_x=minions[farm].x;aim_y=minions[farm].y;}
    int dx=aim_x-a.x,dy=aim_y-a.y,norm=absi(dx)>absi(dy)?absi(dx):absi(dy);if(!norm)norm=1;
    a.facing=dx<0;int d=dist(a,b);
    const int origin_x=a.x,origin_y=a.y;
    if(a.hero==1){
        if(skill==0&&d<65)hit(owner,180+skill_power(owner));
        if(skill==1)a.shield=clampi(a.shield+240,0,400);
        if(skill==2){translate(owner,dx*45/norm,dy*45/norm);
            if(dist(a,b)<60)hit(owner,100+skill_power(owner),600);}
        if(skill==3&&d<95)hit(owner,300+skill_power(owner),900);
    }else if(a.hero==2&&skill==1){
        translate(owner,-dx*35/norm,-dy*35/norm);
        a.shield=clampi(a.shield+90,0,300);
    }else if((a.hero==0&&skill==1)||skill==3){
        int range=skill==3?(a.hero==2?180:130):85;
        if(d<range)hit(owner,(skill==3?(a.hero==2?240:300):140)+skill_power(owner),0,skill==3?900:0);
    }else{
        int damage=a.hero==2?(skill==2?100:165):(skill==2?90:190);
        int stun=skill==2?(a.hero==2?650:1000):0;
        for(auto& p:projectiles)if(!p.active){p={a.x,a.y-18,dx*6/norm,dy*6/norm,1600,damage+skill_power(owner),stun,skill==0?350:0,owner,a.hero,skill,1};break;}
    }
    farm_cast(owner,skill);
    int dash=(a.hero==1&&skill==2)||(a.hero==2&&skill==1);
    spawn_effect(owner,a.hero,skill,origin_x,origin_y,dash?a.x:aim_x,dash?a.y:aim_y);
}
void FoxScene::bot_update(unsigned short dt){
    auto& bot=fighters[1];auto& player=fighters[0];const auto& h=duel_heroes[bot.hero];
    if(bot.stun_ms||bot.hp<=0)return;
    bot_think_ms-=dt;bool think=bot_think_ms<=0;
    if(think){bot_think_ms=350;++bot_decisions;}
    const int hp=bot.hp*100/max_hp(1),mp=bot.mana*100/max_mana(1);
    if(hp<30||mp<10||(player.hp>0&&dist(bot,player)<180&&hp<60&&player.hp*100/max_hp(0)>hp+20))bot_plan=BOT_RECOVER;
    // Stay in recovery until both resources are usable, instead of oscillating at 30% HP.
    if(bot_plan==BOT_RECOVER&&(hp<75||mp<50)){
        bot_goal_x=bot.x<=120?65:175;bot_goal_y=135;
        if(think&&hp<65&&!bot.heal_ms)heal(1);
        if(absi(bot.y-90)>=55||absi(bot.x-bot_goal_x)>4){
            bot_move(bot_goal_x>bot.x?1:(bot_goal_x<bot.x?-1:0),bot_goal_y>bot.y?1:(bot_goal_y<bot.y?-1:0));++bot_retreats;
        }
        if(think&&dist(bot,player)<85&&bot.hero!=0)cast_for(1,1);
        return;
    }
    auto cover=[&](int tower){
        for(const auto& m:minions)if(m.active&&m.owner==1&&absi(m.x-120)+absi(m.y-structures[tower].y)<105)return true;
        return false;
    };
    auto danger=[&](int x,int y){
        for(int j=0;j<3;++j)if(structures[j].hp>0&&absi(x-120)+absi(y-structures[j].y)<112&&
            (!cover(j)||structures[j].aggro_ms||hp<55))return true;
        return false;
    };
    // Protect the deepest threatened friendly objective first, even if a farm target is closer.
    int threat=-1,score=-10000;bool hero_threat=false;
    for(int j=3;j<6;++j)if(structures[j].hp>0){
        int priority=(6-j)*300;
        int d=absi(player.x-120)+absi(player.y-structures[j].y);
        if(player.hp>0&&d<145&&priority-d>score){score=priority-d;threat=j;hero_threat=true;}
        for(int i=0;i<48;++i){const auto& m=minions[i];if(!m.active||m.owner==1)continue;
            d=absi(m.x-120)+absi(m.y-structures[j].y);
            if(d<170&&priority-d+(m.kind==2?40:0)>score){score=priority-d+(m.kind==2?40:0);threat=i;hero_threat=false;}
        }
    }
    int enemy_distance=dist(bot,player);
    bool defend=threat>=0;
    bool favorable=hp+20>=player.hp*100/max_hp(0)||attack_power(1)>attack_power(0)*3/2||player.hp<attack_power(1)*3;
    bool duel=player.hp>0&&enemy_distance<210&&((defend&&hero_threat)||favorable)&&!danger(player.x,player.y);
    if(defend){bot_plan=BOT_DEFEND;bot_goal_x=hero_threat?player.x:minions[threat].x;bot_goal_y=hero_threat?player.y:minions[threat].y;}
    else if(duel){bot_plan=BOT_DUEL;bot_goal_x=player.x;bot_goal_y=player.y;}
    else{
        int farm=-1,best=10000;
        for(int i=0;i<48;++i){const auto& m=minions[i];if(!m.active||m.owner==1||danger(m.x,m.y))continue;
            int d=absi(bot.x-m.x)+absi(bot.y-m.y);
            int rank=d+(m.hp<=attack_power(1)?-80:0);
            if(d<260&&rank<best){best=rank;farm=i;}
        }
        if(farm>=0){bot_plan=BOT_FARM;bot_goal_x=minions[farm].x;bot_goal_y=minions[farm].y;}
        else{
            int tower=0;for(int j=2;j>=0;--j)if(structures[j].hp>0){tower=j;break;}
            bot_plan=BOT_PUSH;bot_goal_x=120;bot_goal_y=structures[tower].y;
            // Ranged heroes can poke from outside tower range; melee waits for wave cover.
            if(h.attack_range<100&&!cover(tower)&&absi(bot.x-120)+absi(bot.y-bot_goal_y)<150)bot_plan=BOT_WAIT;
        }
    }
    if(bot_plan==BOT_WAIT||danger(bot.x,bot.y)){
        if(danger(bot.x,bot.y))bot_move(bot.x<=120?-1:1,-1);
        return;
    }
    int dx=bot_goal_x>bot.x?1:(bot_goal_x<bot.x?-1:0),dy=bot_goal_y>bot.y?1:(bot_goal_y<bot.y?-1:0);
    int distance=absi(bot_goal_x-bot.x)+absi(bot_goal_y-bot.y);
    int desired=duel&&(!defend||hero_threat)?(bot.hero==1?30:(bot.hero==2?100:80)):h.attack_range;
    if(bot_plan==BOT_PUSH)desired=h.attack_range+20;
    if(duel&&(!defend||hero_threat)&&distance<desired-15)bot_move(-dx,-dy);
    else if(distance>desired+8){
        if(!danger(bot.x+dx*move_speed(1),bot.y+dy*move_speed(1)))bot_move(dx,dy);
    }
    if(!think)return;
    if(hp<55&&!bot.heal_ms)heal(1);
    if((bot_plan==BOT_FARM||(defend&&!hero_threat))&&distance<180){
        // Spend a basic skill to secure last hits; keep control/ultimate for a nearby hero.
        if(bot.hero!=1||distance<65)cast_for(1,0);
        if(bot.hero==0&&distance<85)cast_for(1,1);
        return;
    }
    if(!duel||enemy_distance>180)return;
    if(bot.hero==1){
        if(enemy_distance<65)cast_for(1,0);
        if(hp<65)cast_for(1,1);
        if(enemy_distance>55&&enemy_distance<140&&!danger(player.x,player.y))cast_for(1,2);
        if(enemy_distance<90)cast_for(1,3);
    }else{
        cast_for(1,0);
        if(bot.hero==0&&enemy_distance<85)cast_for(1,1);
        if(bot.hero==2&&enemy_distance<75)cast_for(1,1);
        if(enemy_distance<150)cast_for(1,2);
        if(enemy_distance<120)cast_for(1,3);
    }
}
void FoxScene::update(unsigned short dt){
    init();ui_ms+=dt;
    if(screen==DUEL_SPLASH){if(ui_ms>=1800){screen=DUEL_SELECT;ui_ms=0;}return;}
    if(screen!=DUEL_MATCH||paused||result)return;
    time_ms+=dt;
    for(auto& e:effects)e.life=clampi(e.life-dt,0,e.duration);
    lane_update(dt);
    for(auto& f:fighters){
        f.moving=0;
        for(int& c:f.cooldown)c=clampi(c-dt,0,7000);
        f.basic_ms=clampi(f.basic_ms-dt,0,200);
        f.attack_ms=clampi(f.attack_ms-dt,0,1000);f.stun_ms=clampi(f.stun_ms-dt,0,2000);
        f.slow_ms=clampi(f.slow_ms-dt,0,2000);f.cast_ms=clampi(f.cast_ms-dt,0,300);
        f.heal_ms=clampi(f.heal_ms-dt,0,15000);
    }
    army_update(dt);
    int dx=((held&2)?1:0)-((held&1)?1:0),dy=((held&8)?1:0)-((held&4)?1:0);
    move(0,dx,dy);bot_update(dt);
    if(held&16)basic_attack(0);
    if(screen!=DUEL_MATCH)return;
    regen_ms+=dt;
    if(regen_ms>=300){regen_ms-=300;
        for(int i=0;i<2;++i){auto& f=fighters[i];
            if(f.hp>0&&(f.items&(1<<5)))f.hp=clampi(f.hp+3,0,max_hp(i));
            f.mana=clampi(f.mana+4+((f.hero==2&&f.moving)?2:0),0,max_mana(i));}
    }
    for(int i=0;i<2&&screen==DUEL_MATCH;++i){auto& a=fighters[i];const auto& h=duel_heroes[a.hero];
        if(a.hp>0&&fighters[1-i].hp>0&&!a.stun_ms&&!a.attack_ms&&dist(a,fighters[1-i])<=h.attack_range){
            basic_attack(i);}
    }
    for(auto& p:projectiles)if(p.active&&screen==DUEL_MATCH){
        p.x+=p.vx;p.y+=p.vy;p.life-=dt;
        if(p.life<=0||p.x<0||p.x>239||p.y<0||p.y>960){p.active=0;continue;}
        bool hit_unit=false;
        for(int j=0;j<48;++j){const auto& m=minions[j];if(m.active&&m.owner!=p.owner&&absi(p.x-m.x)+absi(p.y-(m.y-9))<15){
            p.active=0;spawn_effect(p.owner,p.hero,p.skill,m.x,m.y,m.x,m.y,1);hurt_minion(p.owner,j,p.damage);hit_unit=true;break;}}
        if(hit_unit)continue;
        auto& target=fighters[1-p.owner];
        if(absi(p.x-target.x)+absi(p.y-(target.y-18))<20){p.active=0;spawn_effect(p.owner,p.hero,p.skill,target.x,target.y,target.x,target.y,1);hit(p.owner,p.damage,p.stun,p.slow);}
    }
    camera_y=clampi(fighters[0].y-190,0,640);
    finish();
}
static VxpeFontStyle ui_style(unsigned short color){
    VxpeFontStyle s=(color==0xFFE9||color==0xEDEB)?vaelora_font_accent:vaelora_font_body;
    if(color!=0xFFFF&&color!=0xFFB8&&color!=0xFFE9&&color!=0xEDEB)s.color565=color;
    return s;
}
void FoxScene::text(unsigned short* fb,int x,int y,const char* value,unsigned short color){
    auto s=ui_style(color);vxpe_font_draw(fb,240,320,x,y,value,&s,{0,0,240,320});
}
void FoxScene::centered(unsigned short* fb,int y,const char* value,unsigned short color){
    auto s=ui_style(color);vxpe_font_draw(fb,240,320,(240-vxpe_font_measure(value,&s))/2,y,value,&s,{0,0,240,320});
}
void FoxScene::title(unsigned short* fb,int y,const char* value,int scale){
    auto s=vaelora_font_title;if(scale>0)s.scale=(uint8_t)scale;
    vxpe_font_draw(fb,240,320,(240-vxpe_font_measure(value,&s))/2,y,value,&s,{0,0,240,320});
}
void FoxScene::numbers(unsigned short* fb,int x,int y,const char* value){
    vxpe_font_draw(fb,240,320,x,y,value,&vaelora_font_numbers,{0,0,240,320});
}
void FoxScene::hero_text(unsigned short* fb,int x,int y,const char* value,unsigned short color){
    auto s=vaelora_font_hero;if(color!=0x57F7&&color!=0xCF5F)s.color565=color;
    vxpe_font_draw(fb,240,320,x,y,value,&s,{0,0,240,320});
}
void FoxScene::bar(unsigned short* fb,int x,int y,int w,int value,int maximum,unsigned short color){
    vxpe2d_fill_rect(fb,240,320,x,y,w,5,0x1083);
    vxpe2d_fill_rect(fb,240,320,x+1,y+1,clampi(value,0,maximum)*(w-2)/maximum,3,color);
}
void FoxScene::sprite(unsigned short* fb,int hero,int row,int x,int y,int w,int h,int flip,int skin){
    VxpeBlit565 b={};b.src={(short)(hero*64),(short)(row*64),64,64};
    b.dst_x=x-w/2;b.dst_y=y-h;b.dst_w=w;b.dst_h=h;b.flip_x=flip;
    b.alpha=255;b.tint565=0xFFFF;
    if(skin)b.tint565=skin_tints[hero];
    if(screen==DUEL_MATCH&&row!=3){b.clip_x=0;b.clip_y=41;b.clip_w=240;b.clip_h=209;}
    b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&heroes,&b);
}
void FoxScene::skill_icon(unsigned short* fb,int hero,int skill,int x,int y,int size){
    VxpeBlit565 b={};b.src={(short)(skill*32),(short)(hero*32),32,32};
    b.dst_x=x;b.dst_y=y;b.dst_w=b.dst_h=size;b.alpha=255;b.tint565=0xFFFF;
    b.blend=VXPE_BLEND_ALPHA;vxpe2d_blit_a8(fb,240,320,&skill_art,&b);
}
void FoxScene::draw_menu(unsigned short* fb){
    vxpe2d_overlay_rect(fb,240,320,0,0,240,320,0x0862,210,VXPE_BLEND_ALPHA);
    title(fb,13,"VAELORA DUEL");centered(fb,13+vxpe_font_height(&vaelora_font_title)+7,"CHOOSE YOUR HERO",0xCF5F);
    for(int i=0;i<3;++i){int x=7+i*78;
        vxpe2d_fill_rect(fb,240,320,x,46,70,83,i==selected?0xB388:0x2945);
        vxpe2d_fill_rect(fb,240,320,x+1,47,68,81,0x1083);
        sprite(fb,i,3,x+35,111,62,62,0,i==selected?selected_skin:0);hero_text(fb,x+14,117,duel_heroes[i].name,i==selected?0xFFE9:0xAD55);
    }
    const auto& h=duel_heroes[selected];char value[48];
    centered(fb,142,h.role,h.color);
    snprintf(value,sizeof(value),"HP %d  MP %d  SPEED %d",h.max_hp,h.max_mana,h.speed);numbers(fb,(240-vxpe_font_measure(value,&vaelora_font_numbers))/2,155,value);
    centered(fb,168,h.passive,0xAD55);
    static const char* keys[]={"5","7","9","0"};
    for(int i=0;i<4;++i){int y=185+i*12;skill_icon(fb,selected,i,6,y-1,10);text(fb,21,y,keys[i],0xFFE9);text(fb,37,y,h.skills[i],0xFFFF);
        snprintf(value,sizeof(value),"%d.%ds",h.cd[i]/1000,(h.cd[i]%1000)/100);numbers(fb,189,y,value);}
    snprintf(value,sizeof(value),"BOT: %s  [2/8]",duel_heroes[bot_selected].name);centered(fb,240,value,0xCF5F);
    snprintf(value,sizeof(value),"7 %s  9 BOT SKIN",skin_names[selected][selected_skin]);centered(fb,225,value,0xFFE9);
    vxpe2d_fill_rect(fb,240,320,25,258,190,24,0x2945);centered(fb,266,"5 / OK - START DUEL",0xFFE9);
    centered(fb,291,"4/6 HERO  1 HELP  BACK EXIT",0xAD55);
    if(help){vxpe2d_overlay_rect(fb,240,320,7,42,226,242,0x0862,252,VXPE_BLEND_ALPHA);
        centered(fb,58,"SOLO / DESTROY ENEMY CORE",0xFFE9);
        const char* lines[]={"2468 MOVE / ARROWS","LEFT SOFTKEY: HOLD ATTACK","5 7 9 0: FOUR SKILLS","1: RECOVER HP AND MANA","*: PAUSE  3: REMATCH","BACK: HERO SELECTION","# SHOP / GOLD FROM LAST HIT","FOLLOW MINIONS TO PUSH","1 CLOSE / 5 START"};
        for(int i=0;i<9;++i)text(fb,17,82+i*20,lines[i],0xFFFF);
    }
}
void FoxScene::draw_map_object(unsigned short* fb,int index){
    const auto& o=duel_map_objects[index];int y=o.y-camera_y;
    if(y+o.h<41||y>=250)return;
    VxpeBlit565 art={};art.src={(short)((o.kind%3)*64),(short)((o.kind/3)*80),64,80};
    art.dst_x=o.x;art.dst_y=y;art.dst_w=o.w;art.dst_h=o.h;
    art.alpha=255;art.tint565=0xFFFF;art.blend=VXPE_BLEND_ALPHA;
    art.clip_x=0;art.clip_y=41;art.clip_w=240;art.clip_h=209;
    vxpe2d_blit_a8(fb,240,320,&environment_art,&art);
}
void FoxScene::draw_structure(unsigned short* fb,int index){
    const auto& t=structures[index];int y=t.y-camera_y;if(y<41||y>330)return;
        unsigned short c=t.owner?0xF980:0x57F7;
        int core=t.max_hp==1800,col=t.hp?t.owner:2;
        VxpeBlit565 art={};art.src={(short)(col*64),(short)(core*80),64,80};
        art.dst_w=core?68:56;art.dst_h=core?80:70;
        art.dst_x=120-art.dst_w/2;art.dst_y=y-art.dst_h+2;
        art.alpha=255;art.tint565=0xFFFF;art.blend=VXPE_BLEND_ALPHA;
        art.clip_x=0;art.clip_y=41;art.clip_w=240;art.clip_h=209;
        vxpe2d_blit_a8(fb,240,320,&structure_art,&art);
        if(t.hp){int label_y=y-(core?75:81);
            if(label_y>=41&&label_y<=233){
                bar(fb,95,label_y+10,50,t.hp,t.max_hp,c);
                text(fb,101,label_y,core?"CORE":"TOWER",c);
            }
        }else text(fb,97,y-14,"RUINS",0xAD55);

}
void FoxScene::draw_fighter(unsigned short* fb,int i){
    const auto& f=fighters[i];int y=f.y-camera_y;
    if(f.hp<=0||y<41||y>310)return;
    const auto& h=duel_heroes[f.hero];
        vxpe2d_overlay_rect(fb,240,320,f.x-17,y-3,34,4,0,130,VXPE_BLEND_ALPHA);
        if(f.cast_ms||f.basic_ms||f.moving)draw_action(fb,i,f.x,y);
        else if(f.direction==2||f.direction==8)draw_action(fb,i,f.x,y);
        else sprite(fb,f.hero,0,f.x,y,60,60,f.facing,f.skin);
        unsigned short team=i?0xFA08:0x57F7;
        vxpe2d_fill_rect(fb,240,320,f.x-14,y-1,28,2,team);
        if(y-77>=41&&(!i || dist(fighters[i],fighters[0])>65))
            hero_text(fb,clampi(f.x-vxpe_font_measure(h.name,&vaelora_font_hero)/2,1,200),y-77,h.name,team);
        if(y-67>=41&&(!i || dist(fighters[i],fighters[0])>65)){
            bar(fb,f.x-25,y-67,50,f.hp,max_hp(i),i?0xF980:0x77E5);
            bar(fb,f.x-25,y-61,50,f.mana,max_mana(i),0x2DFF);
            if(f.shield)bar(fb,f.x-25,y-55,50,f.shield,400,0xFFE9);
        }
        if(f.stun_ms)text(fb,f.x-12,y-86,"STUN",0xFFE9);

}
void FoxScene::draw_match(unsigned short* fb){
    // Initialize only HUD bands; the scrolling world below replaces the middle.
    memcpy(fb,duel_lane_ground+12,41*240*sizeof(unsigned short));
    memcpy(fb+250*240,duel_lane_ground+12+250*240*2,70*240*sizeof(unsigned short));
    // Scroll the original terrain in world coordinates, retaining a native QVGA framebuffer.
    for(int y=41;y<250;++y){int sy=(y+camera_y)%320;
        // Existing opaque VXA8 terrain stores RGB565 immediately after its 12-byte header.
        const unsigned char* row=duel_lane_ground+12+sy*240*2;
        memcpy(fb+y*240,row,240*sizeof(unsigned short));
    }
    struct Node {int depth,kind,index;};Node nodes[duel_map_count+56];int count=0;
    for(int i=0;i<duel_map_count;++i){const auto& o=duel_map_objects[i];if(o.y+o.h-camera_y>=41&&o.y-camera_y<250)nodes[count++]={o.y+o.h,0,i};}
    for(int i=0;i<6;++i)if(structures[i].y-camera_y>=41&&structures[i].y-camera_y<330)nodes[count++]={structures[i].y,1,i};
    for(int i=0;i<48;++i)if(minions[i].active&&minions[i].y-camera_y>=41&&minions[i].y-camera_y<=285)nodes[count++]={minions[i].y,3,i};
    for(int i=0;i<2;++i)if(fighters[i].hp>0&&fighters[i].y-camera_y>=41&&fighters[i].y-camera_y<=310)nodes[count++]={fighters[i].y,2,i};
    for(int i=1;i<count;++i){Node n=nodes[i];int j=i;while(j>0&&nodes[j-1].depth>n.depth){nodes[j]=nodes[j-1];--j;}nodes[j]=n;}
    for(int i=0;i<count;++i){const auto& n=nodes[i];
        if(n.kind==0)draw_map_object(fb,n.index);else if(n.kind==1)draw_structure(fb,n.index);else if(n.kind==2)draw_fighter(fb,n.index);else draw_minion(fb,n.index);
    }
    for(const auto& t:structures)if(t.hp>0&&t.shot_ms){
        int y=t.y-camera_y-40,ty=t.shot_y-camera_y-18;
        unsigned short color=t.owner?0xFA08:0x57F7;
        for(int j=0;j<=20;++j){int px=120+(t.shot_x-120)*j/20,py=y+(ty-y)*j/20;
            if(py>=41&&py+2<=250)vxpe2d_fill_rect(fb,240,320,px,py,2,2,color);}
    }
    draw_skill_effects(fb);
    // World effects above replace screen-space particle rendering during lane play.
    vxpe2d_overlay_rect(fb,240,320,0,0,240,24,0x0862,242,VXPE_BLEND_ALPHA);
    text(fb,7,4,"VAELORA DUEL",0xEDEB);char value[64];
    snprintf(value,sizeof(value),"%02d:%02d",time_ms/60000,(time_ms/1000)%60);numbers(fb,233-vxpe_font_measure(value,&vaelora_font_numbers),4,value);
    snprintf(value,sizeof(value),"CORE %d VS %d",structures[0].hp,structures[3].hp);text(fb,7,15,value,0xCF5F);
    vxpe2d_overlay_rect(fb,240,320,0,24,240,17,0x0862,225,VXPE_BLEND_ALPHA);
    const auto& bot=fighters[1];
    static const char* plans[]={"FARM","DUEL","DEFEND","PUSH","RECOVER","WAIT"};
    snprintf(value,sizeof(value),"BOT %s",plans[bot_plan]);text(fb,7,27,value,0xFA08);
    bar(fb,80,28,101,bot.hp,max_hp(1),0xF980);
    snprintf(value,sizeof(value),"A%d M%d",attack_power(1),bot.mana);text(fb,155,15,value,0xFFE9);
    snprintf(value,sizeof(value),"%d",bot.hp);numbers(fb,188,27,value);
    const auto& p=fighters[0];const auto& h=duel_heroes[p.hero];
    vxpe2d_overlay_rect(fb,240,320,3,250,234,67,0x0862,248,VXPE_BLEND_ALPHA);
    vxpe2d_fill_rect(fb,240,320,3,250,234,1,0xB388);
    sprite(fb,p.hero,3,26,291,40,40,0,p.skin);text(fb,10,294,h.name,0xFFE9);
    static const char* keys[]={"5","7","9","0"};
    for(int i=0;i<4;++i){int x=51+i*44;
        vxpe2d_fill_rect(fb,240,320,x,255,40,29,0xB388);
        vxpe2d_fill_rect(fb,240,320,x+1,256,38,27,0x18C4);
        skill_icon(fb,p.hero,i,x+2,257,24);
        vxpe2d_fill_rect(fb,240,320,x+28,273,10,10,0x0862);
        text(fb,x+30,275,keys[i],0xFFE9);
        if(p.cooldown[i]){vxpe2d_overlay_rect(fb,240,320,x+1,256,38,27,0,160,VXPE_BLEND_ALPHA);
            snprintf(value,sizeof(value),"%d",(p.cooldown[i]+999)/1000);numbers(fb,x+10,264,value);}
    }
    bar(fb,51,287,172,p.hp,max_hp(0),0x4DA4);
    snprintf(value,sizeof(value),"%d / %d",p.hp,max_hp(0));numbers(fb,102,294,value);
    bar(fb,51,303,172,p.mana,max_mana(0),0x2BFF);
    snprintf(value,sizeof(value),"MP %d/%d",p.mana,max_mana(0));numbers(fb,105,303,value);
    if(p.hp<=0)snprintf(value,sizeof(value),"RESPAWN %ds",(p.respawn_ms+999)/1000);
    else snprintf(value,sizeof(value),"G%d F%d LSK ATK #SHOP",p.gold,p.last_hits);
    text(fb,51,311,value,0xEDEB);
    if(shop_open)draw_shop(fb);
    if(paused||screen==DUEL_RESULT){
        vxpe2d_overlay_rect(fb,240,320,0,24,240,226,0,205,VXPE_BLEND_ALPHA);
        title(fb,78,paused?"PAUSED":(result==2?"DRAW":(result>0?"VICTORY":"DEFEAT")),2);
        if(!paused){snprintf(value,sizeof(value),"DAMAGE %d  BOT %d",fighters[0].damage_dealt,fighters[1].damage_dealt);centered(fb,112,value,0xFFFF);
            snprintf(value,sizeof(value),"CASTS %d  BOT %d",fighters[0].casts,fighters[1].casts);centered(fb,130,value,0xFFFF);
            centered(fb,175,"5 REMATCH / BACK HEROES",0xCF5F);
        }else centered(fb,140,"* RESUME / 3 REMATCH",0xCF5F);
    }
}
void FoxScene::draw(unsigned short* fb){
    init();if(!fb)return;VxpeBlit565 b={};b.dst_w=240;b.dst_h=320;b.alpha=255;b.tint565=0xFFFF;b.blend=VXPE_BLEND_COPY;
    if(screen==DUEL_MATCH||screen==DUEL_RESULT){draw_match(fb);return;}
    vxpe2d_blit_a8(fb,240,320,&background,&b);
    if(screen==DUEL_SPLASH){
        vxpe2d_overlay_rect(fb,240,320,0,0,240,320,0x0862,216,VXPE_BLEND_ALPHA);
        b={};b.dst_x=20;b.dst_y=76;b.dst_w=200;b.dst_h=114;b.alpha=255;b.tint565=0xFFFF;b.blend=VXPE_BLEND_ALPHA;
        vxpe2d_blit_a8(fb,240,320,&logo,&b);
        centered(fb,214,"THREE HEROES. ONE DUEL.",0xCF5F);
        centered(fb,262,"PRESS 5 TO CONTINUE",0xEDEB);
        bar(fb,45,289,150,clampi(ui_ms,0,1800),1800,0x57F7);
    }else if(screen==DUEL_SELECT)draw_menu(fb);
    else draw_match(fb);
}
