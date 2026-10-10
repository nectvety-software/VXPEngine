#include "scene.h"
#include <stdio.h>

namespace {
int absn(int n){return n<0?-n:n;}
int bound(int n,int low,int high){return n<low?low:(n>high?high:n);}
bool item(const DuelFighter& f,int i){return (f.items&(1<<i))!=0;}
const int unit_hp[3]={220,150,480},unit_attack[3]={18,22,48},unit_range[3]={24,70,85};
const int bounty[3]={32,40,65};
}
const DuelItem duel_items[6]={
    {"EDGE BLADE","+14 BASIC ATTACK",120},{"STONE MAIL","+260 HP / 12% ARMOR",160},
    {"PRISM ORB","+160 MP / +25 SKILL",160},{"WIND BOOTS","+1 MOVE SPEED",100},
    {"RAPID BOW","-180ms ATTACK DELAY",150},{"LIFE CHARM","+120 HP / REGEN",130}
};
int FoxScene::max_hp(int o)const{return duel_heroes[fighters[o].hero].max_hp+(item(fighters[o],1)?260:0)+(item(fighters[o],5)?120:0);}
int FoxScene::max_mana(int o)const{return duel_heroes[fighters[o].hero].max_mana+(item(fighters[o],2)?160:0);}
int FoxScene::attack_power(int o)const{return duel_heroes[fighters[o].hero].attack+(item(fighters[o],0)?14:0);}
int FoxScene::skill_power(int o)const{return item(fighters[o],2)?25:0;}
int FoxScene::attack_delay(int o)const{return bound(duel_heroes[fighters[o].hero].attack_cd-(item(fighters[o],4)?180:0),250,1000);}
int FoxScene::move_speed(int o)const{return bound(duel_heroes[fighters[o].hero].speed+(item(fighters[o],3)?1:0),1,4);}
int FoxScene::take_damage(int o,int amount){
    auto& f=fighters[o];if(f.hp<=0||amount<=0)return 0;
    if(f.hero==1)amount=amount*85/100;
    if(item(f,1))amount=amount*88/100;
    int absorbed=amount<f.shield?amount:f.shield;f.shield-=absorbed;amount-=absorbed;
    int actual=amount<f.hp?amount:f.hp;f.hp=bound(f.hp-amount,0,max_hp(o));return actual;
}
bool FoxScene::buy_item(int owner,int index){
    if(owner<0||owner>1||index<0||index>=6||screen!=DUEL_MATCH)return false;
    auto& f=fighters[owner];if(item(f,index)||f.gold<duel_items[index].cost)return false;
    int hp=max_hp(owner),mp=max_mana(owner);f.gold-=duel_items[index].cost;f.items|=1<<index;
    if(f.hp>0)f.hp+=max_hp(owner)-hp;
    f.mana+=max_mana(owner)-mp;return true;
}
int FoxScene::nearest_minion(int owner,int x,int y,int range)const{
    int best=-1,distance=range+1;
    for(int i=0;i<48;++i){const auto& m=minions[i];if(!m.active||m.owner==owner)continue;
        int d=absn(x-m.x)+absn(y-m.y);
        if(d<distance){distance=d;best=i;}
    }return best;
}
void FoxScene::hurt_minion(int owner,int index,int damage){
    if(index<0||index>=48||damage<=0)return;
    auto& m=minions[index];if(!m.active||owner==m.owner)return;
    m.hp=bound(m.hp-damage,0,m.max_hp);
    if(m.hp==0){
        m.active=0;int team=1-m.owner;auto& f=fighters[team];
        if(owner==team){f.gold+=bounty[m.kind];++f.last_hits;}
        else if(f.hp>0&&absn(f.x-m.x)+absn(f.y-m.y)<=160)f.gold+=8;
    }
}
void FoxScene::spawn_wave(){
    ++wave_count;
    for(int owner=0;owner<2;++owner)for(int u=0;u<(wave_count%3==0?4:3);++u){
        int kind=u<2?0:(u==2?1:2);
        for(auto& m:minions)if(!m.active){
            m={1,owner,kind,u%2?150:90,owner?(155-u*12):(805+u*12),unit_hp[kind],unit_hp[kind],0,0,0};break;
        }
    }
}
void FoxScene::army_update(unsigned short dt){
    gold_ms+=dt;if(gold_ms>=1000){gold_ms-=1000;for(auto& f:fighters)f.gold+=4;}
    wave_ms-=dt;if(wave_ms<=0){wave_ms+=12000;spawn_wave();}
    shop_notice=bound(shop_notice-dt,0,1800);
    // Bot chooses equipment according to archetype, with the same prices and gold as the player.
    static const int order[3][6]={{2,4,1,0,5,3},{1,0,5,4,3,2},{4,0,3,1,5,2}};
    auto& bot=fighters[1];int urgent=-1;
    if(bot.hp>0&&bot.hp<max_hp(1)*45/100&&!item(bot,1))urgent=1;
    else if(bot.mana<max_mana(1)/4&&!item(bot,2))urgent=2;
    if(urgent>=0)buy_item(1,urgent);
    else for(int i=0;i<6;++i){int choice=order[bot.hero][i];if(!item(bot,choice)){buy_item(1,choice);break;}}
    bool march=false;army_ms+=dt;if(army_ms>=66){army_ms-=66;march=true;}
    for(int i=0;i<48;++i){auto& m=minions[i];if(!m.active)continue;
        m.attack_ms=bound(m.attack_ms-dt,0,1500);m.shot_ms=bound(m.shot_ms-dt,0,200);m.moving=0;
        int target=nearest_minion(m.owner,m.x,m.y,unit_range[m.kind]);
        auto& enemy=fighters[1-m.owner];int hd=absn(m.x-enemy.x)+absn(m.y-enemy.y);
        if(target>=0){if(!m.attack_ms){hurt_minion(-1,target,unit_attack[m.kind]);m.attack_ms=m.kind==2?1500:900;m.shot_ms=180;}continue;}
        if(enemy.hp>0&&hd<=unit_range[m.kind]){if(!m.attack_ms){take_damage(1-m.owner,unit_attack[m.kind]);m.attack_ms=1000;m.shot_ms=180;}continue;}
        int structure=(1-m.owner)*3;
        for(int j=structure+2;j>=structure;--j)if(structures[j].hp>0){structure=j;break;}
        int d=absn(m.x-120)+absn(m.y-structures[structure].y);
        if(d<=unit_range[m.kind]+18){if(!m.attack_ms){damage_structure(m.owner,structure,unit_attack[m.kind]*(m.kind==2?2:1));m.attack_ms=m.kind==2?1500:1000;m.shot_ms=180;}continue;}
        if(!march)continue;
        int dy=m.owner?1:-1;
        // Keep a clear lane side when passing friendly towers; all movement respects world geometry.
        int desired=m.x<=120?86:154,dx=m.x<desired?1:(m.x>desired?-1:0);
        if(walkable(m.x+dx,m.y+dy)){m.x+=dx;m.y+=dy;m.moving=1;}
        else {int side=m.x<=120?-1:1;if(walkable(m.x+side,m.y)){m.x+=side;m.moving=1;}else if(walkable(m.x-side,m.y)){m.x-=side;m.moving=1;}}
    }
    // Farm automatically when no hero is in attack range; last-hit rewards favor deliberate skill timing.
    for(int o=0;o<2;++o){auto& f=fighters[o];if(f.hp<=0||f.stun_ms||f.attack_ms)continue;
        const auto& enemy=fighters[1-o];int range=duel_heroes[f.hero].attack_range;
        if(enemy.hp>0&&absn(f.x-enemy.x)+absn(f.y-enemy.y)<=range)continue;
        int target=-1,hp=100000;
        for(int j=0;j<48;++j){const auto& m=minions[j];if(m.active&&m.owner!=o&&m.hp<hp&&absn(f.x-m.x)+absn(f.y-m.y)<=range){target=j;hp=m.hp;}}
        if(target>=0){basic_attack(o);}
    }
}
bool FoxScene::basic_attack(int owner){
    if(owner<0||owner>1||screen!=DUEL_MATCH||paused||result||(shop_open&&owner==0))return false;
    if(owner==1&&(bot_plan==BOT_RECOVER||bot_plan==BOT_WAIT))return false;
    auto& f=fighters[owner];if(f.hp<=0||f.stun_ms||f.cast_ms||f.attack_ms)return false;
    int range=duel_heroes[f.hero].attack_range;
    f.basic_x=f.x+(f.facing?-range:range);f.basic_y=f.y;
    auto& enemy=fighters[1-owner];
    int target=-1,lowest=100000;
    for(int j=0;j<48;++j){const auto& m=minions[j];if(m.active&&m.owner!=owner&&m.hp<lowest&&absn(f.x-m.x)+absn(f.y-m.y)<=range){target=j;lowest=m.hp;}}
    if(enemy.hp>0&&absn(f.x-enemy.x)+absn(f.y-enemy.y)<=range){
        f.basic_x=enemy.x;f.basic_y=enemy.y;hit(owner,attack_power(owner));
    }else if(target>=0){
        f.basic_x=minions[target].x;f.basic_y=minions[target].y;hurt_minion(owner,target,attack_power(owner));
    }else{
        int outer=(1-owner)*3+2,index=outer;
        while(index>outer-2&&structures[index].hp<=0)--index;
        const auto& t=structures[index];
        if(t.hp>0&&absn(f.x-120)+absn(f.y-t.y)<=range+30){f.basic_x=120;f.basic_y=t.y;damage_structure(owner,index,attack_power(owner));}
    }
    f.attack_ms=attack_delay(owner);f.basic_ms=200;
    if(f.basic_x!=f.x)f.facing=f.basic_x<f.x;
    return true;
}
void FoxScene::farm_cast(int owner,int skill){
    const auto& f=fighters[owner];int range=0,damage=0;
    if(f.hero==0&&skill==1){range=85;damage=140;}
    if(f.hero==0&&skill==3){range=130;damage=300;}
    if(f.hero==1&&skill==0){range=65;damage=180;}
    if(f.hero==1&&skill==2){range=60;damage=100;}
    if(f.hero==1&&skill==3){range=95;damage=300;}
    if(f.hero==2&&skill==3){range=180;damage=240;}
    if(!range)return;
    for(int i=0;i<48;++i){const auto& m=minions[i];if(m.active&&m.owner!=owner&&absn(f.x-m.x)+absn(f.y-m.y)<range)hurt_minion(owner,i,damage+skill_power(owner));}
}
void FoxScene::draw_shop(unsigned short* fb){
    vxpe2d_overlay_rect(fb,240,320,5,44,230,201,0x0862,252,VXPE_BLEND_ALPHA);
    centered(fb,52,"EQUIPMENT SHOP",0xFFE9);char value[64];
    snprintf(value,sizeof(value),"GOLD %d / FARM %d",fighters[0].gold,fighters[0].last_hits);centered(fb,66,value,0xCF5F);
    for(int i=0;i<6;++i){int y=82+i*23;
        if(i==shop_selected)vxpe2d_fill_rect(fb,240,320,10,y-2,220,21,0x2945);
        text(fb,15,y,duel_items[i].name,item(fighters[0],i)?0x77E5:0xFFFF);
        snprintf(value,sizeof(value),item(fighters[0],i)?"OWNED":"%d G",duel_items[i].cost);numbers(fb,179,y,value);
        text(fb,15,y+10,duel_items[i].description,0xAD55);
    }
    centered(fb,224,shop_notice?"NOT ENOUGH GOLD / OWNED":"2/8 PICK  5 BUY  # CLOSE",0xFFE9);
}
void FoxScene::draw_action(unsigned short* fb,int owner,int x,int y){
    const auto& f=fighters[owner];int pose=(time_ms/120)&1;
    if(f.basic_ms)pose=2;
    if(f.cast_ms){
        if((f.hero==1&&f.last_skill==2)||(f.hero==2&&f.last_skill==1))pose=5;
        else if(f.hero==1&&f.last_skill==0)pose=2;
        else if(f.last_skill==1||f.last_skill==3)pose=3;
        else pose=4;
        if(f.hero==1&&f.last_skill==3)pose=4;
    }
    VxpeBlit565 b={};b.src={(short)(pose*48),(short)(f.hero*48),48,48};
    bool vertical=!f.cast_ms&&!f.basic_ms&&(f.direction==2||f.direction==8);
    if(vertical){int frame=f.moving?((time_ms/120)&1):0;
        b.src={(short)((frame+(f.direction==8?2:0))*40),(short)(f.hero*40),40,40};}
    b.dst_x=x-30;b.dst_y=y-60;b.dst_w=b.dst_h=60;b.alpha=255;
    const unsigned short tints[3]={0x87FF,0xC5BF,0xFD30};b.tint565=f.skin?tints[f.hero]:0xFFFF;
    b.blend=VXPE_BLEND_ALPHA;b.flip_x=vertical?0:f.facing;b.clip_x=0;b.clip_y=41;b.clip_w=240;b.clip_h=209;
    vxpe2d_blit_a8(fb,240,320,vertical?&direction_art:&action_art,&b);
    if(f.basic_ms){
        int progress=200-f.basic_ms;
        int tx=f.basic_x,ty=f.basic_y-camera_y-20;
        unsigned short color=duel_heroes[f.hero].color;
        if(f.hero==1){
            // Hammer sweep at the contacted target, distinct from ranged bolts.
            for(int j=-2;j<=2;++j){int px=tx+j*5,py=ty-8+absn(j)*3+progress/30;
                if(py>=41&&py+3<=250)vxpe2d_fill_rect(fb,240,320,px,py,4,3,color);}
        }else{
            int px=x+(tx-x)*progress/200,py=y-28+(ty-y+28)*progress/200;
            if(py>=41&&py+4<=250)vxpe2d_fill_rect(fb,240,320,px-2,py, f.hero==0?5:7,4,color);
        }
    }
}
void FoxScene::draw_minion(unsigned short* fb,int index){
    const auto& m=minions[index];int y=m.y-camera_y;
    if(y<41||y>285)return;
    int size=m.kind==2?36:27,bob=m.moving?((time_ms/140+index)&1):0;
    VxpeBlit565 b={};b.src={(short)(m.owner*32),(short)(m.kind*32),32,32};
    b.dst_x=m.x-size/2;b.dst_y=y-size-bob;b.dst_w=b.dst_h=size;b.alpha=255;b.tint565=0xFFFF;
    b.blend=VXPE_BLEND_ALPHA;b.clip_x=0;b.clip_y=41;b.clip_w=240;b.clip_h=209;
    vxpe2d_blit_a8(fb,240,320,&army_art,&b);
    if(y-size-5>=41&&y-size<250)bar(fb,m.x-12,y-size-5,24,m.hp,m.max_hp,m.owner?0xF980:0x57F7);
    if(m.shot_ms&&y>50&&y<240){
        int forward=m.owner?1:-1;unsigned short c=m.owner?0xF980:0x57F7;
        int sy=y-14+forward*(200-m.shot_ms)/12,len=m.kind==0?3:6;
        if(sy>=41&&sy+len<=250)vxpe2d_fill_rect(fb,240,320,m.x-1,sy,3,len,c);
    }
}
