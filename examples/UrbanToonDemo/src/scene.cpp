#include "scene.h"
#include "actor.h"
#include "city.h"
#include "skater.h"
#include "font.h"
#include "graphics/VxpToon3D.h"
#include "graphics/VxpArtStyle.h"
#include "graphics/VxpRender2D.h"
#include <math.h>
#include <stdio.h>

static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565((uint8_t)r,(uint8_t)g,(uint8_t)b);}
static void label(uint16_t* fb,int x,int y,const char* s,uint16_t color,int scale=1){
    for(;*s;++s,x+=6*scale){int i=*s>='A'&&*s<='Z'?*s-'A':*s>='0'&&*s<='9'?26+*s-'0':-1;if(i<0)continue;
        for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))vxpe2d_fill_rect(fb,240,320,x+xx*scale,y+yy*scale,scale,scale,color);
    }
}
static void face(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,VxpeVec3D e,uint16_t color,int light,int ink=1,const VxpeSpriteA8* texture=0){
    VxpeVec3D v[4]={a,b,d,e};VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,color);m.outline_px=(uint8_t)ink;m.fog_near_z=700;m.fog_far_z=2200;m.fog_alpha=90;
    if(texture){VxpeToonVertex3D uv[4]={{a,0,(texture->height-1)*256},{b,(texture->width-1)*256,(texture->height-1)*256},{d,(texture->width-1)*256,0},{e,0,0}};if(texture->pixels==CITY_BRICK||texture->pixels==CITY_ROAD){m.texture_wrap=1;for(int i=0;i<4;++i){uv[i].u_q8=v[i].x*128;uv[i].v_q8=v[i].z*128;}}vxpe_toon3d_quad_textured(t,c,uv,texture,&m,(uint8_t)light);}
    else vxpe_toon3d_quad(t,c,v,&m,(uint8_t)light);
}
static void box(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,int x,int z,int w,int length,int h,uint16_t color,int baseY=0,const VxpeSpriteA8* texture=0){
    int right=x+w,back=z+length,top=baseY+h;
    face(t,c,{x,baseY,z},{right,baseY,z},{right,top,z},{x,top,z},color,210,1,texture);
    face(t,c,{x,baseY,back},{x,baseY,z},{x,top,z},{x,top,back},color,145,1,texture);
    face(t,c,{right,baseY,z},{right,baseY,back},{right,top,back},{right,top,z},color,75,1,texture);
    face(t,c,{x,top,z},{right,top,z},{right,top,back},{x,top,back},color,255);
}
UrbanScene::UrbanScene(){tick=0;px=0;pz=0;speed=4;jump=0;grind=0;cameraMode=0;points=0;lean=0;paused=exiting=false;}
void UrbanScene::input(int key){
    if(key==9){paused=!paused;return;}if(key<0){exiting=true;return;}if(paused)return;
    if(key==4){lean=-12;px-=8;if(px<-130)px=-130;}if(key==6){lean=12;px+=8;if(px>130)px=130;}
    if(key==2&&speed<9)++speed;if(key==8&&speed>0)--speed;
    if(key==5&&!jump){jump=36;points+=50;}
    if(key==7){grind=!grind;if(grind){px=-125;points+=100;}}
    if(key==0)cameraMode=(cameraMode+1)%3;
}
void UrbanScene::update(){if(paused)return;++tick;pz+=speed;if(pz>20000)pz-=19200;if(jump)--jump;if(lean>0)--lean;else if(lean<0)++lean;if(grind&&tick%15==0)points+=10;}
void UrbanScene::draw(uint16_t* fb){
    VxpeToonTarget3D target={worldPixels,depth,RENDER_WIDTH,RENDER_HEIGHT};vxpe_toon3d_clear(&target,rgb(32,107,231));
    vxpe2d_gradient_vertical(worldPixels,RENDER_WIDTH,RENDER_HEIGHT,0,0,RENDER_WIDTH,90,rgb(22,84,227),rgb(124,202,241));
    // Clouds stay in the sky pass and need no texture/alpha buffers.
    for(int i=0;i<3;++i){int cx=(17+i*44-tick/24)%150;if(cx<0)cx+=150;cx-=15;int cy=16+i%2*12;
        vxpe2d_fill_rect(worldPixels,RENDER_WIDTH,RENDER_HEIGHT,cx,cy,24,5,rgb(215,234,228));
        vxpe2d_fill_rect(worldPixels,RENDER_WIDTH,RENDER_HEIGHT,cx+6,cy-3,11,4,rgb(242,243,222));}
    VxpeToonCamera3D camera;vxpe_toon3d_camera_init(&camera,RENDER_WIDTH,RENDER_HEIGHT);camera.position={px-110,165,pz-230};camera.focal_px=90;camera.horizon_y=88;camera.sin_yaw_q14=6800;camera.cos_yaw_q14=14907;camera.sin_pitch_q14=5618;camera.cos_pitch_q14=15393;camera.far_z=2600;
    if(cameraMode){float angle=cameraMode==1?.12f:-.30f;camera.sin_yaw_q14=(int16_t)(sinf(angle)*16384);camera.cos_yaw_q14=(int16_t)(cosf(angle)*16384);camera.position.x=px+(cameraMode==1?-35:95);}
    if(camera.position.x < -145)camera.position.x=-145;
    if(camera.position.x > 145)camera.position.x=145;
    float followYaw=atan2f((float)(px-camera.position.x),230.f);
    camera.sin_yaw_q14=(int16_t)(sinf(followYaw)*16384);camera.cos_yaw_q14=(int16_t)(cosf(followYaw)*16384);
    // Distant skyline uses the same depth/fog pass as the street.
    for(int i=0;i<6;++i)box(&target,&camera,-700+i*245,pz+1650+(i%2)*120,130,140,360+(i%3)*120,rgb(97,149,184));
    int segment=pz/320*320;
    const VxpeSpriteA8 brick={CITY_BRICK,0,64,64,64,0,1},road={CITY_ROAD,0,64,64,64,0,1},shop={CITY_SHOP,0,128,128,128,0,1},office={CITY_OFFICE,0,128,128,128,0,1};
    face(&target,&camera,{-180,0,pz-230},{180,0,pz-230},{180,0,pz+2400},{-180,0,pz+2400},0xffff,255,0,&road);
    face(&target,&camera,{-230,2,pz-230},{-160,2,pz-230},{-160,2,pz+2400},{-230,2,pz+2400},0xffff,255,0,&brick);
    face(&target,&camera,{160,2,pz-230},{230,2,pz-230},{230,2,pz+2400},{160,2,pz+2400},0xffff,255,0,&brick);
    const VxpeSpriteA8 facade={CITY_FACADE,0,64,64,64,0,1},graffiti={CITY_GRAFFITI,0,64,64,64,0,1};
    const VxpeSpriteA8 signs[3]={{CITY_SIGN_RADIO,0,64,64,64,0,1},{CITY_SIGN_CAFE,0,64,64,64,0,1},{CITY_SIGN_SKATE,0,64,64,64,0,1}};
    for(int i=0;i<9;++i){int z=segment-320+i*320;

        box(&target,&camera,-370-(i%2)*30,z,155+(i%2)*30,235+(i%3)*15,170+(i%3)*75,0xffff,0,i%2?&shop:&facade);
        box(&target,&camera,215+(i%3)*12,z+45,160,220,190+(i%3)*85,0xffff,0,i%2?&office:&shop);
        box(&target,&camera,-230,z+20,22,185,8,rgb(239,81,42),65);
        box(&target,&camera,200,z+75,30,150,10,rgb(35,167,156),70);
        for(int j=0;j<3;++j){box(&target,&camera,-214,z+30+j*55,3,40,45,rgb(50,91,109),8);box(&target,&camera,202,z+82+j*44,3,32,50,rgb(39,61,72),8);}
        box(&target,&camera,183,z+270,8,8,80,rgb(94,67,38));
        // Faceted crown avoids the old box-shaped trees.
        VxpeToonMaterial3D leaf;vxpe_toon3d_material_init(&leaf,rgb(92,161,52));leaf.outline_px=0;leaf.fog_alpha=70;
        VxpeVec3D ring[4]={{156,92,z+274},{187,92,z+243},{218,92,z+274},{187,92,z+305}};
        for(int k=0;k<4;++k){vxpe_toon3d_triangle(&target,&camera,ring[k],ring[(k+1)%4],{187,130,z+274},&leaf,(uint8_t)(155+k*30),0);
            vxpe_toon3d_triangle(&target,&camera,ring[(k+1)%4],ring[k],{187,66,z+274},&leaf,145,0);}
        // Building shadows retain the road texture and follow one sun direction.
        face(&target,&camera,{154,1,z+155},{58,1,z+201},{75,1,z+270},{154,1,z+215},rgb(143,147,153),255,0,&road);
        // Roof trim, balcony ledges and supports add visible depth to shopfronts.
        box(&target,&camera,209+(i%3)*12,z+45,168,225,5,rgb(187,173,139),190+(i%3)*85);
        if(i<5){box(&target,&camera,203,z+103,18,85,5,rgb(187,194,174),125);
            for(int rail=0;rail<5;++rail)box(&target,&camera,201,z+105+rail*18,3,3,15,rgb(39,56,59),130);
            box(&target,&camera,201,z+103,3,86,3,rgb(66,78,78),143);}
        // Curb, drain and striped awnings add street-scale detail.
        box(&target,&camera,-164,z,4,300,4,rgb(210,204,178));box(&target,&camera,160,z,4,300,4,rgb(210,204,178));
        box(&target,&camera,151,z+210,8,24,1,rgb(41,49,48),1);
        for(int j=0;j<8;++j)box(&target,&camera,198,z+75+j*18,32,9,3,j%2?rgb(243,223,164):rgb(213,73,45),78);
        box(&target,&camera,-204,z+170,20,17,55,rgb(40,107,128));
        face(&target,&camera,{-183,8,z+170},{-183,8,z+187},{-183,48,z+187},{-183,48,z+170},0xffff,255,0,&signs[2]);
        box(&target,&camera,-200,z+45,8,8,118,rgb(45,65,78));
        box(&target,&camera,192,z+200,8,8,120,rgb(45,65,78));
        // Cyan and magenta shop signs extend towards the street.
        box(&target,&camera,-222,z+65,12,32,80,0xffff,90,&signs[i%3]);
        box(&target,&camera,204,z+155,12,32,80,0xffff,100,&signs[(i+1)%3]);
        face(&target,&camera,{-3,1,z+30},{3,1,z+30},{3,1,z+120},{-3,1,z+120},rgb(239,236,217),255,0);
    }
    // Rail and supports. Core depth handles every intersection with the road/actor.
    for(int i=0;i<8;++i){int z=segment+i*150;box(&target,&camera,-131,z,5,5,22,rgb(250,196,33));}
    box(&target,&camera,-133,segment-150,9,1400,6,rgb(255,212,39),22);
    int busZ=segment+470;
    box(&target,&camera,45,busZ,92,210,76,rgb(230,233,212));
    box(&target,&camera,46,busZ+8,90,150,35,rgb(57,90,112),40);
    face(&target,&camera,{51,40,busZ-2},{129,40,busZ-2},{129,70,busZ-2},{51,70,busZ-2},rgb(65,109,137),190);
    face(&target,&camera,{49,14,busZ-3},{132,14,busZ-3},{132,24,busZ-3},{49,24,busZ-3},rgb(18,198,189),255);
    face(&target,&camera,{44,8,busZ+12},{44,8,busZ+200},{44,50,busZ+200},{44,50,busZ+12},0xffff,255,1,&graffiti);
    box(&target,&camera,42,busZ+20,9,35,24,rgb(22,31,35));box(&target,&camera,134,busZ+145,9,35,24,rgb(22,31,35));
    // Pedestrian bridge, stairs and yellow guard rails, in world space.
    int bridgeZ=segment+380;
    box(&target,&camera,-215,bridgeZ,430,58,10,rgb(205,184,127),133);
    for(int side=-1;side<=1;side+=2){box(&target,&camera,side*195,bridgeZ+15,12,12,133,rgb(177,176,157));
        for(int step=0;step<12;++step)box(&target,&camera,side<0?-230:172,bridgeZ-220+step*18,60,18,11+step*11,rgb(165,169,158));}
    for(int j=0;j<12;++j){box(&target,&camera,-210+j*37,bridgeZ,3,3,31,rgb(242,190,29),143);box(&target,&camera,-210+j*37,bridgeZ+55,3,3,31,rgb(242,190,29),143);}
    box(&target,&camera,-215,bridgeZ,430,3,4,rgb(255,213,42),172);
    box(&target,&camera,-215,bridgeZ+55,430,3,4,rgb(255,213,42),172);
    // Small parked cars with dark wheels, windscreens and bright bodywork.
    for(int i=0;i<3;++i){int z=segment+130+i*360,x=i%2?-154:105;
        box(&target,&camera,x,z,47,86,23,i%2?rgb(226,210,145):rgb(217,73,43),8);
        box(&target,&camera,x+4,z+24,39,40,18,rgb(55,95,116),31);
        box(&target,&camera,x-3,z+10,7,18,16,rgb(25,29,30));box(&target,&camera,x+44,z+57,7,18,16,rgb(25,29,30));}
    // Zebra crossing and lane paint are depth-tested road geometry.
    for(int stripe=0;stripe<8;++stripe)face(&target,&camera,{-142+stripe*38,1,segment+240},{-123+stripe*38,1,segment+240},{-123+stripe*38,1,segment+296},{-142+stripe*38,1,segment+296},rgb(232,224,198),255,0);
    int height=jump?(int)(sinf((36-jump)*3.14159265f/36)*65):0;
    float bodyYaw=lean*.025f;
    UrbanActorPose pose={speed?tick:0,jump,grind,lean,(int16_t)(sinf(bodyYaw)*16384),(int16_t)(cosf(bodyYaw)*16384)};
    // Deterministic grind sparks and speed ribbons are depth-tested world geometry.
    if(grind){for(int i=0;i<9;++i){int age=(tick+i*5)%24,sx=px+(i%3-1)*age/3,sy=30+age/2-age*age/60,sz=pz-8-age*3;
        face(&target,&camera,{sx-2,sy,sz},{sx+2,sy,sz},{sx+1,sy+3,sz+2},{sx-1,sy+3,sz+2},i%2?rgb(255,226,78):rgb(255,126,32),255,0);}}
    else if(speed>4&&!jump){for(int i=0;i<2;++i){int sx=px+(i?11:-11);face(&target,&camera,{sx-2,3,pz-65-speed*3},{sx+2,3,pz-65-speed*3},{sx+3,3,pz-6},{sx-3,3,pz-6},rgb(73,212,220),255,0);}}

        VxpeVec3D actorPosition={px,height+(grind?29:0),pz};
    urban_actor_draw(&target,&camera,actorPosition,&pose,true,false);
    vxpe2d_scale2x565(fb,WIDTH,HEIGHT,worldPixels,RENDER_WIDTH,RENDER_HEIGHT);
    // Reuse the consumed 120x160 colour buffer as an 80x120 colour+depth tile.
    // Original scene depth remains available for occlusion at each display pixel.
    enum { ACTOR_W=80,ACTOR_H=120,ACTOR_PIXELS=ACTOR_W*ACTOR_H };
    static_assert(ACTOR_PIXELS*2<=RENDER_WIDTH*RENDER_HEIGHT,"actor tile exceeds reusable buffer");
    VxpeToonCamera3D detailCamera=camera;
    detailCamera.center_x*=2;detailCamera.horizon_y*=2;detailCamera.focal_px*=2;
    VxpeToonPoint3D anchor;
    if(vxpe_toon3d_project(&detailCamera,actorPosition,&anchor)){
        int originX=anchor.x-ACTOR_W/2,originY=anchor.y-(ACTOR_H-10);
        detailCamera.center_x-=originX;detailCamera.horizon_y-=originY;
        VxpeToonTarget3D detail={worldPixels,worldPixels+ACTOR_PIXELS,ACTOR_W,ACTOR_H};
        vxpe_toon3d_clear(&detail,0);urban_actor_draw(&detail,&detailCamera,actorPosition,&pose,false);
        for(int y=0;y<ACTOR_H;++y){int displayY=originY+y;if(displayY<0||displayY>=HEIGHT)continue;
            for(int x=0;x<ACTOR_W;++x){int displayX=originX+x;if(displayX<0||displayX>=WIDTH)continue;
                uint16_t actorDepth=detail.depth[y*ACTOR_W+x];
                if(actorDepth!=65535&&actorDepth<=depth[(displayY/2)*RENDER_WIDTH+displayX/2])fb[displayY*WIDTH+displayX]=detail.pixels[y*ACTOR_W+x];}}
    }
    // Slanted stamina meter and high contrast score/timer, outside the 3D pass.
    vxpe2d_fill_rect(fb,240,320,8,8,104,13,rgb(17,25,27));
    for(int i=0;i<9;++i)for(int y=0;y<8;++y)vxpe2d_fill_rect(fb,240,320,12+i*10+y/3,10+y,7,1,rgb(255,214,31));
    char line[64];sprintf(line,"%05d",points);label(fb,17,30,line,rgb(12,24,29),2);label(fb,16,29,line,rgb(84,231,239),2);
    sprintf(line,"%03d",180-tick/30%180);label(fb,195,11,line,rgb(20,26,25),2);label(fb,193,9,line,rgb(255,135,20),2);
    if(grind){label(fb,12,249,"GRIND",rgb(15,24,24),2);label(fb,10,247,"GRIND",rgb(255,202,34),2);label(fb,12,270,"100  50",rgb(89,233,235));}
    vxpe2d_fill_rect(fb,240,320,0,289,240,31,rgb(13,22,32));label(fb,9,296,"4 6 STEER  5 JUMP  7 RAIL",rgb(218,228,223));
    label(fb,9,309,"0 CAMERA  9 PAUSE  2 8 SPEED",rgb(218,228,223));
    if(paused){vxpe2d_fill_rect(fb,240,320,62,145,116,29,rgb(13,22,32));label(fb,78,153,"PAUSED",rgb(255,212,39),2);}
}
