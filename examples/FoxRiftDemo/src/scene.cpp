#include "scene.h"
#include "assets_generated.h"
#include "combat_assets_generated.h"
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
    vxpe2d_sprite_a8_from_vxa8(duel_arena,sizeof(duel_arena),&background);
    vxpe2d_sprite_a8_from_vxa8(duel_heroes_atlas,sizeof(duel_heroes_atlas),&heroes);
    vxpe2d_sprite_a8_from_vxa8(duel_logo,sizeof(duel_logo),&logo);
    vxpe2d_sprite_a8_from_vxa8(duel_structures,sizeof(duel_structures),&structure_art);
    vxpe2d_sprite_a8_from_vxa8(duel_skill_icons,sizeof(duel_skill_icons),&skill_art);
    vxpe_particles_init(&particles,48);screen=DUEL_SPLASH;
}
static const char* skin_names[3][2]={{"PRISM","FROST PRISM"},{"COPPER","OBSIDIAN"},{"WIND","SUNSET"}};
static const unsigned short skin_tints[3]={0x87FF,0xC5BF,0xFD30};
void FoxScene::select_hero(int index){selected=(index%3+3)%3;held=0;}
void FoxScene::start_match(){
    init();memset(fighters,0,sizeof(fighters));memset(projectiles,0,sizeof(projectiles));
    fighters[0].hero=selected;fighters[1].hero=bot_selected;
    fighters[0].skin=selected_skin;fighters[1].skin=bot_skin;
    memset(effects,0,sizeof(effects));
    for(int i=0;i<6;++i){int owner=i/3;structures[i]={owner,owner?(90+(i%3)*130):(870-(i%3)*130),i%3?900:1800,i%3?900:1800,0};}
    for(int i=0;i<2;++i){auto& f=fighters[i];const auto& h=duel_heroes[f.hero];
        f.x=i?179:65;f.y=i?210:750;f.hp=h.max_hp;f.mana=h.max_mana;f.facing=i;}
    screen=DUEL_MATCH;held=paused=result=time_ms=regen_ms=bot_think_ms=bot_decisions=bot_retreats=0;
    camera_y=clampi(fighters[0].y-190,0,640);vxpe_particles_clear(&particles);
}
void FoxScene::restart(){start_match();}
void FoxScene::hold(int key,bool down){
    if(screen==DUEL_SELECT){if(down){
        if(key==4)select_hero(selected-1);
        if(key==6)select_hero(selected+1);
        if(key==2)bot_selected=(bot_selected+2)%3;
        if(key==8)bot_selected=(bot_selected+1)%3;
    }return;}
    if(screen!=DUEL_MATCH||paused||result)return;
    int b=key==4?1:(key==6?2:(key==2?4:(key==8?8:0)));
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
    if(key==-1){screen=DUEL_SELECT;held=paused=0;return;}
    if(key==3 || (screen==DUEL_RESULT&&key==5)){start_match();return;}
    if(screen!=DUEL_MATCH)return;
    if(key==10){paused=!paused;held=0;return;}
    if(paused||result)return;
    if(key==5)cast(0);
    if(key==7)cast(1);
    if(key==9)cast(2);
    if(key==0)cast(3);
    if(key==1)heal(0);
}
void FoxScene::sparks(int x,int y,unsigned short color,int count){
    for(int i=0;i<count;++i){VxpeParticleSpawn p={};p.x=x;p.y=y;
        p.vx_q8=((i*23%91)-45)*256;p.vy_q8=((i*17%71)-45)*256;
        p.lifetime_ms=350+(i*29%350);p.color565=color;p.tint565=0xFFFF;
        p.alpha_start=255;p.size_start=3;p.size_end=1;p.blend=VXPE_BLEND_ADD;
        vxpe_particles_spawn(&particles,&p);}
}
void FoxScene::finish(){
    if(screen!=DUEL_MATCH)return;
    if(structures[0].hp<=0||structures[3].hp<=0||time_ms>=300000){
        int a=structures[0].hp,b=structures[3].hp;
        result=a==b?2:(a>b?1:-1);screen=DUEL_RESULT;held=paused=0;
    }
}
void FoxScene::damage_structure(int owner,int index,int amount){
    if(owner<0||owner>1||index<0||index>=6||amount<=0)return;
    auto& t=structures[index];if(t.owner==owner||t.hp<=0)return;
    int outer=t.owner*3+2,inner=t.owner*3+1;
    if(index!=outer&&structures[outer].hp>0)return;
    if(index%3==0&&structures[inner].hp>0)return;
    t.hp=clampi(t.hp-amount,0,t.max_hp);finish();
}
void FoxScene::lane_update(unsigned short dt){
    for(auto& t:structures){
        if(t.hp<=0)continue;
        t.attack_ms=clampi(t.attack_ms-dt,0,1200);
        auto& enemy=fighters[1-t.owner];
        if(enemy.hp>0&&absi(enemy.y-t.y)+absi(enemy.x-120)<105&&!t.attack_ms){
            t.attack_ms=1200;enemy.hp=clampi(enemy.hp-(t.owner*3==(&t-structures)?45:65),0,2000);
        }
    }
    for(int i=0;i<2;++i){auto& f=fighters[i];
        if(f.hp<=0){
            if(!f.respawn_ms)f.respawn_ms=5000;
            else {f.respawn_ms=clampi(f.respawn_ms-dt,0,5000);if(!f.respawn_ms){
                f.hp=duel_heroes[f.hero].max_hp;f.mana=duel_heroes[f.hero].max_mana;
                f.shield=f.stun_ms=f.slow_ms=0;f.x=120;f.y=i?160:800;
            }}continue;
        }
        if(absi(f.y-structures[i*3].y)<65){f.hp=clampi(f.hp+3,0,duel_heroes[f.hero].max_hp);f.mana=clampi(f.mana+2,0,duel_heroes[f.hero].max_mana);}
        if(f.attack_ms||f.stun_ms)continue;
        for(int j=(1-i)*3+2;j>=(1-i)*3;--j){auto& t=structures[j];
            if(t.hp>0&&absi(f.y-t.y)+absi(f.x-120)<=duel_heroes[f.hero].attack_range+30){
                f.attack_ms=duel_heroes[f.hero].attack_cd;damage_structure(i,j,duel_heroes[f.hero].attack);break;
            }
        }
    }
    camera_y=clampi(fighters[0].y-190,0,640);
}
void FoxScene::hit(int owner,int amount,int stun,int slow){
    if(owner<0||owner>1||amount<=0||screen!=DUEL_MATCH)return;
    auto& defender=fighters[1-owner];auto& attacker=fighters[owner];
    if(defender.hp<=0||attacker.hp<=0)return;
    if(defender.hero==1)amount=amount*85/100;
    int absorbed=amount<defender.shield?amount:defender.shield;
    defender.shield-=absorbed;amount-=absorbed;
    int actual=amount<defender.hp?amount:defender.hp;
    defender.hp=clampi(defender.hp-amount,0,duel_heroes[defender.hero].max_hp);
    attacker.damage_dealt+=actual;
    if(stun>defender.stun_ms)defender.stun_ms=stun;
    if(slow>defender.slow_ms)defender.slow_ms=slow;
    sparks(defender.x,defender.y-20,duel_heroes[attacker.hero].color,5);finish();
}
void FoxScene::move(int owner,int dx,int dy){
    auto& f=fighters[owner];if(f.stun_ms||f.hp<=0)return;
    int step=f.slow_ms?1:duel_heroes[f.hero].speed;
    if(dx)f.facing=dx<0;
    int old_x=f.x,old_y=f.y;
    f.x=clampi(f.x+dx*step,26,214);f.y=clampi(f.y+dy*step,80,880);
    f.moving=(old_x!=f.x||old_y!=f.y);
}
void FoxScene::heal(int owner){
    auto& f=fighters[owner];const auto& h=duel_heroes[f.hero];
    if(f.hp<=0||f.heal_ms||f.stun_ms||screen!=DUEL_MATCH||paused)return;
    int before=f.hp;f.hp=clampi(f.hp+300,0,h.max_hp);f.healing+=f.hp-before;
    f.mana=clampi(f.mana+120,0,h.max_mana);f.heal_ms=15000;
    sparks(f.x,f.y-20,0x87F0,12);
}
void FoxScene::cast(int skill){cast_for(0,skill);}
void FoxScene::cast_for(int owner,int skill){
    if(owner<0||owner>1||skill<0||skill>3||screen!=DUEL_MATCH||paused||result)return;
    auto& a=fighters[owner];auto& b=fighters[1-owner];const auto& h=duel_heroes[a.hero];
    if(a.hp<=0||a.stun_ms||a.cooldown[skill]||a.mana<h.cost[skill])return;
    a.mana-=h.cost[skill];a.cooldown[skill]=h.cd[skill];a.cast_ms=300;++a.casts;++a.skill_count;
    if(a.hero==0&&a.skill_count%3==0)a.shield=clampi(a.shield+50,0,300);
    int dx=b.x-a.x,dy=b.y-a.y,norm=absi(dx)>absi(dy)?absi(dx):absi(dy);if(!norm)norm=1;
    a.facing=dx<0;int d=dist(a,b);
    sparks(a.x,a.y-20,h.color,10);
    for(auto& e:effects)if(!e.life){e={a.x,a.y,650,a.hero,skill,owner};break;}
    if(a.hero==1){
        if(skill==0&&d<65)hit(owner,180);
        if(skill==1)a.shield=clampi(a.shield+240,0,400);
        if(skill==2){a.x=clampi(a.x+dx*45/norm,26,214);a.y=clampi(a.y+dy*45/norm,80,880);
            if(dist(a,b)<60)hit(owner,100,600);}
        if(skill==3&&d<95)hit(owner,300,900);
    }else if(a.hero==2&&skill==1){
        a.x=clampi(a.x-dx*35/norm,26,214);a.y=clampi(a.y-dy*35/norm,80,880);
        a.shield=clampi(a.shield+90,0,300);
    }else if((a.hero==0&&skill==1)||skill==3){
        int range=skill==3?(a.hero==2?180:130):85;
        if(d<range)hit(owner,skill==3?(a.hero==2?240:300):140,0,skill==3?900:0);
    }else{
        int damage=a.hero==2?(skill==2?100:165):(skill==2?90:190);
        int stun=skill==2?(a.hero==2?650:1000):0;
        for(auto& p:projectiles)if(!p.active){p={a.x,a.y-18,dx*6/norm,dy*6/norm,1600,damage,stun,skill==0?350:0,owner,1};break;}
    }
}
void FoxScene::bot_update(unsigned short dt){
    auto& bot=fighters[1];auto& player=fighters[0];const auto& h=duel_heroes[bot.hero];
    if(bot.stun_ms||bot.hp<=0)return;
    if(player.hp<=0||dist(bot,player)>210){
        int target=0;for(int j=2;j>=0;--j)if(structures[j].hp>0){target=j;break;}
        int y=structures[target].y;
        if(absi(bot.y-y)>duel_heroes[bot.hero].attack_range+20)move(1,bot.x<120?1:(bot.x>120?-1:0),bot.y<y?1:-1);
        return;
    }
    int d=dist(bot,player),dx=player.x>bot.x?1:(player.x<bot.x?-1:0),dy=player.y>bot.y?1:(player.y<bot.y?-1:0);
    bool retreat=bot.hp<h.max_hp*30/100;
    int desired=bot.hero==1?30:(bot.hero==2?100:80);
    // The bot uses the same movement, mana, cooldown and skill rules as the player.
    if((time_ms/33)%2==0){
        if(retreat||d<desired-15){move(1,-dx,-dy);if(retreat)++bot_retreats;}
        else if(d>desired+12)move(1,dx,dy);
    }
    bot_think_ms-=dt;if(bot_think_ms>0)return;bot_think_ms=350;++bot_decisions;
    if(retreat&&!bot.heal_ms)heal(1);
    if(bot.hero==1){
        if(d<65)cast_for(1,0);
        if(bot.hp<h.max_hp*65/100)cast_for(1,1);
        if(d>55&&d<140)cast_for(1,2);
        if(d<90)cast_for(1,3);
    }else{
        if(d<180)cast_for(1,0);
        if(bot.hero==0&&d<85)cast_for(1,1);
        if(bot.hero==2&&d<75)cast_for(1,1);
        if(d<150)cast_for(1,2);
        if(d<120)cast_for(1,3);
    }
}
void FoxScene::update(unsigned short dt){
    init();ui_ms+=dt;
    if(screen==DUEL_SPLASH){if(ui_ms>=1800){screen=DUEL_SELECT;ui_ms=0;}return;}
    if(screen!=DUEL_MATCH||paused||result)return;
    time_ms+=dt;
    for(auto& e:effects)e.life=clampi(e.life-dt,0,650);
    lane_update(dt);
    vxpe_particles_update(&particles,dt);
    for(auto& f:fighters){
        f.moving=0;
        for(int& c:f.cooldown)c=clampi(c-dt,0,7000);
        f.attack_ms=clampi(f.attack_ms-dt,0,1000);f.stun_ms=clampi(f.stun_ms-dt,0,2000);
        f.slow_ms=clampi(f.slow_ms-dt,0,2000);f.cast_ms=clampi(f.cast_ms-dt,0,300);
        f.heal_ms=clampi(f.heal_ms-dt,0,15000);
    }
    int dx=((held&2)?1:0)-((held&1)?1:0),dy=((held&8)?1:0)-((held&4)?1:0);
    move(0,dx,dy);bot_update(dt);
    if(screen!=DUEL_MATCH)return;
    regen_ms+=dt;
    if(regen_ms>=300){regen_ms-=300;
        for(int i=0;i<2;++i){auto& f=fighters[i];const auto& h=duel_heroes[f.hero];
            f.mana=clampi(f.mana+4+((f.hero==2&&f.moving)?2:0),0,h.max_mana);}
    }
    for(int i=0;i<2&&screen==DUEL_MATCH;++i){auto& a=fighters[i];const auto& h=duel_heroes[a.hero];
        if(a.hp>0&&fighters[1-i].hp>0&&!a.stun_ms&&!a.attack_ms&&dist(a,fighters[1-i])<=h.attack_range){
            a.attack_ms=h.attack_cd;hit(i,h.attack);}
    }
    for(auto& p:projectiles)if(p.active&&screen==DUEL_MATCH){
        p.x+=p.vx;p.y+=p.vy;p.life-=dt;
        if(p.life<=0||p.x<0||p.x>239||p.y<0||p.y>960){p.active=0;continue;}
        auto& target=fighters[1-p.owner];
        if(absi(p.x-target.x)+absi(p.y-(target.y-18))<20){p.active=0;hit(p.owner,p.damage,p.stun,p.slow);}
    }
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
        const char* lines[]={"2468 MOVE / ARROWS","AUTO ATTACK IN RANGE","5 7 9 0: FOUR SKILLS","1: RECOVER HP AND MANA","*: PAUSE  3: REMATCH","BACK: HERO SELECTION","BOT USES THE SAME RULES","TOWERS FIRST / 5s RESPAWN","1 CLOSE / 5 START"};
        for(int i=0;i<9;++i)text(fb,17,82+i*20,lines[i],0xFFFF);
    }
}
void FoxScene::draw_match(unsigned short* fb){
    // Scroll the original terrain in world coordinates, retaining a native QVGA framebuffer.
    for(int y=41;y<250;++y){int sy=(y+camera_y)%320;
        // Existing opaque VXA8 terrain stores RGB565 immediately after its 12-byte header.
        const unsigned char* row=duel_arena+12+sy*240*2;
        for(int x=0;x<240;++x)fb[y*240+x]=(unsigned short)(row[x*2]|(row[x*2+1]<<8));
    }
    for(auto& t:structures){int y=t.y-camera_y;if(y<55||y>246)continue;
        unsigned short c=t.owner?0xF980:0x57F7;
        int core=t.max_hp==1800,col=t.hp?t.owner:2;
        VxpeBlit565 art={};art.src={(short)(col*64),(short)(core*80),64,80};
        art.dst_w=core?68:56;art.dst_h=core?80:70;
        art.dst_x=120-art.dst_w/2;art.dst_y=y-art.dst_h+2;
        art.alpha=255;art.tint565=0xFFFF;art.blend=VXPE_BLEND_ALPHA;
        art.clip_x=0;art.clip_y=41;art.clip_w=240;art.clip_h=209;
        vxpe2d_blit_a8(fb,240,320,&structure_art,&art);
        if(t.hp){int label_y=y-(core?75:81);
            bar(fb,95,label_y+10,50,t.hp,t.max_hp,c);
            text(fb,101,label_y,core?"CORE":"TOWER",c);
        }else text(fb,97,y-14,"RUINS",0xAD55);
    }
    for(auto& e:effects)if(e.life){int y=e.y-camera_y,r=8+e.skill*5+(650-e.life)/(18-e.skill*2);
        unsigned short c=fighters[e.owner].skin?skin_tints[e.hero]:duel_heroes[e.hero].color;
        if(y<60||y>240)continue;
        if(e.hero==0){for(int n=0;n<4;++n){int d=r+n*4;vxpe2d_fill_rect(fb,240,320,e.x-d,y-22-n*6,2,12,c);vxpe2d_fill_rect(fb,240,320,e.x+d,y-22-n*6,2,12,c);}}
        else if(e.hero==1){for(int n=0;n<3;++n)vxpe2d_fill_rect(fb,240,320,e.x-r,y-n*5,r*2,2,c);}
        else {for(int n=0;n<5;++n)vxpe2d_fill_rect(fb,240,320,e.x-24+n*10,y-20-r+n*3,3,15,c);}
    }

    int first=fighters[0].y<=fighters[1].y?0:1;
    for(int j=0;j<2;++j){int i=j?1-first:first;auto f=fighters[i];f.y-=camera_y;if(f.hp<=0||f.y<70||f.y>249)continue;const auto& h=duel_heroes[f.hero];
        vxpe2d_overlay_rect(fb,240,320,f.x-17,f.y-3,34,4,0,130,VXPE_BLEND_ALPHA);
        sprite(fb,f.hero,f.cast_ms?2:((i?dist(fighters[i],fighters[0])>40:held)?1:0),f.x,f.y,60,60,f.facing,f.skin);
        unsigned short team=i?0xFA08:0x57F7;
        vxpe2d_fill_rect(fb,240,320,f.x-14,f.y-1,28,2,team);
        if(!i || dist(fighters[i],fighters[0])>65)
            hero_text(fb,clampi(f.x-vxpe_font_measure(h.name,&vaelora_font_hero)/2,1,200),f.y-77,h.name,team);
        if(!i || dist(fighters[i],fighters[0])>65){
            bar(fb,f.x-25,f.y-67,50,f.hp,h.max_hp,i?0xF980:0x77E5);
            bar(fb,f.x-25,f.y-61,50,f.mana,h.max_mana,0x2DFF);
            if(f.shield)bar(fb,f.x-25,f.y-55,50,f.shield,400,0xFFE9);
        }
        if(f.stun_ms)text(fb,f.x-12,f.y-86,"STUN",0xFFE9);
    }
    for(auto& p:projectiles)if(p.active){const auto& h=duel_heroes[fighters[p.owner].hero];
        vxpe2d_radial_light(fb,240,320,p.x,p.y-camera_y,9,h.color,110);
        vxpe2d_fill_rect(fb,240,320,p.x-2,p.y-camera_y-2,5,5,0xFFFF);}
    // World effects above replace screen-space particle rendering during lane play.
    vxpe2d_overlay_rect(fb,240,320,0,0,240,24,0x0862,242,VXPE_BLEND_ALPHA);
    text(fb,7,4,"VAELORA DUEL",0xEDEB);char value[64];
    snprintf(value,sizeof(value),"%02d:%02d",time_ms/60000,(time_ms/1000)%60);numbers(fb,233-vxpe_font_measure(value,&vaelora_font_numbers),4,value);
    snprintf(value,sizeof(value),"CORE %d VS %d",structures[0].hp,structures[3].hp);text(fb,7,15,value,0xCF5F);
    vxpe2d_overlay_rect(fb,240,320,0,24,240,17,0x0862,225,VXPE_BLEND_ALPHA);
    const auto& bot=fighters[1];const auto& bot_def=duel_heroes[bot.hero];
    text(fb,7,27,"BOT",0xFA08);bar(fb,32,28,149,bot.hp,bot_def.max_hp,0xF980);
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
    bar(fb,51,287,172,p.hp,h.max_hp,0x4DA4);
    snprintf(value,sizeof(value),"%d / %d",p.hp,h.max_hp);numbers(fb,102,294,value);
    bar(fb,51,303,172,p.mana,h.max_mana,0x2BFF);
    snprintf(value,sizeof(value),"MP %d/%d",p.mana,h.max_mana);numbers(fb,105,303,value);
    if(p.hp<=0)snprintf(value,sizeof(value),"RESPAWN %ds",(p.respawn_ms+999)/1000);
    else snprintf(value,sizeof(value),"1 HEAL %ds  * PAUSE",(p.heal_ms+999)/1000);
    text(fb,51,311,value,0xEDEB);
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
