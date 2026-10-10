#include "scene.h"
#include "font.h"
#include "graphics/VxpToon3D.h"
#include "graphics/VxpRender2D.h"
#include <string.h>
#include <stdio.h>

namespace {
static const int16_t SIN_Q14[32]={0,3196,6270,9102,11585,13623,15137,16069,16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196};
static const int16_t COS_Q14[32]={16384,16069,15137,13623,11585,9102,6270,3196,0,-3196,-6270,-9102,-11585,-13623,-15137,-16069,-16384,-16069,-15137,-13623,-11585,-9102,-6270,-3196,0,3196,6270,9102,11585,13623,15137,16069};
static const int SCAN_Z[4]={150,390,650,910},SCAN_X[4]={-108,108,-108,108};
static const char* MEMORY_NAME[4]={"OCEAN GARDEN","GLASS HARBOR","SKY ORCHARD","BLUE LAGOON"};
static const char* MEMORY_LINE[4]={"A CITY CAN BREATHE WITH WATER","LIGHT CURVES AROUND THE TOWERS","TREES TAKE ROOT ABOVE THE SEA","THE FUTURE IS SHARED"};
enum { NAVY=0x10B3,GOLD=0xF6A8,MINT=0x5F5A,GLASS=0x96FD,IVORY=0xF7F1 };
static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static void rect(uint16_t* f,int x,int y,int w,int h,uint16_t c){vxpe2d_fill_rect(f,240,320,x,y,w,h,c);}
static void text(uint16_t* f,int x,int y,const char* s,uint16_t c,int scale=1){for(;*s;++s,x+=6*scale){int ch=*s,i=ch>='A'&&ch<='Z'?ch-'A':ch>='0'&&ch<='9'?26+ch-'0':-1;if(i<0)continue;for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))rect(f,x+xx*scale,y+yy*scale,scale,scale,c);}}
static void center(uint16_t* f,int y,const char* s,uint16_t c,int scale=1){text(f,(240-(int)strlen(s)*6*scale+scale)/2,y,s,c,scale);}
static void material(VxpeToonMaterial3D& m,uint16_t color,uint16_t fog){vxpe_toon3d_material_init(&m,color);m.ink565=color;m.fog565=fog;m.fog_near_z=360;m.fog_far_z=1450;m.fog_alpha=100;m.outline_px=0;m.affine_depth=0;m.depth_bias=0;m.shadow_threshold=78;m.highlight_threshold=184;m.shadow_q8=150;m.midtone_q8=218;m.highlight_q8=255;}
static void quad(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,const VxpeToonMaterial3D& m,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,VxpeVec3D e,uint8_t light=225){VxpeVec3D v[4]={a,b,d,e};vxpe_toon3d_quad(&t,&c,v,&m,light);}
static void tri(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,const VxpeToonMaterial3D& m,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,uint8_t light=225){vxpe_toon3d_triangle(&t,&c,a,b,d,&m,light,0);}
static void quadG(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,const VxpeToonMaterial3D& m,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,VxpeVec3D e,const uint8_t light[4]){VxpeVec3D v[4]={a,b,d,e};vxpe_toon3d_quad_gouraud(&t,&c,v,&m,light);}
/* One sun for the whole scene, up and to the left, in front of the camera. Ring
 * corners take their illumination from the outward surface direction, so the lit
 * flank of every arcology, island and cloud is on the same side and the falloff
 * across a face is continuous; the previous per-quad value varied with the ring
 * index instead, which read as noise rather than light. The three cel bands still
 * quantise the result, so the toon look is unchanged. */
static const int SUN_X_Q14=-12400,SUN_Z_Q14=-9800;
static uint8_t sun_light(int corner){
    int k=(corner&15)*2;
    int32_t dot=((int32_t)SUN_X_Q14*COS_Q14[k]+(int32_t)SUN_Z_Q14*SIN_Q14[k])>>14;
    int32_t lit=132+dot*92/16384;
    return (uint8_t)(lit<40?40:lit>224?224:lit);
}
static VxpeVec3D point(int x,int y,int z){VxpeVec3D v={x,y,z};return v;}
static VxpeVec3D ring(int cx,int cy,int cz,int radius,int i){int k=(i&7)*4;return point(cx+(int32_t)COS_Q14[k]*radius/16384,cy,cz+(int32_t)SIN_Q14[k]*radius/16384);}
static VxpeVec3D ring16(int cx,int cy,int cz,int radius,int i){int k=(i&15)*2;return point(cx+(int32_t)COS_Q14[k]*radius/16384,cy,cz+(int32_t)SIN_Q14[k]*radius/16384);}
/* Ring rings are shared between the two levels that meet at them, so the shell
 * is one continuous surface: ring k sits at ys[k]/rs[k] with a single lean
 * offset RING_OX[k] used by both the level below and the level above. Building
 * each level from `x` at the bottom and a per-level bend at the top left a
 * radius and centre step at every joint, so the silhouette carried unfilled
 * overhangs that a back-facing ring quad could resolve differently frame to
 * frame. The glass stripe is a decal at the shell radius rather than a ring
 * pushed 2 units outside it: the core material depth_bias separates the two
 * coincident surfaces, so no protruding ledge exists to see through. */
