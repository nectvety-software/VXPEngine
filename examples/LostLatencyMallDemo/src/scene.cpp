#include "scene.h"
#include "font.h"
#include "graphics/VxpRaycast3D.h"
#include "graphics/VxpRender2D.h"
#include <array>
#include <string.h>
#include <stdio.h>

namespace {
static const int16_t SIN_Q14[32]={0,3196,6270,9102,11585,13623,15137,16069,16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196};
static const int16_t COS_Q14[32]={16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196,0,3196,6270,9102,11585,13623,15137,16069};
static const int SCAN_Z[4]={150,390,650,910};
static const int SCAN_X[4]={-108,108,-108,108};
static const char* MEMORY_NAME[4]={"ATRIUM ARCHIVE","ARCADE MEMORY","SHARED TABLE","AQUARIUM WALK"};
static const char* MEMORY_LINE[4]={"ARRIVAL IS A KIND OF HOME","THE SOUND OF PLAY RETURNS","A TABLE HOLDS MANY NAMES","WATER REMEMBERS THE SKY"};
static const uint32_t QR_BITS[4]={0x15D3B6Du,0x1CA6B59u,0x12E5D2Bu,0x1B4D36Fu};
enum { NAVY=0x10B3,DARK=0x10A2,GOLD=0xF6A8,MINT=0x5F5A,GLASS=0x96FD,CORAL=0xF2A6,AQUA=0x56F7,IVORY=0xF7F1 };
static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static void rect(uint16_t* f,int x,int y,int w,int h,uint16_t c){vxpe2d_fill_rect(f,240,320,x,y,w,h,c);}
static void text(uint16_t* f,int x,int y,const char* s,uint16_t c,int scale=1){for(;*s;++s,x+=6*scale){int ch=*s,i=ch>='A'&&ch<='Z'?ch-'A':ch>='0'&&ch<='9'?26+ch-'0':-1;if(i<0)continue;for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))rect(f,x+xx*scale,y+yy*scale,scale,scale,c);}}
static void center(uint16_t* f,int y,const char* s,uint16_t c,int scale=1){int n=(int)strlen(s);text(f,(240-n*6*scale+scale)/2,y,s,c,scale);}
static constexpr uint16_t c565(int r,int g,int b){return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
using Tile=std::array<uint16_t,16*16>;
static constexpr Tile makeTile(int kind){Tile out{};for(int y=0;y<16;++y)for(int x=0;x<16;++x){uint16_t c=0;
    if(kind==0){bool diagonal=((x+y)&7)<2;bool grout=(x==0||x==15||y==0||y==15);c=grout?c565(53,73,74):(diagonal?c565(96,126,119):(((x/4+y/4)&1)?c565(128,142,127):c565(104,126,118)));if((x==7||x==8)&&((y&3)==0))c=c565(209,177,111);}
    else if(kind==1){bool rib=(x<2||x>13||y<2||y>13);bool pane=((x/4)&1)==((y/4)&1);c=rib?c565(147,116,74):(pane?c565(49,101,121):c565(71,139,153));if(y==7||y==8)c=c565(194,164,103);}
    else if(kind==2){bool frame=x<2||x>13||y<2||y>13;c=frame?c565(164,119,72):(((x/4+y/4)&1)?c565(119,90,74):c565(83,79,80));if(y==5||y==10)c=c565(201,158,91);}
    else if(kind==3){bool bezel=x<3||x>12||y<2||y>13;c=bezel?c565(56,51,62):(((x+y)&3)<2?c565(54,110,150):c565(45,75,106));if(x==4&&y>4&&y<12)c=c565(211,69,139);}
    else if(kind==4){bool stripe=((x+y)&7)<2;c=stripe?c565(218,166,111):c565(157,103,80);if(y>12)c=c565(91,71,66);}
    else {bool wave=((x+2*y)&7)<2;c=wave?c565(109,201,213):c565(36,107,148);if((x%8)==0)c=c565(122,166,180);}
    out[y*16+x]=c;}return out;}
static constexpr Tile FLOOR_TILE=makeTile(0),CEILING_TILE=makeTile(1),WALL_ATRIUM=makeTile(1),WALL_SHOP=makeTile(2),WALL_ARCADE=makeTile(3),WALL_FOOD=makeTile(4),WALL_AQUARIUM=makeTile(5);
static const VxpeRaycastTexture WALL_TEXTURES[5]={{WALL_ATRIUM.data(),16,16,16},{WALL_SHOP.data(),16,16,16},{WALL_ARCADE.data(),16,16,16},{WALL_FOOD.data(),16,16,16},{WALL_AQUARIUM.data(),16,16,16}};
static const VxpeRaycastTexture FLOOR_TEXTURE={FLOOR_TILE.data(),16,16,16},ROOF_TEXTURE={CEILING_TILE.data(),16,16,16};
using SpritePixels=uint16_t[16*24];using SpriteAlpha=uint8_t[16*24];
struct PixelSprite {SpritePixels color;SpriteAlpha alpha;};
static constexpr PixelSprite makeSprite(int kind){PixelSprite s{};for(int y=0;y<24;++y)for(int x=0;x<16;++x){uint16_t c=0;bool on=false;
    if(kind==0){int dx=x-8;if(y>=13&&y<=23&&dx>=-1&&dx<=1){on=true;c=(y&2)?c565(123,84,54):c565(149,105,64);}int leafW=y<12?2+y:0;if(y<=14&&dx<leafW&&dx>-leafW){on=true;c=((x+y)&3)?c565(46,137,75):c565(97,183,79);}if(y<8&&((x+y*2)%9==0)){on=true;c=c565(139,207,97);}}
    else if(kind==1){if(y>=12&&y<=21&&x>=2+y/5&&x<=13-y/5){on=true;c=(y==12||y==21)?c565(174,144,91):c565(55,143,162);}if(y>=8&&y<13&&x>=5&&x<=10){on=true;c=c565(203,181,118);}if(y<9&&x>=7-(y/3)&&x<=8+(y/3)){on=true;c=c565(89,210,220);}}
    else if(kind==2){if(x>=3&&x<=12&&y>=2&&y<=22){on=true;c=(x==3||x==12||y==2||y==22)?c565(159,119,69):c565(44,51,51);}if(x>=5&&x<=10&&y>=5&&y<=16){on=true;c=c565(223,208,157);}if(x>=6&&x<=9&&y>=7&&y<=14&&((x+y)&1)){on=true;c=DARK;}if(y==18&&x>=5&&x<=10){on=true;c=c565(80,171,142);}}
    else if(kind==3){int dy=y-11;if((x>=3&&x<=12&&dy*dy<=31)||(x>=1&&x<=4&&y>=8&&y<=14)){on=true;c=((x+y)&3)?c565(62,191,217):c565(183,234,228);}if(x==11&&y==9){on=true;c=IVORY;}if(x==12&&y==9){on=true;c=DARK;}}
    else if(kind==4){if(x>=3&&x<=12&&y>=3&&y<=22){on=true;c=(x==3||x==12||y==3||y==22)?c565(130,88,60):c565(53,48,53);}if(x>=5&&x<=10&&y>=6&&y<=12){on=true;c=((x+y)&1)?c565(67,206,209):c565(242,87,162);}if(y>=15&&y<=17&&x>=5&&x<=10){on=true;c=GOLD;}}
    else {int half=(y<12)?(12-y):0;if(y>=4&&y<=12&&x>=8-half&&x<=8+half){on=true;c=((x/3)&1)?c565(223,157,100):c565(207,96,88);}if(y>=12&&y<=23&&x>=7&&x<=8){on=true;c=c565(144,103,67);}}
    int i=y*16+x;if(on){s.color[i]=c;s.alpha[i]=255;}}
    return s;}
static constexpr PixelSprite TREE=makeSprite(0),FOUNTAIN=makeSprite(1),QR_BOARD=makeSprite(2),FISH=makeSprite(3),ARCADE=makeSprite(4),UMBRELLA=makeSprite(5);
static const VxpeSpriteA8 SPRITES[6]={{TREE.color,TREE.alpha,16,24,16,16,0},{FOUNTAIN.color,FOUNTAIN.alpha,16,24,16,16,0},{QR_BOARD.color,QR_BOARD.alpha,16,24,16,16,0},{FISH.color,FISH.alpha,16,24,16,16,0},{ARCADE.color,ARCADE.alpha,16,24,16,16,0},{UMBRELLA.color,UMBRELLA.alpha,16,24,16,16,0}};
static constexpr std::array<uint8_t,6*24> makeMallMap(){std::array<uint8_t,6*24> m{};for(int z=0;z<24;++z){int wall=z<8?1:z<10?2:z<14?3:z<17?4:5;m[z*6]=m[z*6+5]=(uint8_t)wall;if(z==0||z==23)for(int x=0;x<6;++x)m[z*6+x]=1;}return m;}
static constexpr auto MALL_MAP=makeMallMap();
static int q8(int world){return world*4;}
static void lowText(uint16_t* f,int x,int y,const char* s,uint16_t c,int scale=1){for(;*s;++s,x+=6*scale){int ch=*s,i=ch>='A'&&ch<='Z'?ch-'A':ch>='0'&&ch<='9'?26+ch-'0':-1;if(i<0)continue;for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))vxpe2d_fill_rect(f,120,160,x+xx*scale,y+yy*scale,scale,scale,c);}}
struct BillboardItem {int x,z,bottom,width,height,kind,depth;};
}

