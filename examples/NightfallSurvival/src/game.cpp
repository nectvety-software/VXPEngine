#include "game.h"
#include "art.h"
#include "font.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char* MAP[16]={
 "1111111111111111",
 "1000000100000001",
 "1000000100000001",
 "1022000100000001",
 "1000000100000001",
 "1000000400000001",
 "1000000100000001",
 "1115111100000001",
 "1000000000000001",
 "1000000000000001",
 "1000000000000001",
 "1000000000000001",
 "1000000000000001",
 "1000000000000001",
 "1000000000000001",
 "1111111111111111"
};
static const int SCREEN_W=240,SCREEN_H=320;
static const float PI=3.14159265f;
static int clamp(int v,int low,int high){return v<low?low:v>high?high:v;}
static uint16_t color(int r,int g,int b){return ((r>>3)<<11)|((g>>2)<<5)|(b>>3);}
static uint16_t shade(uint16_t c,float factor){
    int r=(int)(((c>>11)&31)*factor),g=(int)(((c>>5)&63)*factor),b=(int)((c&31)*factor);
    return (clamp(r,0,31)<<11)|(clamp(g,0,63)<<5)|clamp(b,0,31);
}
static void rect(uint16_t* fb,int x,int y,int w,int h,uint16_t c){
    int right=clamp(x+w,0,SCREEN_W),bottom=clamp(y+h,0,SCREEN_H);
    for(int py=clamp(y,0,SCREEN_H);py<bottom;++py)for(int px=clamp(x,0,SCREEN_W);px<right;++px)fb[py*SCREEN_W+px]=c;
}
static void text(uint16_t* fb,int x,int y,const char* str,uint16_t c,int scale=1){
    for(;*str;++str,x+=6*scale){int i=*str>='A'&&*str<='Z'?*str-'A':*str>='0'&&*str<='9'?26+*str-'0':-1;
        if(i<0)continue;
        for(int row=0;row<7;++row)for(int col=0;col<5;++col)
            if(FONT5X7[i][row]&(1<<(4-col)))rect(fb,x+col*scale,y+row*scale,scale,scale,c);
    }
}
static float dist2(float ax,float ay,float bx,float by){float dx=ax-bx,dy=ay-by;return dx*dx+dy*dy;}
Game::Game(){phase=TITLE;selected=0;tick=0;exiting=false;start();phase=TITLE;}
void Game::start(){
    x=3.5f;y=5.5f;angle=-0.27f;health=100;ammo=12;reserve=60;points=0;kills=0;
    wave=1;remaining=5;spawnTimer=30;reloadTimer=fireTimer=hurtTimer=breakTimer=0;
    barrier=4;held=0;gateOpen=false;random=481388;message="SURVIVE THE NIGHT";messageTimer=100;
    memset(zombies,0,sizeof(zombies));phase=RUNNING;
}
int Game::cell(int cx,int cy)const{
    if(cx<0||cy<0||cx>=16||cy>=16)return 1;
    int c=MAP[cy][cx]-'0';
    if((c==4&&gateOpen)||(c==5&&barrier==0))return 0;
    return c;
}
bool Game::blocked(float px,float py)const{
    const float r=.18f;
    return cell((int)floorf(px-r),(int)floorf(py-r))||cell((int)floorf(px+r),(int)floorf(py-r))||
           cell((int)floorf(px-r),(int)floorf(py+r))||cell((int)floorf(px+r),(int)floorf(py+r));
}
bool Game::visible(float ax,float ay,float bx,float by)const{
    float dx=bx-ax,dy=by-ay;int steps=(int)(sqrtf(dx*dx+dy*dy)*12)+1;
    for(int i=1;i<steps;++i)if(cell((int)(ax+dx*i/steps),(int)(ay+dy*i/steps)))return false;
    return true;
}
void Game::move(float forward,float side){
    float nx=x+cosf(angle)*forward-sinf(angle)*side,ny=y+sinf(angle)*forward+cosf(angle)*side;
    if(!blocked(nx,y))x=nx;
    if(!blocked(x,ny))y=ny;
}
void Game::hold(Action key,bool down){
    if(key>STRAFE_RIGHT)return;
    if(phase!=RUNNING){held=0;return;}
    if(down)held|=1u<<key;else held&=~(1u<<key);
}
void Game::shoot(){
    if(fireTimer||reloadTimer)return;
    if(!ammo){message="EMPTY   PRESS 0 TO RELOAD";messageTimer=50;return;}
    --ammo;fireTimer=7;
    int target=-1;float nearest=30;
    for(int i=0;i<18;++i){Zombie& z=zombies[i];if(!z.alive)continue;
        float dx=z.x-x,dy=z.y-y,forward=dx*cosf(angle)+dy*sinf(angle),side=-dx*sinf(angle)+dy*cosf(angle);
        if(forward>0&&forward<nearest&&fabsf(side)<.25f+forward*.018f&&visible(x,y,z.x,z.y)){target=i;nearest=forward;}}
    if(target>=0){Zombie& z=zombies[target];z.hp-=40;points+=10;
        if(z.hp<=0){z.alive=false;++kills;points+=90;message="ELIMINATED   100 POINTS";messageTimer=30;}}
}
void Game::interact(){
    if(dist2(x,y,6.3f,5.5f)<2.0f&&!gateOpen){
        if(points>=500){points-=500;gateOpen=true;message="COURTYARD UNLOCKED";}else message="GATE COSTS 500 POINTS";
    }else if(dist2(x,y,2.5f,5.5f)<2.0f){
        if(points>=200&&reserve<120){points-=200;reserve=120;message="AMMO RESTOCKED";}
        else message="AMMO 200 POINTS";
    }else if(dist2(x,y,3.5f,6.4f)<2.0f){
        if(barrier<4){++barrier;points+=10;message="BARRICADE REPAIRED   10 POINTS";}else message="BARRICADE SECURE";
    }else if(dist2(x,y,10.5f,10.5f)<2.0f){
        if(points>=300&&health<100){points-=300;health=100;message="HEALTH RESTORED";}else message="MEDKIT 300 POINTS";
    }else message="MOVE CLOSE TO A SUPPLY OR GATE";
    messageTimer=60;
}
void Game::action(Action key){
    if(phase==TITLE){
        if(key==FORWARD||key==TURN_LEFT)selected=(selected+2)%3;
        if(key==REVERSE||key==TURN_RIGHT)selected=(selected+1)%3;
        if(key==FIRE){if(selected==0)start();else if(selected==1)phase=GUIDE;else exiting=true;}
        if(key==BACK)exiting=true;
        return;
    }
    if(phase==GUIDE){if(key==BACK||key==FIRE)phase=TITLE;return;}
    if(phase==DEAD){if(key==FIRE)start();if(key==BACK)phase=TITLE;return;}
    if(key==BACK){phase=TITLE;held=0;return;}
    if(key==PAUSE){phase=phase==RUNNING?PAUSED:RUNNING;held=0;return;}
    if(phase!=RUNNING)return;
    if(key==FIRE)shoot();
    if(key==RELOAD&&!reloadTimer&&ammo<12&&reserve>0){reloadTimer=40;message="RELOADING";messageTimer=40;}
    if(key==INTERACT)interact();
}
void Game::spawn(){
    static const float positions[6][2]={{5.5f,2.5f},{1.5f,1.5f},{5.5f,6.5f},{12.5f,2.5f},{13.5f,12.5f},{3.5f,8.5f}};
    for(int i=0;i<18;++i)if(!zombies[i].alive){
        random=random*1664525u+1013904223u;int index=(random>>16)% (gateOpen?6:3);
        if(!gateOpen&&barrier==0&&wave>1)index=5;
        Zombie& z=zombies[i];z.x=positions[index][0];z.y=positions[index][1];
        z.hp=60+wave*8;z.attack=0;z.frame=0;z.alive=true;--remaining;return;
    }
}
void Game::update(){
    ++tick;if(phase!=RUNNING)return;
    if(held&(1u<<TURN_LEFT))angle-=.055f;
    if(held&(1u<<TURN_RIGHT))angle+=.055f;
    if(angle>PI)angle-=2*PI;
    if(angle<-PI)angle+=2*PI;
    float f=((held&(1u<<FORWARD))?1.f:0.f)-((held&(1u<<REVERSE))?1.f:0.f);
    float s=((held&(1u<<STRAFE_RIGHT))?1.f:0.f)-((held&(1u<<STRAFE_LEFT))?1.f:0.f);
    if(f&&s){f*=.7071f;s*=.7071f;}move(f*.072f,s*.072f);
    if(fireTimer)--fireTimer;
    if(hurtTimer)--hurtTimer;
    if(messageTimer)--messageTimer;
    if(reloadTimer&&!--reloadTimer){int amount=12-ammo;if(amount>reserve)amount=reserve;ammo+=amount;reserve-=amount;}
    if(breakTimer){--breakTimer;if(!breakTimer){++wave;remaining=4+wave*2;spawnTimer=30;message="NEXT WAVE INCOMING";messageTimer=70;}}
    if(!breakTimer&&remaining&&!--spawnTimer){spawn();spawnTimer=clamp(70-wave*3,20,70);}
    int alive=0;
    for(int i=0;i<18;++i){Zombie& z=zombies[i];if(!z.alive)continue;++alive;
        float dx=x-z.x,dy=y-z.y,d=sqrtf(dx*dx+dy*dy);if(z.attack)--z.attack;
        if(d<.65f){if(!z.attack){health-=10;hurtTimer=9;z.attack=25;if(health<=0){health=0;phase=DEAD;held=0;}}continue;}
        float speed=.012f+clamp(wave,1,15)*.002f;
        // Local detour around a wall: choose an open neighbour that approaches the player.
        float nx=z.x+dx/d*speed,ny=z.y+dy/d*speed;
        bool canX=!blocked(nx,z.y),canY=!blocked(z.x,ny);
        if(canX)z.x=nx;
        if(canY)z.y=ny;
        if(!canX&&!canY){float best=1e9f,bx=z.x,by=z.y;
            const float offsets[4][2]={{1,0},{-1,0},{0,1},{0,-1}};
            for(int j=0;j<4;++j){float tx=z.x+offsets[j][0]*speed,ty=z.y+offsets[j][1]*speed;
                float distance=dist2(tx,ty,x,y);if(!blocked(tx,ty)&&distance<best){best=distance;bx=tx;by=ty;}}
            z.x=bx;z.y=by;
        }
        z.frame=(tick/12+i)%2;
        if(barrier&&dist2(z.x,z.y,3.5f,8.1f)<1.5f&&tick%45==0)--barrier;
    }
    if(!alive&&!remaining&&!breakTimer){breakTimer=120;points+=100;health=clamp(health+20,0,100);message="WAVE CLEAR   100 BONUS";messageTimer=100;}
}

