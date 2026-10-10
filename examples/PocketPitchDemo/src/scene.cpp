#include "scene.h"
#include "font.h"
#include "graphics/VxpRender2D.h"
#include <stdio.h>
#include <string.h>

namespace {
enum Color { NIGHT=0x088D, DEEP=0x10F1, PANEL=0x10D2, GREEN0=0x2588, GREEN1=0x2E4B,
  LINE=0xDFFF, MINT=0x7F35, GOLD=0xFEA8, ORANGE=0xF3C5, PINK=0xF1B2, ICE=0x8F7D, WHITE=0xFFFF };
static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static void rect(uint16_t* f,int x,int y,int w,int h,uint16_t c){vxpe2d_fill_rect(f,240,320,x,y,w,h,c);}
static void line(uint16_t* f,int x0,int y0,int x1,int y1,uint16_t c){int dx=x1-x0,dy=y1-y0,steps=(dx<0?-dx:dx)>(dy<0?-dy:dy)?(dx<0?-dx:dx):(dy<0?-dy:dy);if(!steps){rect(f,x0,y0,1,1,c);return;}for(int i=0;i<=steps;++i)rect(f,x0+dx*i/steps,y0+dy*i/steps,1,1,c);}
static void ring(uint16_t* f,int cx,int cy,int r,uint16_t c){int x=r,y=0,err=1-r;while(x>=y){rect(f,cx+x,cy+y,1,1,c);rect(f,cx+y,cy+x,1,1,c);rect(f,cx-y,cy+x,1,1,c);rect(f,cx-x,cy+y,1,1,c);rect(f,cx-x,cy-y,1,1,c);rect(f,cx-y,cy-x,1,1,c);rect(f,cx+y,cy-x,1,1,c);rect(f,cx+x,cy-y,1,1,c);++y;if(err<0)err+=2*y+1;else{--x;err+=2*(y-x)+1;}}}
static int isqrt(int n);
static void ellipse(uint16_t* f,int cx,int cy,int rx,int ry,uint16_t c){for(int x=-rx;x<=rx;++x){int yy=ry*isqrt(rx*rx-x*x)/rx;rect(f,cx+x,cy-yy,1,1,c);rect(f,cx+x,cy+yy,1,1,c);}}
static void fillcircle(uint16_t* f,int cx,int cy,int r,uint16_t c){for(int y=-r;y<=r;++y){int x=0;while((x+1)*(x+1)+y*y<=r*r)++x;rect(f,cx-x,cy+y,2*x+1,1,c);}}
static int isqrt(int n){if(n<=0)return 0;unsigned x=(unsigned)n, r=0, bit=1u<<30;while(bit>x)bit>>=2;while(bit){if(x>=r+bit){x-=r+bit;r=(r>>1)+bit;}else r>>=1;bit>>=2;}return (int)r;}
static void text(uint16_t* f,int x,int y,const char* s,uint16_t color,int scale=1){for(;*s;++s,x+=6*scale){int ch=*s;int i=ch>='A'&&ch<='Z'?ch-'A':ch>='0'&&ch<='9'?26+ch-'0':-1;if(i<0)continue;for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))rect(f,x+xx*scale,y+yy*scale,scale,scale,color);}}
static void centered(uint16_t* f,int y,const char* s,uint16_t c,int scale=1){int len=(int)strlen(s);text(f,(240-len*6*scale+scale)/2,y,s,c,scale);}
static void hudbar(uint16_t* f,int x,int y,int w,uint16_t a,uint16_t b){rect(f,x,y,w,8,0x0000);rect(f,x+1,y+1,w-2,6,a);rect(f,x+1,y+1,(w-2)/2,2,b);}
static void football(uint16_t* f,int x,int y,int r){fillcircle(f,x+1,y+2,r+1,0x0841);fillcircle(f,x,y,r,0xFFFF);fillcircle(f,x-1,y-1,r-2,0xEF7D);fillcircle(f,x,y,r/3,0x3186);line(f,x-r/2,y-r/2,x,y-r/3,0x3186);line(f,x+r/2,y-r/2,x,y-r/3,0x3186);line(f,x-r/2,y+r/2,x,y+r/3,0x3186);line(f,x+r/2,y+r/2,x,y+r/3,0x3186);}
static void bumper(uint16_t* f,int x,int y,int r,int tick,int kind){uint16_t hi=kind==0?GOLD:kind==1?ICE:kind==2?PINK:MINT;fillcircle(f,x+1,y+2,r+2,0x0841);fillcircle(f,x,y,r+1,0x73B0);fillcircle(f,x,y,r-2,PANEL);fillcircle(f,x,y,r-4,hi);fillcircle(f,x-2,y-2,r/3,WHITE);ring(f,x,y,r+1,0xC6FC);if((tick/5)%2==0)fillcircle(f,x,y,2,WHITE);}
static void player(uint16_t* f,int x,int y,bool home,int pose){uint16_t jersey=home?0x22DE:0xF2A9,trim=home?0xBFFF:GOLD;fillcircle(f,x+1,y+2,7,0x0841);fillcircle(f,x,y,6,0x18E3);rect(f,x-5,y-4,10,8,jersey);rect(f,x-4,y-4,8,2,trim);rect(f,x-4,y+4,3,5,0x294A);rect(f,x+1,y+4,3,5,0x294A);rect(f,x-5,y+7,4,2,WHITE);rect(f,x+1,y+7,4,2,WHITE);rect(f,x-2+(pose%3)-1,y-2,1,2,WHITE);}
static void goalFrame(uint16_t* f,int x,int y,bool top){int w=53,h=12;rect(f,x-2,y-2,w+4,h+4,0x0841);rect(f,x,y,w,h,0xC6D8);rect(f,x+3,y+2,w-6,h-4,0x108F);for(int xx=x+6;xx<x+w-4;xx+=8)line(f,xx,y+2,xx,y+h-2,0x6B75);for(int yy=y+4;yy<y+h-2;yy+=4)line(f,x+3,yy,x+w-3,yy,0x6B75);rect(f,x-1,top?y+h-1:y, w+2,2,GOLD);}
}