LostLatencyMall::LostLatencyMall():mode(0),tick(0),worldX(0),worldZ(24),yaw(0),scanBits(0),scanFlash(0),nearest(-1),walked(0),exiting(false){}
void LostLatencyMall::restore(uint8_t saved){scanBits=saved&15;}
uint8_t LostLatencyMall::progress()const{return (uint8_t)(scanBits&15);}
void LostLatencyMall::scan(){if(nearest<0)return;int dx=worldX-SCAN_X[nearest],dz=worldZ-SCAN_Z[nearest];if(dx*dx+dz*dz>86*86)return;scanBits|=1<<nearest;scanFlash=100;}
void LostLatencyMall::input(int key){if(key<0){if(mode==0)exiting=true;else if(mode==1)mode=2;else mode=0;return;}if(mode==0){if(key==5){mode=1;return;}if(key==9)exiting=true;return;}if(mode==2){if(key==9||key==5)mode=1;else if(key==0)mode=0;return;}if(mode==3){if(key==0||key==5||key==9)mode=1;return;}if(mode!=1)return;if(key==9){mode=2;return;}if(key==0){mode=3;return;}if(key==4)yaw=(yaw+31)&31;if(key==6)yaw=(yaw+1)&31;if(key==5)scan();if(key==2||key==8){int d=key==2?5:-4;int nx=worldX+SIN_Q14[yaw]*d/16384,nz=worldZ+COS_Q14[yaw]*d/16384;if(nx< -125)nx=-125;if(nx>125)nx=125;if(nz<8)nz=8;if(nz>1050)nz=1050;walked+=((nx-worldX<0?worldX-nx:nx-worldX)+(nz-worldZ<0?worldZ-nz:nz-worldZ));worldX=nx;worldZ=nz;}}
void LostLatencyMall::touch(int x,int y){if(mode==0){input(5);return;}if(mode==2||mode==3){input(5);return;}if(y<34){input(9);return;}if(y>250){if(x<80)input(4);else if(x>160)input(6);else input(2);return;}if(x>90&&x<150&&y>105&&y<220)input(5);}
void LostLatencyMall::update(){if(mode!=1)return;++tick;if(scanFlash>0)--scanFlash;nearest=-1;int best=90*90;for(int i=0;i<4;++i){int dx=worldX-SCAN_X[i],dz=worldZ-SCAN_Z[i],d=dx*dx+dz*dz;if(d<best){best=d;nearest=i;}}}