static const int RING_OX[5]={0,0,2,8,18};
static void tower(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,int x,int z,int h,int r,const VxpeToonMaterial3D& white,const VxpeToonMaterial3D& glass,const VxpeToonMaterial3D& shade,const VxpeToonMaterial3D& band){
    int ys[5]={0,h/5,h*2/5,h*4/5,h},rs[5]={r,r*6/5,r*11/10,r*4/5,r/4};
    for(int level=0;level<4;++level)for(int s=0;s<16;++s){
        VxpeVec3D a=ring16(x+RING_OX[level],ys[level],z,rs[level],s),b=ring16(x+RING_OX[level],ys[level],z,rs[level],s+1),d=ring16(x+RING_OX[level+1],ys[level+1],z,rs[level+1],s+1),e=ring16(x+RING_OX[level+1],ys[level+1],z,rs[level+1],s);const VxpeToonMaterial3D& m=((s+level)&5)==0?shade:(((s+level)&1)?glass:white);const uint8_t sl[4]={sun_light(s),sun_light(s+1),sun_light(s+1),sun_light(s)};quadG(t,c,m,a,b,d,e,sl);
        if((s&1)==0){/* The stripe corners take the shell's own ring parameters interpolated to
             * their heights, so the decal lies on the surface instead of being a
             * slightly counter-sheared copy of it. */
            int dy=ys[level+1]-ys[level],dr=rs[level+1]-rs[level],dx=RING_OX[level+1]-RING_OX[level];
            int yb=ys[level]+dy/7,yt=ys[level]+dy*6/7,rb=rs[level]+dr/7,rt=rs[level]+dr*6/7,xb=x+RING_OX[level]+dx/7,xt=x+RING_OX[level]+dx*6/7;
            VxpeVec3D ga=ring16(xb,yb,z,rb,s),gb=ring16(xb,yb,z,rb,s+1),gd=ring16(xt,yt,z,rt,s+1),ge=ring16(xt,yt,z,rt,s);const uint8_t bl[4]={sun_light(s),sun_light(s+1),sun_light(s+1),sun_light(s)};quadG(t,c,band,ga,gb,gd,ge,bl);}
    }
    for(int level=1;level<4;++level)for(int s=0;s<16;++s){
        VxpeVec3D a=ring16(x+RING_OX[level],ys[level],z,rs[level]+3,s),b=ring16(x+RING_OX[level],ys[level],z,rs[level]+3,s+1),d=ring16(x+RING_OX[level],ys[level]+4,z,rs[level]+3,s+1),e=ring16(x+RING_OX[level],ys[level]+4,z,rs[level]+3,s);const uint8_t cl[4]={sun_light(s),sun_light(s+1),sun_light(s+1),sun_light(s)};quadG(t,c,white,a,b,d,e,cl);}
}
static void island(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,int x,int z,int radius,int height,const VxpeToonMaterial3D& green,const VxpeToonMaterial3D& light,const VxpeToonMaterial3D& rock){
    for(int i=0;i<8;++i){VxpeVec3D a=ring(x,2,z,radius,i),b=ring(x,2,z,radius,i+1),p=point(x+((i&1)?-radius/5:radius/6),height,z+((i&2)?radius/7:-radius/7));uint8_t sl=sun_light(i);tri(t,c,rock,a,b,point(x,0,z),(uint8_t)(sl*190/255));tri(t,c,((i&1)?green:light),a,b,p,sl);}
}
/* Surf line: a flat annulus one unit above the lagoon. It shares the water plane's
 * footprint, so it relies on the material depth bias instead of a taller offset
 * that would leave a visible lip. */