PocketPitch::PocketPitch():mode(0),tick(0),score(0),best(0),goals(0),seconds(45),serveTicks(0),ballX(120*256),ballY(265*256),ballVx(0),ballVy(0),spin(0),keeperX(120),keeperDir(1),leftKick(0),rightKick(0),flash(0),skillLeft(2),skillRight(2),skillCooldown(0),aim(0),combo(0),exiting(false),loadedBest(false){bumpers[0]={78,104,11,0};bumpers[1]={162,104,11,1};bumpers[2]={120,151,13,2};bumpers[3]={78,198,11,3};bumpers[4]={162,198,11,4};memset(particles,0,sizeof(particles));}
void PocketPitch::loadBest(int value){if(value>best)best=value;loadedBest=true;}
void PocketPitch::newMatch(){mode=1;tick=0;score=0;goals=0;seconds=45;combo=0;skillLeft=2;skillRight=2;skillCooldown=0;aim=0;flash=0;memset(particles,0,sizeof(particles));serve();}
void PocketPitch::serve(){ballX=(120+(aim?aim*4:0))*256;ballY=266*256;ballVx=0;ballVy=0;spin=0;serveTicks=20;leftKick=rightKick=0;}
void PocketPitch::shoot(int side){if(mode!=1)return;if(serveTicks>0){serveTicks=0;ballVy=-3*256;ballVx=side<0?-96:side>0?96:aim*40;leftKick=rightKick=0;emit(ballX/256,ballY/256,GOLD,7);return;}if(ballY/256>224){ballVy=-4*256;ballVx=(side*2+aim)*96;if(ballVx>650)ballVx=650;if(ballVx< -650)ballVx=-650;spin=side*2;leftKick=side<0?8:0;rightKick=side>0?8:0;combo++;emit(ballX/256,ballY/256,side<0?ICE:ORANGE,8);}}
void PocketPitch::input(int key){if(key<0){if(mode==0)exiting=true;else if(mode==1)mode=2;else if(mode==2)mode=1;else mode=0;return;}if(mode==0){if(key==5||key==2||key==8)newMatch();return;}if(mode==2){if(key==5||key==9)mode=1;else if(key==0)mode=0;return;}if(mode==3){if(key==5||key==0)newMatch();else if(key==9)mode=0;return;}if(mode!=1)return;if(key==9){mode=2;return;}if(key==0){mode=0;return;}if(key==2&&serveTicks>0&&aim<3)aim++;if(key==8&&serveTicks>0&&aim> -3)aim--;if(key==4)shoot(-1);if(key==6)shoot(1);if(key==5)shoot(0);if(key==1&&skillLeft>0&&skillCooldown==0&&serveTicks==0){spin-=5;skillLeft--;skillCooldown=75;emit(ballX/256,ballY/256,ICE,6);}if(key==3&&skillRight>0&&skillCooldown==0&&serveTicks==0){spin+=5;skillRight--;skillCooldown=75;emit(ballX/256,ballY/256,ORANGE,6);}}
void PocketPitch::touch(int x,int y){if(mode==0||mode==3){input(5);return;}if(mode==2){input(y>170?0:9);return;}if(y<40){input(9);return;}if(y>218){if(x<112)input(4);else if(x>128)input(6);else input(5);}else if(x<92)input(1);else if(x>148)input(3);}
void PocketPitch::emit(int x,int y,uint16_t color,int count){for(int n=0;n<count;++n){for(int i=0;i<FX_COUNT;++i)if(!particles[i].life){Particle& p=particles[i];p.x=(int16_t)x;p.y=(int16_t)y;p.vx=(int16_t)(((tick*17+i*29+n*11)%7)-3);p.vy=(int16_t)(-1-((tick+i+n)%4));p.life=(uint8_t)(8+(i*3+n)%8);p.color=color;break;}}}
void PocketPitch::goal(){goals++;score+=100+combo*10;if(score>best)best=score;combo++;flash=42;emit(ballX/256,ballY/256,GOLD,FX_COUNT);serve();}
void PocketPitch::update(){if(mode!=1)return;++tick;if(tick%30==0&&seconds>0)seconds--;if(flash>0)--flash;if(leftKick>0)--leftKick;if(rightKick>0)--rightKick;if(skillCooldown>0)--skillCooldown;if(serveTicks>0){--serveTicks;if(serveTicks==0){ballVy=-3*256;ballVx=aim*48;emit(ballX/256,ballY/256,WHITE,4);}}
 keeperX+=keeperDir*(1+(goals>1));if(keeperX<99){keeperX=99;keeperDir=1;}if(keeperX>141){keeperX=141;keeperDir=-1;}
 if(serveTicks==0){ballVx+=spin*5;spin=spin*15/16;if(ballVx>720)ballVx=720;if(ballVx< -720)ballVx=-720;ballX+=ballVx;ballY+=ballVy;
 int x=ballX/256,y=ballY/256;if(x<38){ballX=38*256;ballVx=(ballVx<0?-ballVx:ballVx)*3/4;emit(x,y,ICE,3);}if(x>202){ballX=202*256;ballVx=-(ballVx>0?ballVx:-ballVx)*3/4;emit(x,y,ICE,3);}
 if(y<54){if(x>keeperX-18&&x<keeperX+18&&y>45){ballY=56*256;ballVy=ballVy<0?-ballVy*3/4:ballVy;ballVx+=(x<keeperX?-220:220);combo=0;emit(x,y,WHITE,5);}else if(y<45&&x>95&&x<145){goal();}else if(y<52&&(x<=95||x>=145)){ballY=52*256;ballVy=ballVy<0?-ballVy*3/4:ballVy;}}
 if(y>267){ballY=267*256;ballVy=ballVy>0?-ballVy*3/4:ballVy;if(y>281){serve();combo=0;}}
 for(int i=0;i<BUMPER_COUNT;++i){int dx=x-bumpers[i].x,dy=y-bumpers[i].y,rr=bumpers[i].r+5,d2=dx*dx+dy*dy;if(d2<rr*rr&&d2>0){int d=isqrt(d2);int dot=ballVx*dx+ballVy*dy;if(dot<0){ballVx-=2*dot*dx/(d2+1);ballVy-=2*dot*dy/(d2+1);}else{ballVx+=dx*70/(d+1);ballVy+=dy*70/(d+1);}if(ballVx>700)ballVx=700;if(ballVx< -700)ballVx=-700;if(ballVy>700)ballVy=700;if(ballVy< -700)ballVy=-700;score+=3;emit(x,y,i==0||i==4?GOLD:i==1?ICE:PINK,4);}}
 }
 for(int i=0;i<FX_COUNT;++i){Particle& p=particles[i];if(p.life){p.x+=p.vx;p.y+=p.vy;p.vy++;--p.life;}}
 if(seconds==0){mode=3;ballVx=ballVy=0;}
}