void LostLatencyMall::renderWorld(){
    VxpeRaycastTarget target={worldPixels,WORLD_W,WORLD_H,WORLD_W,wallDepth};
    VxpeRaycastCamera cam;vxpe_raycast3d_camera_init(&cam,WORLD_W,WORLD_H,54,106);
    cam.x_q8=q8(worldX+192);cam.z_q8=q8(worldZ+256);cam.dir_x_q14=SIN_Q14[yaw];cam.dir_z_q14=COS_Q14[yaw];
    cam.plane_x_q14=(int16_t)((int32_t)COS_Q14[yaw]*10923/16384);cam.plane_z_q14=(int16_t)(-(int32_t)SIN_Q14[yaw]*10923/16384);cam.eye_height_q8=120;cam.max_distance_q8=6000;
    VxpeRaycastScene scene{};scene.map={MALL_MAP.data(),6,24,6};scene.wall_textures=WALL_TEXTURES;scene.wall_count=5;scene.floor_texture=FLOOR_TEXTURE;scene.ceiling_texture=ROOF_TEXTURE;scene.sky565=rgb(96,154,180);scene.fog565=rgb(104,145,135);scene.fog_near_q8=1900;scene.fog_far_q8=4700;scene.fog_strength=105;scene.dither_strength=5;
    vxpe_raycast3d_render(&target,&cam,&scene);
    BillboardItem items[24];int count=0;
    auto add=[&](int x,int z,int bottom,int width,int height,int kind){if(count>=24)return;int wx=q8(x+192),wz=q8(z+256);int d=((wx-cam.x_q8)*cam.dir_x_q14+(wz-cam.z_q8)*cam.dir_z_q14)/16384;items[count++]={x,z,bottom,width,height,kind,d};};
    if(worldZ<260&&worldZ>-30){add(0,174,0,52,42,1);add(-126,132,0,48,78,0);add(126,132,0,48,78,0);}
    if(worldZ<590&&worldZ>180)for(int x=-124;x<=124;x+=62)add(x,445,0,40,68,4);
    if(worldZ<810&&worldZ>460){for(int x=-82;x<=82;x+=164)add(x,716,0,74,88,5);}
    if(worldZ<1090&&worldZ>730)for(int k=0;k<5;++k)add((k&1)?52:-44,837+k*38+(tick%24)-12,92+(k%3)*26,30,18,3);
    for(int i=0;i<4;++i)if(SCAN_Z[i]>worldZ-120&&SCAN_Z[i]<worldZ+620&&!(scanBits&(1<<i)))add(SCAN_X[i],SCAN_Z[i]+4,0,34,50,2);
    // Back-to-front painter order; wall-depth columns still mask every sprite.
    for(int i=1;i<count;++i){BillboardItem v=items[i];int j=i;while(j>0&&items[j-1].depth<v.depth){items[j]=items[j-1];--j;}items[j]=v;}
    for(int i=0;i<count;++i){const BillboardItem& v=items[i];VxpeRaycastBillboard b={q8(v.x+192),q8(v.z+256),q8(v.bottom), (uint16_t)q8(v.width),(uint16_t)q8(v.height),0xFFFF,255};vxpe_raycast3d_billboard(&target,&cam,&SPRITES[v.kind],&b);}
}