static void shore(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,int x,int z,int radius,const VxpeToonMaterial3D& foam){
    for(int i=0;i<8;++i){VxpeVec3D a=ring(x,1,z,radius-4,i),b=ring(x,1,z,radius-4,i+1),d=ring(x,1,z,radius+8,i+1),e=ring(x,1,z,radius+8,i);quad(t,c,foam,a,b,d,e,(uint8_t)(196+(i&1)*24));}
}
static void palm(VxpeToonTarget3D& t,const VxpeToonCamera3D& c,int x,int z,int h,const VxpeToonMaterial3D& wood,const VxpeToonMaterial3D& leaves){
    for(int y=0;y<h;y+=h/4){int r=5-y*2/h;quad(t,c,wood,point(x-r,y,z-r),point(x+r,y,z-r),point(x+r,y+h/4+2,z+r),point(x-r,y+h/4+2,z+r),187);}
    VxpeVec3D top=point(x,h,z);for(int i=0;i<8;i++){int k=i*4;VxpeVec3D tip=point(x+(int32_t)COS_Q14[k]*45/16384,h-11+(i%3)*3,z+(int32_t)SIN_Q14[k]*45/16384);VxpeVec3D shoulder=point(x+(int32_t)COS_Q14[k]*22/16384,h+12,z+(int32_t)SIN_Q14[k]*22/16384);tri(t,c,leaves,top,shoulder,tip,sun_light(i*2));}
}
}

PromisedFuture::PromisedFuture():mode(0),tick(0),worldX(0),worldZ(24),yaw(0),scanBits(0),scanFlash(0),nearest(-1),walked(0),exiting(false){}
void PromisedFuture::restore(uint8_t saved){scanBits=saved&15;}
uint8_t PromisedFuture::progress()const{return (uint8_t)(scanBits&15);}
void PromisedFuture::scan(){if(nearest<0)return;int dx=worldX-SCAN_X[nearest],dz=worldZ-SCAN_Z[nearest];if(dx*dx+dz*dz>86*86)return;scanBits|=1<<nearest;scanFlash=100;}
void PromisedFuture::input(int key){if(key<0){if(mode==0)exiting=true;else if(mode==1)mode=2;else mode=0;return;}if(mode==0){if(key==5){mode=1;return;}if(key==9)exiting=true;return;}if(mode==2){if(key==9||key==5)mode=1;else if(key==0)mode=0;return;}if(mode==3){if(key==0||key==5||key==9)mode=1;return;}if(mode!=1)return;if(key==9){mode=2;return;}if(key==0){mode=3;return;}if(key==4)yaw=(yaw+31)&31;if(key==6)yaw=(yaw+1)&31;if(key==5)scan();if(key==2||key==8){int d=key==2?5:-4;int nx=worldX+SIN_Q14[yaw]*d/16384,nz=worldZ+COS_Q14[yaw]*d/16384;if(nx< -125)nx=-125;if(nx>125)nx=125;if(nz<8)nz=8;if(nz>1050)nz=1050;walked+=((nx-worldX<0?worldX-nx:nx-worldX)+(nz-worldZ<0?worldZ-nz:nz-worldZ));worldX=nx;worldZ=nz;}}
void PromisedFuture::touch(int x,int y){if(mode==0){input(5);return;}if(mode==2||mode==3){input(5);return;}if(y<34){input(9);return;}if(y>250){if(x<80)input(4);else if(x>160)input(6);else input(2);return;}if(x>90&&x<150&&y>105&&y<220)input(5);}
void PromisedFuture::update(){if(mode!=1)return;++tick;if(scanFlash>0)--scanFlash;nearest=-1;int best=90*90;for(int i=0;i<4;++i){int dx=worldX-SCAN_X[i],dz=worldZ-SCAN_Z[i],d=dx*dx+dz*dz;if(d<best){best=d;nearest=i;}}}

