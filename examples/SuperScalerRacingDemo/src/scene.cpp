#include "scene.h"
#include "font.h"
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSuperScaler.h"
#include "pixel_art_tiles.h"
#include <stdio.h>
#include <string.h>

namespace {
enum { BLACK=0x0000, SKY=0x3D7F, SUN=0xFEA8, SAND=0xB425, ROAD0=0x7BCF,
       ROAD1=0x9CD3, RED=0xE986, WHITE=0xFFFF, CYAN=0x5F7B, BIKE=0xF2A8,
       DARK=0x2106, GREEN=0x3D67, ROCK=0x9B66, ROCK_LIT=0xC42A,
       ASPHALT_DARK=0x4A49, ASPHALT_LIT=0x8C51, DUST_DARK=0x8B04 };
static void rect(uint16_t*f,int x,int y,int w,int h,uint16_t c){vxpe2d_fill_rect(f,240,320,x,y,w,h,c);}
static void text(uint16_t*f,int x,int y,const char*s,uint16_t c){for(;*s;++s,x+=6){int ch=*s;int i=ch>='A'&&ch<='Z'?ch-'A':ch>='0'&&ch<='9'?26+ch-'0':-1;if(i>=0&&i<36){for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))rect(f,x+xx,y+yy,1,1,c);}else if(ch==':'){rect(f,x+2,y+1,1,1,c);rect(f,x+2,y+5,1,1,c);}}}
static void centered(uint16_t*f,int y,const char*s,uint16_t c){text(f,(240-(int)strlen(s)*6)/2,y,s,c);}
static void circle(uint16_t*f,int cx,int cy,int r,uint16_t c){for(int y=-r;y<=r;++y){int x=0;while((x+1)*(x+1)+y*y<=r*r)++x;rect(f,cx-x,cy+y,2*x+1,1,c);}}
static void ellipse(uint16_t*f,int cx,int cy,int rx,int ry,uint16_t c){if(rx<1||ry<1)return;const int limit=rx*rx*ry*ry;for(int y=-ry;y<=ry;++y){int x=rx;while(x>0&&x*x*ry*ry+y*y*rx*rx>limit)--x;rect(f,cx-x,cy+y,2*x+1,1,c);}}
static void mesa(uint16_t*f,int x,int y,int w,int h,uint16_t shade){
    static const uint8_t profile[16]={7,9,9,9,10,11,12,13,14,15,16,16,16,16,16,16};
    for(int row=0;row<h;++row){int band=row>>1;if(band>15)band=15;int half=w*profile[band]>>5;rect(f,x-half,y+row,2*half+1,1,shade);if((row&3)==1)rect(f,x-half+2,y+row,2*half-4,1,ROCK_LIT);}
    rect(f,x-w/4,y+h/2,w/2,1,ROCK);rect(f,x-w/3,y+(h*3)/4,w/3,1,ROCK_LIT);
    rect(f,x-w/5,y+h/3,1,h/5,DUST_DARK);rect(f,x+w/6,y+h/2,1,h/4,DUST_DARK);
}
static void cactus(uint16_t*f,int x,int y,int h){
    const int w=(h/4)>1?h/4:1;
    rect(f,x-w*2,y+1,w*4,1,0x82E4);
    rect(f,x-w/2,y-h,w,h,GREEN);rect(f,x-w/2+1,y-h,w/2,h-1,0x55C9);
    if(h>5){rect(f,x-w*2,y-h/2,w*2,h/5,GREEN);rect(f,x-w*2,y-h/2,w/2,h/2,GREEN);rect(f,x+w/2,y-h*3/4,w*2,h/5,GREEN);rect(f,x+w,y-h*3/4,w/2,h/2,GREEN);}
    rect(f,x-w/2,y-h,1,h/2,0x7E09);
}
static void boulder(uint16_t*f,int x,int y,int s){
    ellipse(f,x,y+1,s,s/2+1,0x7A82);rect(f,x-s,y-s/2,s*2,s/2+1,ROCK);rect(f,x-s/2,y-s,s,s/2+1,ROCK_LIT);rect(f,x-s,y,s,1,DUST_DARK);
}
static void bike(uint16_t*f,int x,int y,int scale,uint16_t color,bool player){
    if(scale<2)scale=2;const int r=scale/2?scale/2:1;
    ellipse(f,x,y+5*scale+2,scale*2,scale/2+1,0x4208);
    circle(f,x,y+5*scale,r+2,DARK);rect(f,x-r/2,y+4*scale,((r/2)>0?r/2:1),3*scale,0x7BCF);
    circle(f,x,y-3*scale,r+2,DARK);circle(f,x,y-3*scale,r,0xBDF7);
    rect(f,x-scale/2,y-3*scale,scale,7*scale,color);rect(f,x-scale/2,y-2*scale,scale/3?scale/3:1,5*scale,player?0xFEA8:0x85B2);
    rect(f,x-scale,y-2*scale,2*scale,2*scale,WHITE);rect(f,x-scale,y-2*scale,scale,scale,player?0xFDC4:0xD6DB);
    rect(f,x-scale/2,y-6*scale,scale,2*scale,player?0xFBE7:0x4208);
    circle(f,x,y-7*scale,scale/2?scale/2:1,player?CYAN:RED);rect(f,x-2*scale,y-scale/2,4*scale,scale/2?scale/2:1,SUN);
    rect(f,x-scale/2,y+2*scale,scale,scale,player?RED:0xFEA8);
}
}

