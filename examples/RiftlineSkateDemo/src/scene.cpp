#include "scene.h"
#include "actor.h"
#include "graphics/VxpToon3D.h"
#include "graphics/VxpRender2D.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

namespace {
static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static void text(uint16_t* fb,int x,int y,const char* s,uint16_t color,int scale=1){
    // Compact 5x7 uppercase numerals/letters, no runtime font allocation.
    static const uint8_t glyphs[36][7]={
      {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},{30,1,1,14,1,1,30},
      {2,6,10,18,31,2,2},{31,16,16,30,1,1,30},{6,8,16,30,17,17,14},{31,1,2,4,8,8,8},
      {14,17,17,14,17,17,14},{14,17,17,15,1,2,12},{14,17,17,31,17,17,17},{30,17,17,30,17,17,30},
      {14,17,16,16,16,17,14},{30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
      {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},{7,2,2,2,18,18,12},
      {17,18,20,24,20,18,17},{16,16,16,16,16,16,31},{17,27,21,21,17,17,17},{17,25,21,19,17,17,17},
      {14,17,17,17,17,17,14},{30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
      {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},{17,17,17,17,17,10,4},
      {17,17,17,21,21,21,10},{17,17,10,4,10,17,17},{17,17,10,4,4,4,4},{31,1,2,4,8,16,31}};
    for(;*s;++s,x+=6*scale){int i=*s>='A'&&*s<='Z'?10+*s-'A':*s>='0'&&*s<='9'?*s-'0':-1;if(i<0)continue;
      for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(glyphs[i][yy]&(1<<(4-xx)))vxpe2d_fill_rect(fb,240,320,x+xx*scale,y+yy*scale,scale,scale,color);}
}
static void quad(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,VxpeVec3D e,uint16_t color,int light=255){
    VxpeVec3D v[4]={a,b,d,e};VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,color);m.outline_px=0;
    m.fog565=rgb(17,29,40);m.fog_near_z=500;m.fog_far_z=1900;m.fog_alpha=130;m.shadow_q8=145;m.midtone_q8=220;
    vxpe_toon3d_quad(t,c,v,&m,(uint8_t)light);
}
static void box(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int x,int y,int z,int w,int h,int l,uint16_t color){
    int X=x+w,Y=y+h,Z=z+l;
    quad(t,c,{x,y,z},{X,y,z},{X,Y,z},{x,Y,z},color,220);
    quad(t,c,{x,y,Z},{x,y,z},{x,Y,z},{x,Y,Z},color,150);
    quad(t,c,{X,y,z},{X,y,Z},{X,Y,Z},{X,Y,z},color,100);
    quad(t,c,{x,Y,z},{X,Y,z},{X,Y,Z},{x,Y,Z},color,255);
}
static int rampY(int x){int a=x<0?-x:x;if(a<=72)return 0;if(a>=174)return 112;int d=a-72;return d*d*112/(102*102);}
static int runRampY(int z){int section=(z/1400)*1400,local=z-(section+500);if(local<0||local>190)return 0;
    if(local<=142)return local*local*90/(142*142);if(local<=166)return 90;return (190-local)*90/24;}
static void quarterpipe(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int pz){
    int section=(pz/1400)*1400,z0=section+500;const int width=260;
    // A banked quarter pipe, built as small lit facets with a hard coping lip.
    for(int step=0;step<10;++step){int a=step*19,b=(step+1)*19,y0=runRampY(z0+a),y1=runRampY(z0+b);
        uint16_t paint=step%3==0?rgb(132,148,148):rgb(111+(step%2)*4,128+(step%2)*3,132+(step%2)*3);
        quad(t,c,{-width/2,y0,z0+a},{width/2,y0,z0+a},{width/2,y1,z0+b},{-width/2,y1,z0+b},paint,step<7?222:250);
        // Edge cheeks reveal the ramp thickness and give it a readable silhouette.
        quad(t,c,{-width/2-8,0,z0+a},{-width/2,y0,z0+a},{-width/2,y1,z0+b},{-width/2-8,0,z0+b},rgb(66,82,89),145);
        quad(t,c,{width/2,0,z0+a},{width/2+8,0,z0+b},{width/2,y1,z0+b},{width/2,y0,z0+a},rgb(55,73,82),112);
    }
    box(t,c,-width/2,87,z0+160,width,8,8,rgb(37,155,150));
    box(t,c,-width/2,95,z0+160,width,3,5,rgb(208,203,166));
    // Painted landing marks on the upper deck.
    for(int stripe=-2;stripe<=2;++stripe){int x=stripe*34;box(t,c,x-2,91,z0+178,4,1,23,stripe==0?rgb(222,157,87):rgb(169,182,169));}
}
static void groundShadow(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int x,int y,int z){
    for(int layer=0;layer<2;++layer){VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,layer?rgb(49,61,64):rgb(38,49,55));m.outline_px=0;m.fog_alpha=0;
      VxpeVec3D center={x,y+2+layer,z};int rx=layer?23:35,rz=layer?31:48;
      for(int i=0;i<8;++i){float a=i*0.78539816f,b=(i+1)*0.78539816f;
        VxpeVec3D p={x+(int)(cosf(a)*rx),y+2+layer,z+(int)(sinf(a)*rz)};
        VxpeVec3D q={x+(int)(cosf(b)*rx),y+2+layer,z+(int)(sinf(b)*rz)};
        vxpe_toon3d_triangle(t,c,center,p,q,&m,layer?120:150,0);}}
}
static void skatepark(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int pz,int tick){
    const uint16_t concrete=rgb(105,123,127),light=rgb(151,167,166),dark=rgb(66,82,88),teal=rgb(34,118,124);
    int seg=(pz/340)*340;
    // Long U-bowl: curved quarter pipes are triangulated from a deterministic cross section.
    for(int band=-3;band<13;++band){int z=seg+band*170;
      for(int i=0;i<20;++i){int x0=-174+i*17,x1=x0+17;int y0=rampY(x0),y1=rampY(x1);
        int variation=((i*7+band*11)%11)-5;
        uint16_t c0=(i/2+band)%7==0?light:rgb(105+variation,123+variation,127+variation);
        quad(t,c,{x0,y0,z},{x1,y1,z},{x1,y1,z+172},{x0,y0,z+172},c0,(uint8_t)(180+(i%4)*18));
        // Slim expansion joints bend with the bowl, reinforcing the curved form.
        if(i%3==0)quad(t,c,{x0,y0+1,z+2},{x0+1,y0+1,z+2},{x1,y1+1,z+2},{x1-1,y1+1,z+2},dark,188);
      }
      // Coping and safety stripe follow the lips on either side of each bowl.
      box(t,c,-181,107,z,10,8,172,teal);box(t,c,171,107,z,10,8,172,teal);
      box(t,c,-178,113,z,8,2,172,light);box(t,c,170,113,z,8,2,172,light);
      // Subtle expansion seams across the floor help communicate speed and scale.
      for(int stripe=-2;stripe<=2;++stripe)quad(t,c,{-65,2,z+stripe*26},{65,2,z+stripe*26},{65,2,z+stripe*26+2},{-65,2,z+stripe*26+2},dark,220);
      for(int dash=0;dash<3;++dash){int dz=z+34+dash*48;quad(t,c,{-8,3,dz},{8,3,dz},{8,3,dz+17},{-8,3,dz+17},rgb(178,185,165),230);}
    }
    // Raised plaza blocks and a small roll-in ramp visible beyond the near bowl.
    for(int lane=-1;lane<=1;++lane){int x=lane*116;box(t,c,x-34,0,seg+1000,68,30,118,dark);box(t,c,x-36,30,seg+1000,72,4,118,light);}
    for(int n=0;n<6;++n){int z=seg+1260+n*30;int y=(n+1)*5;box(t,c,75,y,z,76,5,25,n%2?concrete:light);}
    quarterpipe(t,c,pz);
    // Two rails with posts; the left one is the grind line used by the trick system.
    for(int rail=0;rail<2;++rail){int x=rail?-108:108;int z=seg+310+rail*360;
      for(int post=0;post<6;++post)box(t,c,x-2,0,z+post*34,4,38,4,dark);
      box(t,c,x-3,38,z,6,4,190,rgb(196,203,185));
      box(t,c,x-4,42,z,8,2,190,teal);
    }
    // Distant original park silhouette and cool evening sky.
    for(int i=0;i<7;++i){int x=-530+i*175;box(t,c,x,0,seg+1630,105,115+(i%3)*38,82,rgb(39,56,69));
      box(t,c,x-3,115+(i%3)*38,seg+1630,111,5,82,rgb(65,84,91));}
    // Tall floodlight masts and polygon lamps create a layered night-sports backdrop.
    int lights=(pz/620)*620;
    for(int i=-1;i<4;++i){int z=lights+i*620;int x=(i&1)?205:-205;
        box(t,c,x-3,0,z,6,240,6,rgb(43,60,70));box(t,c,x-15,235,z-15,30,8,30,rgb(77,102,106));
        box(t,c,x-11,229,z-11,22,5,22,rgb(241,206,137));}
    (void)tick;
}
static void board(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int x,int y,int z,int trick,int tick){
    float angle=trick==1?sinf(tick*.68f)*1.15f:trick==2?sinf(tick*.82f+1.2f)*.92f:0.f;
    float cs=cosf(angle),sn=sinf(angle);
    auto deck=[&](int dx,int dy,int dz)->VxpeVec3D{return {x+dx,y+6+(int)(dy*cs+dx*sn),z+dz};};
    quad(t,c,deck(-20,-2,-38),deck(20,-2,-38),deck(17,-2,38),deck(-17,-2,38),rgb(230,122,63));
    quad(t,c,deck(-18,2,-36),deck(18,2,-36),deck(15,2,36),deck(-15,2,36),rgb(37,48,55));
    for(int w=-1;w<=1;w+=2)box(t,c,x-20,0,z+w*21,40,5,4,rgb(34,39,44));
}
static void finish(uint16_t* p){static const uint8_t b[4]={0,2,3,1};for(int y=0;y<320;++y)for(int x=0;x<240;++x){int i=y*240+x,g=(p[i]>>5)&63;if((g&1)&&b[(y&1)*2+(x&1)]<2&&g<62)++g;p[i]=(uint16_t)((p[i]&0xf81f)|((g&62)<<5));}}
}