void PromisedFuture::renderWorld(){
    VxpeToonTarget3D target={worldPixels,wallDepth,WORLD_W,WORLD_H};
    vxpe2d_gradient_vertical_dithered(worldPixels,WORLD_W,WORLD_H,0,0,WORLD_W,WORLD_H,rgb(5,53,180),rgb(148,223,226));
    /* Warm glow in the sun's corner plus a haze band that lifts the waterline, so
     * the lagoon does not meet the sky on a hard edge. Painted before the depth
     * buffer is cleared, so world geometry occludes both normally. */
    vxpe2d_radial_light_fast(worldPixels,WORLD_W,WORLD_H,24,20,58,rgb(255,244,206),84);
    for(int haze=0;haze<6;++haze)vxpe2d_overlay_rect(worldPixels,WORLD_W,WORLD_H,0,74+haze*2,WORLD_W,2,rgb(198,236,229),(uint8_t)(8+haze*5),VXPE_BLEND_ALPHA);
    vxpe_toon3d_clear_depth(&target);
    VxpeToonCamera3D cam;vxpe_toon3d_camera_init(&cam,WORLD_W,WORLD_H);cam.position=point(worldX,102,worldZ);cam.sin_yaw_q14=SIN_Q14[yaw];cam.cos_yaw_q14=COS_Q14[yaw];cam.center_x=60;cam.horizon_y=82;cam.focal_px=96;cam.near_z=5;cam.far_z=1500;cam.sin_pitch_q14=1050;cam.cos_pitch_q14=16350;
    VxpeToonMaterial3D sea,water,foam,sand,green,leaf,wood,white,glass,shade,cloudmat,stone,band;
    material(sea,rgb(8,113,196),rgb(78,190,219));material(water,rgb(15,165,212),rgb(116,219,225));material(foam,rgb(141,225,218),rgb(195,238,224));material(sand,rgb(207,202,154),rgb(204,226,208));material(green,rgb(36,131,82),rgb(118,195,137));material(leaf,rgb(70,177,98),rgb(164,218,146));material(wood,rgb(131,103,66),rgb(184,190,147));material(white,rgb(232,240,222),rgb(222,239,221));material(glass,rgb(56,190,218),rgb(152,225,227));material(shade,rgb(151,207,209),rgb(193,227,222));material(cloudmat,rgb(246,249,232),rgb(229,241,222));material(stone,rgb(114,153,126),rgb(170,208,182));
    material(band,rgb(56,190,218),rgb(152,225,227));band.depth_bias=-3;
    foam.depth_bias=-4;
    // One continuous ocean plane; larger colored sheets create broad reflective bands without a tile pattern.
    quad(target,cam,sea,point(-1800,0,0),point(1800,0,0),point(1800,0,1550),point(-1800,0,1550),220);
    /* Glints swell and drift on a triangle wave of the frame counter: no wrap pop,
     * no allocation, and the phase differs per sheet so the lagoon is never still. */
    for(int i=0;i<20;++i){int swell=(tick+i*11)%24;if(swell>12)swell=24-swell;int z=70+i*68+swell-6;int x=((i*173)%720)-360;int w=60+(i%4)*28;quad(target,cam,(i%3)?water:foam,point(x-w,2,z),point(x+w,2,z),point(x+w-10,2,z+26),point(x-w+10,2,z+26),(uint8_t)(176+swell*3+(i%3)*8));}
    // A broad sculpted promenade leads through the islands into the city.
    // Curved green islands and pale bridges break up the lagoon; broad water remains in view.
    for(int i=0;i<8;++i){int z=120+i*155;int side=(i&1)?1:-1;int x=side*(150+(i%3)*45);int r=90+(i%3)*15;shore(target,cam,x,z,r,foam);island(target,cam,x,z,r,30+(i%3)*10,(i&1)?green:leaf,leaf,stone);palm(target,cam,x+side*16,z-10,75+(i%3)*12,wood,leaf);}
    // Sail-shaped arcologies cluster around the lagoon, with wide cyan glass faces and planted roofs.
    shore(target,cam,-170,430,115,foam);island(target,cam,-170,430,115,34,green,leaf,stone);shore(target,cam,160,490,112,foam);island(target,cam,160,490,112,32,green,leaf,stone);shore(target,cam,0,710,158,foam);island(target,cam,0,710,158,42,green,leaf,stone);
    tower(target,cam,-175,385,235,61,white,glass,shade,band);tower(target,cam,170,445,218,58,white,glass,shade,band);
    tower(target,cam,-270,650,270,68,white,glass,shade,band);tower(target,cam,265,725,248,64,white,glass,shade,band);
    tower(target,cam,0,930,305,76,white,glass,shade,band);
    // Low-poly cloud puffs are placed in world space and depth-tested against the towers.
    for(int i=0;i<8;++i){int x=(i%2?1:-1)*(225+(i%3)*88);int z=330+i*145;int y=168+(i%3)*14;VxpeVec3D top=point(x,y+30,z),bottom=point(x,y-20,z);VxpeVec3D a=point(x-43,y,z),b=point(x,y,z+36),d=point(x+43,y,z),e=point(x,y,z-36);tri(target,cam,cloudmat,top,a,b);tri(target,cam,cloudmat,top,b,d);tri(target,cam,cloudmat,top,d,e);tri(target,cam,cloudmat,top,e,a);tri(target,cam,shade,bottom,b,a);tri(target,cam,shade,bottom,d,b);tri(target,cam,shade,bottom,e,d);tri(target,cam,shade,bottom,a,e);}
    // Monument and beacon markers give the stroll a focal point and preserve the scan mechanic.
    for(int i=0;i<4;++i){int z=SCAN_Z[i];if(z>worldZ-120&&z<worldZ+620&&!(scanBits&(1<<i))){int x=SCAN_X[i];quad(target,cam,white,point(x-7,7,z),point(x+7,7,z),point(x+7,42,z),point(x-7,42,z),245);quad(target,cam,glass,point(x-4,44,z),point(x+4,44,z),point(x+4,52,z),point(x-4,52,z),255);}}
}