static void sprite(uint16_t* fb,const uint16_t* pixels,int sw,int sh,int left,int top,int width,int height,float light,const float* depth,float distance){
    if(width<=0||height<=0)return;
    for(int py=clamp(top,18,298);py<clamp(top+height,18,298);++py){int sy=(py-top)*sh/height;
        for(int px=clamp(left,0,SCREEN_W);px<clamp(left+width,0,SCREEN_W);++px){
            if(depth&&distance>depth[px])continue;
            uint16_t c=pixels[sy*sw+(px-left)*sw/width];if(c!=65535)fb[py*SCREEN_W+px]=shade(c,light);
        }
    }
}
void Game::draw(uint16_t* fb){
    float dirX=cosf(angle),dirY=sinf(angle),planeX=-dirY*.50f,planeY=dirX*.50f;
    // Perspective floor and ceiling sampled in 2x2 blocks for the MRE CPU budget.
    for(int py=18;py<298;py+=2){
        float distance=py>152?150.f/(py-152):150.f/(152-py+.1f);
        for(int px=0;px<SCREEN_W;px+=2){
            float side=2.f*px/(float)SCREEN_W-1.f;
            float wx=x+distance*(dirX+planeX*side),wy=y+distance*(dirY+planeY*side);
            int tx=((int)floorf(wx*64))&63,ty=((int)floorf(wy*64))&63;
            float light=.85f/(1.f+distance*.19f);
            uint16_t c;
            if(py>=152)c=shade((x<7?ART_wood:ART_floor)[ty*64+tx],light*1.15f);
            else if(x<7)c=shade(ART_wood[ty*64+tx],light*.65f);
            else {
                c=color(13+(152-py)/14,14+(152-py)/20,24+(152-py)/10);
                float panorama=angle+atanf(side*.50f);
                float tree=sin(panorama*17)*sin(panorama*8)*13+sin(panorama*39)*6;
                if(py>119+tree)c=color(9,12,15);
            }
            rect(fb,px,py,2,2,c);
        }
    }
    for(int px=0;px<SCREEN_W;px+=2){
        float side=2.f*px/(float)SCREEN_W-1.f,rx=dirX+planeX*side,ry=dirY+planeY*side;
        int mx=(int)x,my=(int)y,sx=rx<0?-1:1,sy=ry<0?-1:1;
        float dx=fabsf(rx)<.00001f?1e6f:fabsf(1.f/rx),dy=fabsf(ry)<.00001f?1e6f:fabsf(1.f/ry);
        float vx=(rx<0?x-mx:mx+1-x)*dx,vy=(ry<0?y-my:my+1-y)*dy;
        int axis=0,wall=1;
        for(int i=0;i<40;++i){if(vx<vy){vx+=dx;mx+=sx;axis=0;}else{vy+=dy;my+=sy;axis=1;}wall=cell(mx,my);if(wall)break;}
        float d=axis?vy-dy:vx-dx;if(d<.08f)d=.08f;
        depth[px]=depth[px+1]=d;int height=(int)(300.f/d),top=152-height/2;
        float hit=axis?x+d*rx:y+d*ry;int tx=(int)((hit-floorf(hit))*64);
        const uint16_t* texture=(wall==2||(wall==1&&mx<=7&&my<=7))?ART_wood:wall==3?ART_stone:wall>=4?ART_gate:ART_brick;
        float light=(axis?.82f:1.05f)/(1.f+d*.15f);
        float hx=x+d*rx,hy=y+d*ry;
        float warm=.28f/(1.f+dist2(hx,hy,6.5f,1.5f));
        for(int py=clamp(top,18,298);py<clamp(top+height,18,298);++py){
            int ty=clamp((py-top)*64/height,0,63);uint16_t c=shade(texture[ty*64+tx],light+warm);
            if(warm>.07f)c=color(clamp(((c>>11)&31)*8+(int)(warm*70),0,255),((c>>5)&63)*4,(c&31)*8);
            // The window barricade loses horizontal planks as it is damaged.
            if(wall==5&&ty/16>=barrier)c=color(9,12,17);
            fb[py*SCREEN_W+px]=fb[py*SCREEN_W+px+1]=c;
        }
    }
    // Sort transparent billboards back-to-front and clip against wall depth.
    struct Object{float x,y;const uint16_t* image;int w,h;float size;};
    Object objects[32];int count=0;
    for(int i=0;i<18;++i)if(zombies[i].alive)objects[count++]={zombies[i].x,zombies[i].y,zombies[i].frame?ART_zombie1:ART_zombie0,48,64,1.f};
    const float graves[4][2]={{10.5f,4.5f},{12.5f,5.5f},{10.5f,8.5f},{12.5f,9.5f}};
    for(int i=0;i<4;++i)objects[count++]={graves[i][0],graves[i][1],ART_grave,48,64,.75f};
    const float lights[4][2]={{6.5f,1.5f},{9.5f,4.5f},{11.5f,8.5f},{13.5f,11.5f}};
    for(int i=0;i<4;++i)objects[count++]={lights[i][0],lights[i][1],ART_candle,24,48,.55f};
    objects[count++]={4.5f,2.2f,ART_sofa,64,48,.65f};
    for(int i=0;i<count;++i)for(int j=i+1;j<count;++j)
        if(dist2(objects[i].x,objects[i].y,x,y)<dist2(objects[j].x,objects[j].y,x,y)){Object t=objects[i];objects[i]=objects[j];objects[j]=t;}
    for(int i=0;i<count;++i){Object& o=objects[i];float dx=o.x-x,dy=o.y-y,forward=dx*dirX+dy*dirY,side=-dx*dirY+dy*dirX;
        if(forward<.15f)continue;
        int height=(int)(170.f*o.size/forward),width=height*o.w/o.h;
        int center=120+(int)(side/forward*180),bottom=152+(int)(150/forward);
        sprite(fb,o.image,o.w,o.h,center-width/2,bottom-height,width,height,1.15f/(1+forward*.12f),depth,forward);
    }
    // In-world supply markings and interaction hint.
    if(dist2(x,y,2.5f,5.5f)<2.f){text(fb,60,265,"7 AMMO 200",color(200,179,114));}
    else if(dist2(x,y,6.3f,5.5f)<2.f&&!gateOpen)text(fb,40,265,"7 OPEN GATE 500",color(200,179,114));
    else if(dist2(x,y,3.5f,6.4f)<2.f)text(fb,60,265,"7 REPAIR WINDOW",color(200,179,114));
    else if(dist2(x,y,10.5f,10.5f)<2.f)text(fb,60,265,"7 MEDKIT 300",color(200,179,114));
    int bob=held?(int)(sinf(tick*.35f)*2):0,recoil=fireTimer>4?(fireTimer-4)*3:0;
    if(reloadTimer)sprite(fb,ART_pistol,112,104,118,242,112,104,.8f,0,0);
    else sprite(fb,ART_pistol,112,104,100,202+bob+recoil,112,104,.9f,0,0);
    if(fireTimer>4){
        for(int yy=-11;yy<=11;++yy)for(int xx=-14;xx<=14;++xx)
            if(abs(xx)+abs(yy)<14||(abs(xx)<3&&abs(yy)<11)){
                int px=157+xx,py=206+yy;
                fb[py*SCREEN_W+px]=abs(xx)+abs(yy)<7?color(255,238,171):color(230,121,43);
            }
    }
    rect(fb,115,149,3,1,color(203,208,183));rect(fb,122,149,3,1,color(203,208,183));
    rect(fb,120,144,1,3,color(203,208,183));rect(fb,120,152,1,3,color(203,208,183));
    if(hurtTimer)for(int py=18;py<298;++py)for(int px=0;px<SCREEN_W;++px)
        if(px<7||px>232||py<24||py>291)fb[py*SCREEN_W+px]=color(133,25,23);
    // Portrait HUD uses two compact rows; world is 240x320 with no rotation buffer.
    rect(fb,0,0,SCREEN_W,18,color(15,17,20));rect(fb,0,298,SCREEN_W,22,color(15,17,20));
    char label[80];sprintf(label,"WAVE %02d",wave);text(fb,8,5,label,color(200,73,51));
    sprintf(label,"PTS %05d",points);text(fb,85,5,label,color(211,205,175));
    sprintf(label,"K %03d",kills);text(fb,192,5,label,color(159,169,159));
    sprintf(label,"HP %03d",health);text(fb,8,302,label,color(205,103,79));
    rect(fb,8,315,health/2,3,color(158,52,43));
    sprintf(label,"%02d  %03d",ammo,reserve);text(fb,173,302,label,color(217,209,175));
    text(fb,73,313,"5 FIRE 0 LOAD 7 USE",color(125,136,136));
    if(messageTimer&&phase==RUNNING)text(fb,(SCREEN_W-(int)strlen(message)*6)/2,30,message,color(224,199,133));
    if(breakTimer){sprintf(label,"NEXT WAVE %d",(breakTimer+29)/30);text(fb,80,52,label,color(215,194,129));}
    if(phase==TITLE||phase==GUIDE||phase==DEAD||phase==PAUSED){
        for(int i=0;i<SCREEN_W*SCREEN_H;++i)fb[i]=shade(fb[i],.37f);
        rect(fb,12,70,216,178,color(18,20,23));rect(fb,12,70,216,2,color(161,66,42));
        if(phase==TITLE){text(fb,48,87,"NIGHTFALL",color(215,205,174),2);text(fb,60,111,"SURVIVAL",color(192,78,51),2);
            const char* items[]={"PLAY","HOW TO PLAY","EXIT"};for(int i=0;i<3;++i){if(i==selected)rect(fb,36,148+i*24,168,18,color(55,49,38));text(fb,48,153+i*24,items[i],color(215,210,184));}
        }else if(phase==GUIDE){
            const char* lines[]={"SURVIVE EVERY WAVE","2 8 MOVE   4 6 TURN","1 3 STRAFE   5 FIRE","0 RELOAD   7 INTERACT","9 PAUSE   BACK MENU","GATE 500   AMMO 200","MEDKIT 300  REPAIR WINDOWS"};
            for(int i=0;i<7;++i)text(fb,28,88+i*20,lines[i],color(211,204,180));
        }else if(phase==DEAD){text(fb,48,92,"YOU FELL",color(191,65,44),3);sprintf(label,"WAVE %d  KILLS %d",wave,kills);text(fb,45,145,label,color(209,198,171));sprintf(label,"POINTS %d",points);text(fb,60,166,label,color(209,198,171));text(fb,45,201,"5 RETRY   BACK MENU",color(197,189,164));}
        else{text(fb,66,108,"PAUSED",color(214,202,172),3);text(fb,45,169,"9 RESUME  BACK MENU",color(198,190,165));}
        text(fb,36,273,"VXPSTORE ALL RIGHTS RESERVED",color(148,141,122));
    }
}