void PocketPitch::draw(uint16_t* f)const{
 if(!f)return;vxpe2d_gradient_vertical(f,240,320,0,0,240,320,0x084A,0x10B4);
 // Stadium trim and softly lit upper deck.
 for(int i=0;i<8;++i){rect(f,8+i*30,25,14,2,(i&1)?MINT:GOLD);rect(f,12+i*30,29,3,2,0x7D17);}rect(f,12,35,216,258,0x0841);rect(f,14,34,212,255,0x52CF);rect(f,17,37,206,249,0xC6FC);
 goalFrame(f,94,39,true);
 // Two-tone clipped pitch with broadcast stripes and clean field markings.
 for(int y=51;y<277;y+=18){int inset=(y-51)*13/225;rect(f,40-inset,y,160+2*inset,18,((y-51)/18)&1?GREEN1:GREEN0);}
 line(f,40,51,27,276,0x42AF);line(f,200,51,213,276,0x42AF);line(f,40,51,200,51,0x42AF);line(f,27,276,213,276,0x42AF);
 line(f,35,163,205,163,0x9FFF);ellipse(f,120,163,24,17,0x9FFF);fillcircle(f,120,163,2,0xEFFF);
 line(f,88,51,81,81,0xBFFF);line(f,152,51,159,81,0xBFFF);line(f,81,81,159,81,0xBFFF);ellipse(f,120,81,10,6,0xBFFF);
 line(f,73,245,70,276,0xBFFF);line(f,167,245,170,276,0xBFFF);line(f,73,245,167,245,0xBFFF);ellipse(f,120,245,10,6,0xBFFF);
 // Pinball bumpers have hard highlights and coloured cores.
 for(int i=0;i<BUMPER_COUNT;++i)bumper(f,bumpers[i].x,bumpers[i].y,bumpers[i].r,tick+i*3,bumpers[i].kind);
 // Tiny original teams and an animated keeper.
 player(f,88,66,false,tick/6);player(f,152,66,false,tick/6+1);player(f,76,229,true,tick/6);player(f,164,229,true,tick/6+2);player(f,keeperX,57,false,tick/4);
 goalFrame(f,94,39,true);goalFrame(f,94,271,false);
 // Flipper bats.
 int lk=leftKick?10:0,rk=rightKick?10:0;line(f,66,253,103+lk,257,0x0841);line(f,66,251,103+lk,255,GOLD);line(f,174,253,137-rk,257,0x0841);line(f,174,251,137-rk,255,ICE);
 for(int i=0;i<FX_COUNT;++i)if(particles[i].life){int r=particles[i].life>5?2:1;fillcircle(f,particles[i].x,particles[i].y,r,particles[i].color);}
 football(f,ballX/256,ballY/256,5);
 // Score rail.
 rect(f,8,5,224,27,0x0841);rect(f,9,6,222,25,0x10D2);rect(f,9,6,3,25,MINT);
 text(f,17,10,"POCKET PITCH",WHITE,1);char n[20];snprintf(n,sizeof(n),"TIME %02d",seconds);text(f,170,10,n,GOLD);snprintf(n,sizeof(n),"GOALS %02d",goals);text(f,16,21,n,0xAFFF);snprintf(n,sizeof(n),"BEST %04d",best);text(f,157,21,n,0xAFFF);
 if(flash>0){rect(f,57,115,126,28,0x0841);rect(f,59,117,122,24,0xFBE7);centered(f,125,"GOAL!  +100",0x0841,2);}
 if(mode==0){rect(f,20,93,200,151,0x0841);rect(f,22,95,196,147,0x10D2);rect(f,22,95,196,2,MINT);centered(f,112,"POCKET",WHITE,3);centered(f,139,"PITCH",GOLD,3);centered(f,169,"PINBALL SOCCER",0xAFFF);rect(f,51,193,138,24,0x2D95);rect(f,51,193,138,2,GOLD);centered(f,202,"5  KICK OFF",WHITE);centered(f,228,"AIM 2 8  -  BEST SCORE",0x9FB5);}
 if(mode==2){vxpe2d_overlay_rect(f,240,320,0,0,240,320,0x0000,155,VXPE_BLEND_ALPHA);rect(f,38,129,164,62,0x0841);rect(f,40,131,160,58,0x10D2);rect(f,40,131,160,2,GOLD);centered(f,143,"MATCH PAUSED",WHITE,2);centered(f,169,"9 RESUME   0 MENU",0xAFFF);}
 if(mode==3){vxpe2d_overlay_rect(f,240,320,0,0,240,320,0x0000,155,VXPE_BLEND_ALPHA);rect(f,29,107,182,106,0x0841);rect(f,31,109,178,102,0x10D2);rect(f,31,109,178,2,GOLD);centered(f,122,"FULL TIME",WHITE,2);snprintf(n,sizeof(n),"GOALS %02d",goals);centered(f,153,n,GOLD,2);snprintf(n,sizeof(n),"SCORE %04d",score);centered(f,175,n,0xAFFF);centered(f,195,"5 REPLAY  9 TITLE",WHITE);}
 // Bottom controls, outside the pitch, stay readable on native 240x320.
 rect(f,0,289,240,31,0x0841);rect(f,0,289,240,1,0x6B73);text(f,8,296,"4 6 FLIP  5 KICK  1 3 CURVE",0xDFFF);text(f,73,309,"9 PAUSE  0 MENU",0x8F96);
 if(mode==1&&skillCooldown){rect(f,207,258,4,18,0x0841);rect(f,208,274-skillCooldown*18/75,2,skillCooldown*18/75,ORANGE);}
}