void PromisedFuture::draw(uint16_t* fb){if(!fb)return;renderWorld();vxpe2d_scale2x565(fb,240,320,worldPixels,WORLD_W,WORLD_H);
 rect(fb,0,0,240,34,0x18D9);rect(fb,0,0,3,34,0x5F5A);text(fb,10,7,"PROMISED FUTURE",IVORY);text(fb,11,21,"AERO GARDEN",GLASS);char b[24];int got=0;for(int i=0;i<4;++i)got+=(scanBits>>i)&1;snprintf(b,sizeof(b),"%d/4",got);text(fb,196,12,b,GOLD,2);
 if(nearest>=0&&mode==1){int dx=worldX-SCAN_X[nearest],dz=worldZ-SCAN_Z[nearest];if(dx*dx+dz*dz<110*110){rect(fb,53,261,134,22,0x18D9);rect(fb,53,261,134,2,GOLD);center(fb,269,(scanBits&(1<<nearest))?"5 REVISIT BEACON":"5 SCAN BEACON",IVORY);}}
 rect(fb,0,289,240,31,0x18D9);rect(fb,0,289,240,1,0x7BDE);text(fb,9,296,"4 6 TURN   2 8 WALK   5 SCAN",IVORY);text(fb,53,309,"0 JOURNAL    9 PAUSE",GLASS);
 if(scanFlash>0&&nearest>=0&&(scanBits&(1<<nearest))){rect(fb,31,43,178,29,0x18D9);rect(fb,31,43,178,2,MINT);center(fb,50,"ECO MEMORY FOUND",GOLD);}
 if(mode==0){rect(fb,18,81,204,157,0x18D9);rect(fb,20,83,200,153,0x221D);rect(fb,20,83,200,2,0x5F5A);center(fb,103,"THE",IVORY,3);center(fb,132,"FUTURE",GOLD,3);center(fb,166,"A CITY IN BLOOM",GLASS);center(fb,184,"EXPLORE THE ISLAND",IVORY);rect(fb,53,204,134,23,0x36B5);rect(fb,53,204,134,2,GOLD);center(fb,212,"5 ENTER CITY",IVORY);}
 if(mode==2){vxpe2d_overlay_rect(fb,240,320,0,0,240,320,0x0000,150,VXPE_BLEND_ALPHA);rect(fb,32,123,176,72,NAVY);rect(fb,32,123,176,2,GOLD);center(fb,139,"PAUSED",IVORY,2);center(fb,169,"9 CONTINUE  0 EXIT",GLASS);}
 if(mode==3){vxpe2d_overlay_rect(fb,240,320,0,0,240,320,0x0000,155,VXPE_BLEND_ALPHA);rect(fb,16,61,208,207,NAVY);rect(fb,16,61,208,2,MINT);center(fb,73,"ECO JOURNAL",GOLD,2);for(int i=0;i<4;++i){text(fb,28,103+i*31,(scanBits&(1<<i))?MEMORY_NAME[i]:"BEACON LOCKED",IVORY);if(scanBits&(1<<i))text(fb,34,115+i*31,MEMORY_LINE[i],GLASS);else text(fb,34,115+i*31,"WALK CLOSER TO SCAN",0x7B98);}center(fb,244,"5 OR 0 RETURN",IVORY);}
}