SuperScalerGame::SuperScalerGame():player_x(0),speed(52),phase(0),tick(0),distance(0),score(0),bestScore(0),mode(0),exiting(false){
    rivals[0]={-64,75,0};rivals[1]={72,165,1};rivals[2]={-12,228,2};
}
void SuperScalerGame::loadBest(uint16_t value){bestScore=value;}
void SuperScalerGame::input(int key){if(key<0){if(mode==1)mode=2;else if(mode==2)mode=1;else exiting=true;return;}if(mode==0){if(key==5||key==2||key==8)mode=1;return;}if(mode==2){if(key==5||key==9)mode=1;else if(key==0)mode=0;return;}if(mode!=1)return;if(key==4)player_x-=14;if(key==6)player_x+=14;if(key==2&&speed<100)speed+=8;if(key==8&&speed>18)speed-=10;if(key==5)speed=100;if(key==9)mode=2;if(key==0)mode=0;if(player_x< -100)player_x=-100;if(player_x>100)player_x=100;}
void SuperScalerGame::update(){if(mode!=1)return;++tick;phase=(uint16_t)(phase+speed/8);distance=(uint16_t)(distance+speed/16);if((tick%48)==0)score+=speed;for(int i=0;i<3;++i){rivals[i].depth=(uint16_t)(rivals[i].depth+1+(speed>>5));if(rivals[i].depth>255){rivals[i].depth=16;rivals[i].lane_q8=(int16_t)(((tick*(i+3)*37)%193)-96);score+=25;}}if(score>bestScore)bestScore=score;}
void SuperScalerGame::draw(uint16_t*f)const{if(!f)return;
    VxpeSuperScalerConfig c{};c.horizon_y=108;c.center_x=120;c.far_half_width=5;c.near_half_width=119;
    const int turn=((tick/96)%2)?-1:1;c.curve_q8=(int16_t)(turn*(int)(20+((tick/12)%24))*256);c.road_phase=phase;c.curb_period=18;
    c.sky565=SKY;c.ground565=SAND;c.road_a565=ROAD0;c.road_b565=ROAD1;c.curb_a565=0xE8C4;c.curb_b565=WHITE;c.lane565=0xF7DE;
    c.road_texture=VXPE_ROAD_TILE_RGB565;c.road_texture_w=8;c.road_texture_h=8;c.ground_texture=VXPE_SAND_TILE_RGB565;c.ground_texture_w=8;c.ground_texture_h=8;
    (void)vxpe_superscaler_draw(f,240,320,240,&c);
    /* Pixel-art sunset, layered mesas and atmospheric distance bands. */
    circle(f,190,72,21,0xFE68);circle(f,190,72,17,0xFEA8);rect(f,185,68,10,2,0xFF31);rect(f,186,75,8,2,0xFBE7);
    rect(f,18,50,18,2,0x7E5F);rect(f,12,52,28,2,0x7E5F);rect(f,184,42,24,2,0x4D7F);rect(f,178,44,36,2,0x4D7F);
    mesa(f,22,88,62,27,0x8450);mesa(f,89,92,75,25,0x7BCE);mesa(f,224,87,74,29,0x9452);
    rect(f,0,108,240,3,0xC4C3);rect(f,0,111,240,2,0xB4A2);
    /* Six fixed roadside props move toward camera at speed; size follows depth. */
    for(int i=0;i<6;++i){int z=(i*47+(phase>>1))%250;int q=z*z/250;int y=111+q*197/255;int roadCenter=120+(int)(c.curve_q8*q/65536);int half=5+q*114/255;int side=(i&1)?1:-1;int x=roadCenter+side*(half+4+q/12);int h=3+q/10;if(i%3==0)boulder(f,x,y,h/2+1);else cactus(f,x,y,h);}
    for(int z=0;z<256;z+=8)for(int i=0;i<3;++i)if(rivals[i].depth/8==(unsigned)z/8){int q=(int)rivals[i].depth*rivals[i].depth/255;int y=108+q*202/255;int center=120+(int)(c.curve_q8*q/65536);int half=5+q*114/255;int x=center+(int)rivals[i].lane_q8*half/256;int scale=1+q/28;bike(f,x,y,scale,rivals[i].color?0x2D7B:RED,false);}
    bike(f,120+player_x,256,6,BIKE,true);
    rect(f,5,5,230,30,BLACK);rect(f,5,5,230,1,SUN);text(f,12,11,"SUPER SCALER",WHITE);char n[24];snprintf(n,sizeof(n),"SPD:%03u",speed);text(f,154,11,n,SUN);snprintf(n,sizeof(n),"DIST:%04u",distance);text(f,12,22,n,WHITE);snprintf(n,sizeof(n),"PTS:%04u",score);text(f,160,22,n,CYAN);
    if(mode==0){rect(f,24,119,192,92,BLACK);rect(f,25,120,190,2,SUN);centered(f,137,"HORIZON RIDER",WHITE);centered(f,156,"ARCADE ROAD TRIAL",SUN);centered(f,179,"5 START",WHITE);snprintf(n,sizeof(n),"BEST %04u",bestScore);centered(f,194,n,CYAN);}
    if(mode==2){rect(f,36,135,168,52,BLACK);rect(f,37,136,166,2,SUN);centered(f,151,"PAUSED",WHITE);centered(f,169,"9 RESUME / 0 MENU",CYAN);}
    rect(f,0,295,240,25,BLACK);text(f,8,301,"4 6 STEER   2 SPEED  8 BRAKE",WHITE);text(f,48,311,"5 BOOST       9 PAUSE",SUN);
}