RiftlineScene::RiftlineScene():tick(0),px(0),pz(0),speed(5),jump(0),grind(0),cameraMode(0),points(0),lean(0),trick(0),combo(1),comboTicks(0),bestCombo(1),paused(false),exiting(false),started(false),crashed(false){}
void RiftlineScene::input(int key){
    if(key<0){exiting=true;return;}
    if(key==9){if(started)paused=!paused;return;}if(paused)return;
    if(!started){if(key==5||key==2||key==8)started=true;return;}
    if(key==4){lean=-12;px-=9;if(px<-145)px=-145;}
    if(key==6){lean=12;px+=9;if(px>145)px=145;}
    if(key==2&&speed<10)++speed;if(key==8&&speed>2)--speed;
    if(key==5&&!jump){jump=38;trick=0;combo=1;comboTicks=0;grind=0;}
    if((key==1||key==3)&&jump){trick=key==1?1:2;++combo;if(combo>bestCombo)bestCombo=combo;comboTicks=64;points+=key==1?125:180;}
    if(key==7){grind=!grind;if(grind){jump=0;px=px<0?-108:108;++combo;if(combo>bestCombo)bestCombo=combo;comboTicks=64;points+=220;}}
    if(key==0)cameraMode=(cameraMode+1)%3;
}
void RiftlineScene::update(){if(paused||!started)return;++tick;pz+=speed;if(pz>120000)pz=0;if(jump)--jump;
    if(lean>0)--lean;else if(lean<0)++lean;
    if(grind&&tick%5==0){points+=35*combo;comboTicks=48;}
    if(comboTicks>0)--comboTicks;else if(!jump&&!grind)combo=1;
    if(!jump&&!grind&&((px>136)||(px<-136))){crashed=true;if(tick%24==0){speed=2;crashed=false;}}
}
void RiftlineScene::draw(uint16_t* fb){
    VxpeToonTarget3D target={worldPixels,depth,RENDER_WIDTH,RENDER_HEIGHT};vxpe_toon3d_clear(&target,rgb(12,20,31));
    vxpe2d_gradient_vertical(worldPixels,RENDER_WIDTH,RENDER_HEIGHT,0,0,RENDER_WIDTH,110,rgb(14,25,42),rgb(71,102,119));
    int groundLevel=started?rampY(px)+runRampY(pz):0;
    VxpeToonCamera3D camera;vxpe_toon3d_camera_init(&camera,RENDER_WIDTH,RENDER_HEIGHT);
    camera.position={px-72,178+groundLevel,pz-250};camera.focal_px=112;camera.horizon_y=76;camera.sin_yaw_q14=0;camera.cos_yaw_q14=16384;camera.sin_pitch_q14=6200;camera.cos_pitch_q14=15164;camera.far_z=2300;
    if(cameraMode){float a=cameraMode==1?.16f:-.24f;camera.sin_yaw_q14=(int16_t)(sinf(a)*16384);camera.cos_yaw_q14=(int16_t)(cosf(a)*16384);camera.position.x+=cameraMode==1?-45:70;}
    float yaw=atan2f((float)(px-camera.position.x),250.f);camera.sin_yaw_q14=(int16_t)(sinf(yaw)*16384);camera.cos_yaw_q14=(int16_t)(cosf(yaw)*16384);
    skatepark(&target,&camera,pz,tick);
    if(started){
      int ground=rampY(px)+runRampY(pz),h=jump?(int)(sinf((38-jump)*3.14159265f/38)*74):0;
      groundShadow(&target,&camera,px,ground,pz);
      board(&target,&camera,px,ground+h+(grind?39:0),pz,trick,tick);
      if(jump&&trick){for(int i=0;i<6;++i){float a=i*1.04719755f+tick*.12f;int sx=px+(int)(cosf(a)*29),sy=h+52+(int)(sinf(a)*13),sz=pz+(int)(sinf(a)*18);
        uint16_t color=trick==1?(i&1?rgb(255,197,91):rgb(255,237,178)):(i&1?rgb(99,226,207):rgb(194,255,232));
        quad(&target,&camera,{sx-2,sy-2,sz},{sx+2,sy-2,sz},{sx+2,sy+2,sz},{sx-2,sy+2,sz},color);}}
      UrbanActorPose pose={speed?tick:0,jump,grind,lean,(int16_t)(sinf(lean*.025f)*16384),(int16_t)(cosf(lean*.025f)*16384)};
      VxpeVec3D pos={px,ground+h+(grind?36:0),pz};urban_actor_draw(&target,&camera,pos,&pose,true,false);
    }
    vxpe2d_upscale2x565(fb,WIDTH,HEIGHT,worldPixels,RENDER_WIDTH,RENDER_HEIGHT);
    // Render the skater at display resolution by reusing the consumed world
    // color/depth memory as an 80x120 tile; the park framebuffer stays 120x160.
    if(started){
      int ground=rampY(px)+runRampY(pz),h=jump?(int)(sinf((38-jump)*3.14159265f/38)*74):0;
      UrbanActorPose pose={speed?tick:0,jump,grind,lean,(int16_t)(sinf(lean*.025f)*16384),(int16_t)(cosf(lean*.025f)*16384)};
      VxpeVec3D pos={px,ground+h+(grind?36:0),pz};enum { AW=80,AH=120,AP=AW*AH};
      static_assert(AP*2<=RENDER_WIDTH*RENDER_HEIGHT,"actor tile exceeds reusable scene buffers");
      VxpeToonCamera3D detailCamera=camera;detailCamera.center_x*=2;detailCamera.horizon_y*=2;detailCamera.focal_px*=2;
      VxpeToonPoint3D anchor;
      if(vxpe_toon3d_project(&detailCamera,pos,&anchor)){
        int ox=anchor.x-AW/2,oy=anchor.y-(AH-10);detailCamera.center_x-=ox;detailCamera.horizon_y-=oy;
        VxpeToonTarget3D detail={worldPixels,worldPixels+AP,AW,AH};vxpe_toon3d_clear(&detail,0);
        urban_actor_draw(&detail,&detailCamera,pos,&pose,false,true);
        for(int y=0;y<AH;++y){int dy=oy+y;if(dy<0||dy>=HEIGHT)continue;for(int x=0;x<AW;++x){int dx=ox+x;if(dx<0||dx>=WIDTH)continue;
          uint16_t d=detail.depth[y*AW+x];if(d!=65535&&d<=depth[(dy/2)*RENDER_WIDTH+dx/2])fb[dy*WIDTH+dx]=detail.pixels[y*AW+x];}}
      }
    }
    finish(fb);
    // Premium compact HUD: matte panels, acid-lime accents and a live score/combo.
    vxpe2d_fill_rect(fb,240,320,7,7,226,30,rgb(12,20,29));vxpe2d_fill_rect(fb,240,320,7,7,3,30,rgb(108,221,171));
    text(fb,16,11,"RIFTLINE",rgb(229,236,219),2);
    char number[24];sprintf(number,"%06d",points);text(fb,17,48,number,rgb(13,24,28),2);text(fb,16,47,number,rgb(199,238,121),2);
    sprintf(number,"SPD %02d",speed);text(fb,169,13,number,rgb(218,226,224));
    if(comboTicks>0){sprintf(number,"COMBO X%d",combo);text(fb,70,78,number,rgb(255,197,91),2);
      if(trick==1)text(fb,88,98,"KICKFLIP",rgb(229,237,214));else if(trick==2)text(fb,88,98,"SHUVIT",rgb(133,237,213));else if(grind)text(fb,91,98,"RAIL LINE",rgb(133,237,213));}
    if(grind){text(fb,14,105,"RAIL GRIND",rgb(116,231,203),2);}
    if(!started){
      vxpe2d_fill_rect(fb,240,320,16,111,208,127,rgb(9,18,28));vxpe2d_fill_rect(fb,240,320,18,113,204,2,rgb(102,222,172));
      text(fb,42,128,"CONCRETE",rgb(222,233,217),2);text(fb,48,150,"FLOW",rgb(213,139,80),3);
      text(fb,41,193,"OLLIE  TRICK  GRIND",rgb(189,211,203));
      vxpe2d_fill_rect(fb,240,320,39,229,162,26,rgb(43,82,76));text(fb,79,237,"5 TO DROP IN",rgb(233,242,213));
      text(fb,38,273,"ORIGINAL 240 X 320",rgb(137,173,172));
    }
    vxpe2d_fill_rect(fb,240,320,0,289,240,31,rgb(9,16,24));
    text(fb,9,296,"4 6 RIDE  5 OLLIE  1 3 TRICK",rgb(223,232,219));
    text(fb,9,309,"7 GRIND  0 CAM  9 PAUSE",rgb(159,196,183));
    if(paused){vxpe2d_fill_rect(fb,240,320,44,137,152,44,rgb(9,18,28));text(fb,85,151,"PAUSED",rgb(227,208,131),2);text(fb,72,171,"9 RESUME",rgb(211,224,217));}
}
