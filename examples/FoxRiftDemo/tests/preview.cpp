#include "scene.h"
#include <assert.h>
#include <stdio.h>
static void step(FoxScene& s,int n){for(int i=0;i<n;++i)s.update();}
static void save(FoxScene& s,const char* name){
    unsigned short pixels[240*320+2]={};pixels[0]=pixels[240*320+1]=0xCAFE;
    s.draw(pixels+1);assert(pixels[0]==0xCAFE&&pixels[240*320+1]==0xCAFE);
    FILE* f=fopen(name,"wb");assert(f);fprintf(f,"P6\n240 320\n255\n");
    for(int i=1;i<=240*320;++i){unsigned short c=pixels[i];unsigned char rgb[3]={(unsigned char)((c>>11)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(rgb,1,3,f);}fclose(f);
}
static void setup(FoxScene& s,int hero,int enemy=1){s.selected=hero;s.bot_selected=enemy;s.start_match();s.fighters[1].x=s.fighters[0].x+50;s.fighters[1].y=s.fighters[0].y;}
int main(){
    static FoxScene s;s.init();assert(s.screen==DUEL_SPLASH);save(s,"01_splash.ppm");
    step(s,55);assert(s.screen==DUEL_SELECT);save(s,"02_select.ppm");
    s.hold(6,true);assert(s.selected==1);s.hold(6,false);save(s,"03_torvan_select.ppm");
    s.input(1);assert(s.help);save(s,"04_help.ppm");s.input(1);
    s.hold(8,true);assert(s.bot_selected==2);s.hold(8,false);s.input(5);assert(s.screen==DUEL_MATCH&&s.fighters[0].hero==1&&s.fighters[1].hero==2);
    int x=s.fighters[0].x;s.hold(6,true);step(s,5);s.hold(6,false);assert(s.fighters[0].x>x);
    s.input(10);int time=s.time_ms,bot_casts=s.fighters[1].casts;step(s,20);assert(s.time_ms==time&&s.fighters[1].casts==bot_casts);save(s,"05_pause.ppm");s.input(10);
    setup(s,0);int mana=s.fighters[0].mana;s.cast(0);assert(s.fighters[0].mana==mana-40);s.cast(0);assert(s.fighters[0].mana==mana-40);step(s,12);assert(s.fighters[0].damage_dealt>100);
    setup(s,0,0);s.cast(0);s.cast(1);s.cast(2);assert(s.fighters[0].shield==50);save(s,"06_velin.ppm");
    setup(s,1);s.cast(1);assert(s.fighters[0].shield==240);int hp=s.fighters[0].hp;s.hit(1,100);assert(s.fighters[0].hp==hp&&s.fighters[0].shield==155);
    int before=s.fighters[0].x;s.cast(2);assert(s.fighters[0].x>before&&s.fighters[1].stun_ms>0);save(s,"07_torvan.ppm");
    setup(s,2);before=s.fighters[0].x;s.cast(1);assert(s.fighters[0].x<before);s.cast(2);step(s,10);assert(s.fighters[1].stun_ms>0);save(s,"08_nimara.ppm");
    setup(s,0);s.fighters[0].mana=0;s.cast(0);assert(s.fighters[0].casts==0);s.fighters[0].stun_ms=500;s.fighters[0].mana=600;s.cast(0);assert(s.fighters[0].casts==0);
    // A projectile aims at the original position and can miss a moving target.
    setup(s,0);s.cast(0);s.fighters[1].y=112;s.fighters[1].stun_ms=1900;
    step(s,20);assert(s.fighters[0].damage_dealt==0);
    // Ranger passive requires actual movement, for player and bot alike.
    setup(s,2);s.fighters[1].stun_ms=1900;s.fighters[0].mana=100;s.regen_ms=267;
    s.hold(6,true);s.update();s.hold(6,false);assert(s.fighters[0].mana==106);
    s.regen_ms=267;s.update();assert(s.fighters[0].mana==110);
    // Recovery belongs to the shared combat rules; the bot uses it at low HP.
    setup(s,0,2);s.fighters[1].hp=100;s.update();assert(s.fighters[1].healing==300&&s.fighters[1].heal_ms==15000);
    setup(s,1);s.fighters[0].hp=500;s.input(1);assert(s.fighters[0].hp==800);s.input(1);assert(s.fighters[0].hp==800);
    for(int hero=0;hero<3;++hero){setup(s,(hero+1)%3,hero);s.fighters[0].y=s.fighters[1].y=480;step(s,60);assert(s.bot_decisions>0&&s.fighters[1].casts>0);s.fighters[1].hp=100;s.fighters[1].heal_ms=15000;step(s,12);assert(s.bot_retreats>0);}
    setup(s,0);s.hit(0,10000);assert(s.screen==DUEL_MATCH&&s.fighters[1].hp==0);
    step(s,154);assert(s.fighters[1].hp>0&&s.fighters[1].y<250);
    s.damage_structure(0,3,9999);assert(s.structures[3].hp==1800);
    s.damage_structure(0,4,9999);assert(s.structures[4].hp==900);
    s.damage_structure(0,5,9999);s.damage_structure(0,4,9999);s.damage_structure(0,3,9999);
    assert(s.screen==DUEL_RESULT&&s.result==1);save(s,"09_victory.ppm");s.input(5);
    s.damage_structure(1,2,9999);s.damage_structure(1,1,9999);s.damage_structure(1,0,9999);
    assert(s.screen==DUEL_RESULT&&s.result==-1);save(s,"10_defeat.ppm");s.input(-1);
    s.input(7);s.input(9);assert(s.selected_skin==1&&s.bot_skin==1);s.start_match();
    assert(s.fighters[0].skin==1&&s.fighters[1].skin==1);
    int initial=s.camera_y;s.hold(2,true);step(s,80);s.hold(2,false);assert(s.camera_y<initial);save(s,"12_lane_skin.ppm");
    s.time_ms=299999;s.update();assert(s.result==2);save(s,"11_draw.ppm");
    // Solid world geometry, grass passage, swept skills and bot navigation.
    s.selected=0;s.start_match();s.fighters[0].x=50;s.fighters[0].y=280;
    s.fighters[1].x=200;s.fighters[1].y=100;s.fighters[1].stun_ms=1900;
    assert(s.walkable(50,280)&&!s.walkable(50,300));
    s.hold(8,true);step(s,12);s.hold(8,false);assert(s.fighters[0].y==285&&s.walkable(s.fighters[0].x,s.fighters[0].y));
    s.fighters[0].x=202;s.fighters[0].y=575;s.hold(6,true);s.hold(8,true);step(s,8);s.hold(6,false);s.hold(8,false);
    assert(s.fighters[0].x==203&&s.fighters[0].y>575); // Slide along vertical wall.
    s.fighters[0].x=40;s.fighters[0].y=365;s.hold(8,true);step(s,8);s.hold(8,false);assert(s.fighters[0].y==381); // Tall grass is walkable.
    s.selected=1;s.start_match();s.fighters[0].x=50;s.fighters[0].y=280;s.fighters[1].x=50;s.fighters[1].y=340;
    s.cast(2);assert(s.fighters[0].y==285); // A 45px charge cannot tunnel through wall.
    s.selected=2;s.start_match();s.fighters[0].x=50;s.fighters[0].y=280;s.fighters[1].x=50;s.fighters[1].y=240;
    s.cast(1);assert(s.fighters[0].y==285); // Backward wind dash also sweeps collision.
    s.selected=0;s.bot_selected=1;s.start_match();s.fighters[0].x=65;s.fighters[0].y=850;s.fighters[0].stun_ms=1900;
    s.fighters[1].x=120;s.fighters[1].y=190;step(s,140);
    assert(s.fighters[1].y>240&&s.walkable(s.fighters[1].x,s.fighters[1].y)); step(s,200); assert(s.fighters[1].y>240); // Bot gets around its own tower.
    s.start_match();assert(!s.walkable(120,350));s.damage_structure(0,5,900);assert(s.walkable(120,350));
    for(int y=80;y<=880;y+=80){s.fighters[0].x=82;s.fighters[0].y=y;s.camera_y=y<190?0:(y>830?640:y-190);char name[40];snprintf(name,sizeof(name),"19_world_%03d.ppm",y);save(s,name);}
    // Export ready skill icons for all heroes and both teams' structures for visual review.
    for(int hero=0;hero<3;++hero){
        s.selected=hero;s.selected_skin=0;s.start_match();s.fighters[0].x=55;s.fighters[0].y=740;
        s.camera_y=560;char name[40];snprintf(name,sizeof(name),"13_icons_%d.ppm",hero);save(s,name);
    }
    s.fighters[0].y=835;s.camera_y=640;save(s,"14_blue_core.ppm");
    s.fighters[0].y=370;s.camera_y=180;save(s,"15_red_tower.ppm");
    s.structures[5].hp=0;save(s,"16_tower_ruins.ppm");
    s.fighters[0].y=150;s.camera_y=0;save(s,"17_red_core.ppm");
    s.structures[3].hp=0;save(s,"18_core_ruins.ppm");
    // Render animated ability sequences with the bot and basic attacks held still.
    for(int hero=0;hero<3;++hero)for(int skill=0;skill<4;++skill){
        s.selected=hero;s.bot_selected=1;s.selected_skin=0;s.start_match();
        s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].x=150;s.fighters[1].y=500;s.camera_y=310;
        s.fighters[1].stun_ms=1900;s.cast(skill);
        bool spawned=false;for(const auto& e:s.effects)if(e.life)spawned=true;assert(spawned);
        int effect_life=s.effects[0].life;s.input(10);step(s,5);assert(s.effects[0].life==effect_life);s.input(10);
        for(int frame=0;frame<40;++frame){
            s.fighters[1].stun_ms=1900;s.fighters[0].attack_ms=s.fighters[1].attack_ms=999;
            if(frame%4==0){char name[64];snprintf(name,sizeof(name),"fx_%d_%d_%02d.ppm",hero,skill,frame/4);save(s,name);}
            s.update();
        }
        for(int frame=0;frame<20;++frame){s.fighters[1].stun_ms=1900;s.fighters[0].attack_ms=s.fighters[1].attack_ms=999;s.update();}
        for(const auto& e:s.effects)assert(e.life==0);
        s.restart();for(const auto& e:s.effects)assert(e.life==0);for(const auto& p:s.projectiles)assert(!p.active);
    }
    // Binding impact is generated only by a real projectile collision.
    setup(s,0);s.fighters[1].stun_ms=1900;s.cast(2);step(s,12);
    bool bound=false;for(const auto& e:s.effects)if(e.life&&e.impact&&e.skill==2)bound=true;assert(bound);
    // Clipped VFX cannot bleed through translucent HUD panels at viewport boundaries.
    s.selected=0;s.start_match();s.cast(3);s.effects[0].x=0;s.effects[0].y=s.camera_y+42;
    unsigned short with_fx[240*320],without_fx[240*320];s.draw(with_fx);
    for(auto& e:s.effects)e.life=0;
    for(auto& p:s.projectiles)p.active=0;
    s.draw(without_fx);
    for(int y=0;y<320;++y)if(y<41||y>=250)for(int x=0;x<240;++x)assert(with_fx[y*240+x]==without_fx[y*240+x]);
    // Symmetric minion waves and periodic siege carts.
    s.selected=0;s.start_match();s.spawn_wave();int blue=0,red=0,carts=0;
    for(const auto& m:s.minions)if(m.active){m.owner?++red:++blue;if(m.kind==2)++carts;}
    assert(blue==3&&red==3&&carts==0);s.spawn_wave();s.spawn_wave();carts=0;
    for(const auto& m:s.minions)if(m.active&&m.kind==2)++carts;
    assert(carts==2);
    // Exact last-hit bounty, no duplicate reward and no gold from allied kills.
    s.start_match();s.minions[0]={1,1,0,150,500,20,220,0,0,0};int money=s.fighters[0].gold;
    s.hurt_minion(0,0,30);assert(s.fighters[0].gold==money+32&&s.fighters[0].last_hits==1);
    s.hurt_minion(0,0,30);assert(s.fighters[0].gold==money+32);
    s.minions[1]={1,0,0,150,500,20,220,0,0,0};s.hurt_minion(0,1,30);assert(s.minions[1].hp==20);
    // Skills can farm a wave, and ranged spells acquire minions when the hero is distant.
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].x=179;s.fighters[1].y=100;
    s.minions[0]={1,1,0,140,500,100,220,0,0,0};s.minions[1]={1,1,0,150,500,100,220,0,0,0};s.cast(1);
    assert(s.fighters[0].last_hits==2&&s.fighters[0].gold==184);
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].x=179;s.fighters[1].y=100;s.fighters[1].stun_ms=1900;
    s.minions[0]={1,1,1,150,500,100,150,1000,0,0};s.fighters[0].attack_ms=999;s.cast(0);step(s,12);assert(s.fighters[0].last_hits==1);
    // Shop uses one wallet, unique items and persistent stats through death/respawn.
    s.start_match();s.input(11);assert(s.shop_open);s.input(5);assert(s.fighters[0].gold==0&&s.attack_power(0)==48);
    assert(!s.buy_item(0,0)&&!s.buy_item(0,1));s.fighters[0].gold=1000;
    for(int i=1;i<6;++i)assert(s.buy_item(0,i));
    assert(s.fighters[0].items==63&&s.fighters[0].gold==300&&s.max_hp(0)==1480&&s.max_mana(0)==760&&s.move_speed(0)==3&&s.attack_delay(0)==670&&s.skill_power(0)==25);
    save(s,"20_equipment_shop.ppm");s.input(11);hp=s.fighters[0].hp;s.take_damage(0,100);assert(s.fighters[0].hp==hp-88);
    s.hit(1,10000);step(s,155);assert(s.fighters[0].hp==s.max_hp(0)&&s.fighters[0].items==63);
    // Towers shoot minions first, but attacking a defended hero draws tower aggro.
    s.start_match();s.fighters[0].x=86;s.fighters[0].y=320;s.fighters[0].attack_ms=999;
    s.fighters[1].x=150;s.fighters[1].y=330;s.fighters[1].attack_ms=999;
    s.minions[0]={1,0,0,86,330,220,220,999,0,0};hp=s.fighters[0].hp;s.lane_update(33);
    assert(s.fighters[0].hp==hp&&s.minions[0].hp==145);s.hit(0,10);s.structures[5].attack_ms=0;s.lane_update(33);assert(s.fighters[0].hp<hp);
    // A siege cart's cannon damages the next unlocked tower.
    s.start_match();s.fighters[0].x=65;s.fighters[0].y=850;s.minions[0]={1,0,2,86,330,480,480,0,0,0};s.army_update(33);assert(s.structures[5].hp==804);
    s.camera_y=200;s.fighters[0].x=100;s.fighters[0].y=390;s.minions[1]={1,0,0,90,375,220,220,0,0,1};s.minions[2]={1,1,0,150,385,220,220,0,0,1};s.minions[3]={1,1,1,150,415,150,150,0,0,0};s.minions[0].x=105;s.minions[0].y=425;save(s,"21_minion_siege.ppm");
    s.start_match();for(int i=0;i<12;++i)s.spawn_wave();int count=0;for(const auto& m:s.minions)if(m.active)++count;assert(count==48);save(s,"22_waves.ppm");
    s.input(10);int waves=s.wave_count,gold=s.fighters[0].gold;step(s,100);assert(s.wave_count==waves&&s.fighters[0].gold==gold);s.input(10);
    s.restart();assert(s.fighters[0].items==0&&s.fighters[0].gold==120&&s.wave_count==0);for(const auto& m:s.minions)assert(!m.active);
    // Basic attack targets vulnerable enemy minions and the bot buys according to its archetype.
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;s.fighters[1].stun_ms=1900;s.minions[0]={1,1,0,120,500,5,220,999,0,0};s.army_update(33);assert(s.fighters[0].last_hits==1&&s.fighters[0].basic_ms>0);
    s.bot_selected=2;s.start_match();s.fighters[1].gold=150;s.army_update(33);assert(s.fighters[1].items==(1<<4)&&s.fighters[1].gold==0);
    // End-to-end lane economy over multiple live waves.
    s.selected=0;s.bot_selected=2;s.start_match();
    for(int frame=0;frame<1900&&s.screen==DUEL_MATCH;++frame){s.update();if(frame%500==0)save(s,"23_live_waves.ppm");}
    assert(s.wave_count>=5&&s.fighters[1].gold>=0&&s.fighters[1].items!=0);
    for(const auto& m:s.minions)if(m.active)assert(m.hp>0&&m.x>=26&&m.x<=214&&m.y>=80&&m.y<=880);
    // Explicit basic attack spends no mana, respects cadence and uses last-hit rewards.
    setup(s,0,0);int basic_hp=s.fighters[1].hp,basic_mana=s.fighters[0].mana;
    s.input(12);assert(s.fighters[1].hp==basic_hp-34&&s.fighters[0].mana==basic_mana);
    assert(s.fighters[0].basic_ms==200&&s.fighters[0].attack_ms==850);
    s.input(12);assert(s.fighters[1].hp==basic_hp-34);
    for(int cd:s.fighters[0].cooldown)assert(cd==0);
    s.start_match();s.fighters[0].x=100;s.fighters[0].y=500;
    s.minions[0]={1,1,0,120,500,5,220,999,0,0};s.input(12);
    assert(!s.minions[0].active&&s.fighters[0].last_hits==1&&s.fighters[0].gold==152);
    s.start_match();s.hold(12,true);s.update();assert(s.fighters[0].basic_ms==200);
    step(s,26);assert(s.fighters[0].basic_ms==200);s.hold(12,false);assert(!(s.held&16));
    s.input(10);s.fighters[0].attack_ms=0;s.input(12);assert(s.fighters[0].attack_ms==0);s.input(10);
    s.input(11);s.input(12);assert(s.fighters[0].attack_ms==0);s.input(11);
    s.fighters[0].stun_ms=500;assert(!s.basic_attack(0));s.fighters[0].stun_ms=0;
    s.fighters[0].hp=0;assert(!s.basic_attack(0));
    // Running north and south changes actual facing; horizontal movement stays lateral.
    for(int hero=0;hero<3;++hero){
        s.selected=hero;s.start_match();int y0=s.fighters[0].y;
        s.hold(2,true);s.update();s.hold(2,false);
        assert(s.fighters[0].y<y0&&s.fighters[0].direction==2);
        char file[48];snprintf(file,sizeof(file),"24_north_%d.ppm",hero);save(s,file);
        s.hold(8,true);s.update();s.hold(8,false);assert(s.fighters[0].direction==8);
        snprintf(file,sizeof(file),"25_south_%d.ppm",hero);save(s,file);
        s.hold(6,true);s.update();s.hold(6,false);assert(s.fighters[0].direction==6&&!s.fighters[0].facing);
        s.hold(4,true);s.update();s.hold(4,false);assert(s.fighters[0].direction==4&&s.fighters[0].facing);
    }
    // Towers hit either opposing hero, escalate sustained dives, and reset outside range.
    s.selected=0;s.bot_selected=0;s.start_match();s.fighters[0].x=86;s.fighters[0].y=310;
    before=s.fighters[0].hp;s.lane_update(33);
    assert(s.fighters[0].hp==before-65&&s.structures[5].hero_shots==1&&s.structures[5].shot_ms>0);
    s.structures[5].attack_ms=0;before=s.fighters[0].hp;s.lane_update(33);assert(s.fighters[0].hp==before-85);
    s.fighters[0].y=500;s.lane_update(33);assert(s.structures[5].hero_shots==0);
    s.fighters[1].x=86;s.fighters[1].y=570;s.structures[2].attack_ms=0;
    before=s.fighters[1].hp;s.lane_update(33);assert(s.fighters[1].hp==before-65);
    s.camera_y=150;save(s,"27_tower_fire.ppm");
    // Recovery applies even when the enemy hero is distant; maintain it until replenished.
    s.start_match();s.fighters[1].x=65;s.fighters[1].y=500;s.fighters[1].hp=100;s.fighters[1].heal_ms=15000;
    s.update();assert(s.bot_plan==BOT_RECOVER&&s.bot_goal_y==135&&s.bot_retreats>0);
    s.fighters[1].hp=s.max_hp(1)/2;s.update();assert(s.bot_plan==BOT_RECOVER);
    s.fighters[1].hp=s.max_hp(1);s.fighters[1].mana=s.max_mana(1);s.update();assert(s.bot_plan!=BOT_RECOVER);
    // A siege threat at the core overrides a nearby lane farm opportunity.
    s.start_match();s.fighters[0].y=850;s.fighters[1].x=65;s.fighters[1].y=500;
    s.minions[0]={1,0,2,85,140,480,480,999,0,0};s.minions[1]={1,0,0,85,500,220,220,999,0,0};
    s.update();assert(s.bot_plan==BOT_DEFEND&&s.bot_goal_y==140);
    // With no objective threat, select a lane wave for farm.
    s.start_match();s.fighters[0].y=850;s.fighters[1].x=65;s.fighters[1].y=500;
    s.minions[0]={1,0,0,100,500,220,220,999,0,0};s.update();assert(s.bot_plan==BOT_FARM);
    // Melee waits outside enemy tower range, then pushes with allied minion cover.
    s.bot_selected=1;s.start_match();s.fighters[0].y=850;s.fighters[1].x=65;s.fighters[1].y=550;
    s.update();assert(s.bot_plan==BOT_WAIT);
    s.minions[0]={1,1,0,86,600,220,220,999,0,0};s.update();assert(s.bot_plan==BOT_PUSH);
    // Bot inventory uses real gold and increases HP, MP, normal and skill damage.
    s.bot_selected=0;s.start_match();s.fighters[1].gold=1000;
    for(int i=0;i<6;++i)s.army_update(0);
    assert(s.fighters[1].items==63&&s.fighters[1].gold==180);
    assert(s.max_hp(1)==1480&&s.max_mana(1)==760&&s.attack_power(1)==48&&s.skill_power(1)==25);
    assert(s.fighters[1].hp==1480&&s.fighters[1].mana==760);
    s.start_match();s.fighters[0].y=850;s.fighters[1].x=65;s.fighters[1].y=500;s.fighters[1].mana=0;
    s.update();assert(s.bot_plan==BOT_RECOVER);assert(!s.basic_attack(1));
    s.fighters[1].y=135;s.fighters[1].hp=500;s.fighters[1].heal_ms=15000;
    int recovered_hp=s.fighters[1].hp,recovered_mp=s.fighters[1].mana;
    step(s,15);assert(s.fighters[1].hp>recovered_hp&&s.fighters[1].mana>recovered_mp);
    setup(s,0,0);s.fighters[0].y=s.fighters[1].y=480;s.update();assert(s.bot_plan==BOT_DUEL);
    save(s,"28_bot_duel.ppm");
    s.input(-1);s.input(-1);assert(s.exiting);
    puts("PASS: splash/menu, hero/bot selection, mana/cooldown/stun, three hero mechanics, AI casts/retreat, heal, pause, respawn, guarded towers/core victory, camera, skins/time limit, rematch/back, framebuffer guards");
}