void LostLatencyMall::draw(uint16_t* fb){if(!fb)return;renderWorld();vxpe2d_scale2x565(fb,240,320,worldPixels,WORLD_W,WORLD_H);
 rect(fb,0,0,240,34,0x0842);rect(fb,0,0,3,34,MINT);text(fb,10,7,"LOST IN LATENCY",IVORY);text(fb,11,21,"MEMORY QR",GLASS);char b[24];int got=0;for(int i=0;i<4;++i)got+=(scanBits>>i)&1;snprintf(b,sizeof(b),"%d/4",got);text(fb,196,12,b,GOLD,2);
 if(nearest>=0&&mode==1){int dx=worldX-SCAN_X[nearest],dz=worldZ-SCAN_Z[nearest];if(dx*dx+dz*dz<110*110){rect(fb,53,261,134,22,0x0842);rect(fb,53,261,134,2,GOLD);center(fb,269,(scanBits&(1<<nearest))?"5 REVISIT MEMORY":"5 SCAN MEMORY QR",IVORY);}}
 rect(fb,0,289,240,31,0x0842);rect(fb,0,289,240,1,0x7B98);text(fb,9,296,"4 6 TURN   2 8 WALK   5 SCAN",IVORY);text(fb,53,309,"0 JOURNAL    9 PAUSE",GLASS);
 if(scanFlash>0&&nearest>=0&&(scanBits&(1<<nearest))){rect(fb,31,43,178,29,0x0842);rect(fb,31,43,178,2,MINT);center(fb,50,"MEMORY RECOVERED",GOLD);}
 if(mode==0){rect(fb,18,81,204,157,0x0842);rect(fb,20,83,200,153,NAVY);rect(fb,20,83,200,2,MINT);center(fb,103,"LOST IN",IVORY,3);center(fb,132,"LATENCY",GOLD,3);center(fb,166,"THE MALL REMEMBERS",GLASS);center(fb,184,"SCAN FOUR QR MEMORIES",IVORY);rect(fb,53,204,134,23,0x36B5);rect(fb,53,204,134,2,GOLD);center(fb,212,"5 ENTER MALL",IVORY);}
 if(mode==2){vxpe2d_overlay_rect(fb,240,320,0,0,240,320,0x0000,150,VXPE_BLEND_ALPHA);rect(fb,32,123,176,72,NAVY);rect(fb,32,123,176,2,GOLD);center(fb,139,"PAUSED",IVORY,2);center(fb,169,"9 CONTINUE  0 EXIT",GLASS);}
 if(mode==3){vxpe2d_overlay_rect(fb,240,320,0,0,240,320,0x0000,155,VXPE_BLEND_ALPHA);rect(fb,16,61,208,207,NAVY);rect(fb,16,61,208,2,MINT);center(fb,73,"MEMORY JOURNAL",GOLD,2);for(int i=0;i<4;++i){text(fb,28,103+i*31,(scanBits&(1<<i))?MEMORY_NAME[i]:"QR MEMORY LOCKED",IVORY);if(scanBits&(1<<i))text(fb,34,115+i*31,MEMORY_LINE[i],GLASS);else text(fb,34,115+i*31,"WALK CLOSER TO SCAN",0x7B98);}center(fb,244,"5 OR 0 RETURN",IVORY);}
}
