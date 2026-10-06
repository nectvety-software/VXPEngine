#include "scene.h"
#include "assets.h"
#include "font.h"
#include "graphics/VxpDungeonFx.h"
#include "graphics/VxpRender2D.h"
#include <math.h>
#include <stdio.h>
static const char* map[10]={"#########","#.......#","#.......#","#..#.#..#","#.......#","###...###","#.......#","#.......#","#.......#","#########"};
static uint16_t rgb(int r,int g,int b){return vxpe2d_rgb565(r,g,b);}
static void label(uint16_t* fb,int x,int y,const char* s,uint16_t color,int scale=1){for(;*s;++s,x+=6*scale){int i=*s>='A'&&*s<='Z'?*s-'A':*s>='0'&&*s<='9'?26+*s-'0':-1;if(i<0)continue;for(int yy=0;yy<7;++yy)for(int xx=0;xx<5;++xx)if(FONT5X7[i][yy]&(1<<(4-xx)))vxpe2d_fill_rect(fb,240,320,x+xx*scale,y+yy*scale,scale,scale,color);}}
DungeonScene::DungeonScene(){exiting=false;selected=0;start();phase=0;}
void DungeonScene::start(){x=288;z=105;yaw=0;tick=0;health=100;slash=0;keys=0;phase=1;enemies[0]={180,263,3,0};enemies[1]={370,475,3,0};enemies[2]={210,530,4,0};}
bool DungeonScene::blocked(float px,float pz)const{int cx=(int)floorf(px/64),cz=(int)floorf(pz/64);return cx<0||cx>=9||cz<0||cz>=10||map[cz][cx]=='#';}
void DungeonScene::move(float d){float nx=x+sinf(yaw)*d,nz=z+cosf(yaw)*d;const float margin=9;
 if(!blocked(nx-margin,z)&&!blocked(nx+margin,z)&&!blocked(nx,z-margin)&&!blocked(nx,z+margin))x=nx;
 if(!blocked(x-margin,nz)&&!blocked(x+margin,nz)&&!blocked(x,nz-margin)&&!blocked(x,nz+margin))z=nz;}
static bool clearPath(const DungeonScene* s,float ax,float az,float bx,float bz){float dx=bx-ax,dz=bz-az;int steps=(int)(sqrtf(dx*dx+dz*dz)/5)+1;for(int i=1;i<steps;++i)if(s->blocked(ax+dx*i/steps,az+dz*i/steps))return false;return true;}
void DungeonScene::attack(){if(slash)return;slash=12;for(int i=0;i<3;++i){DungeonEnemy& e=enemies[i];float dx=e.x-x,dz=e.z-z,dist=sqrtf(dx*dx+dz*dz);if(e.hp>0&&dist<92&&clearPath(this,x,z,e.x,e.z)&&(dx*sinf(yaw)+dz*cosf(yaw))/ (dist+1)>.55f)--e.hp;}}
void DungeonScene::input(int key){if(key<0){if(phase==0)exiting=true;else phase=0;return;}
 if(phase==0){if(key==2||key==8)selected=1-selected;if(key==5){if(selected==0)start();else phase=5;}return;}
 if(phase==5){if(key==5||key==0)phase=0;return;}if(phase==3||phase==4){if(key==5)start();return;}
 if(key==9){phase=phase==2?1:2;return;}if(phase!=1)return;
 if(key==2)move(12);if(key==8)move(-10);if(key==4)yaw-=.15f;if(key==6)yaw+=.15f;if(key==5)attack();
 if(key==7){if(!keys&&(x-444)*(x-444)+(z-474)*(z-474)<64*64)keys=1;if(keys&&z<140&&x>430)phase=4;}
 if(key==0)start();}
void DungeonScene::update(){if(phase!=1)return;++tick;if(slash)--slash;
 for(int i=0;i<3;++i){DungeonEnemy& e=enemies[i];if(e.hp<=0)continue;if(e.cooldown)--e.cooldown;
 float dx=x-e.x,dz=z-e.z,d=sqrtf(dx*dx+dz*dz);if(d<170&&d>27&&clearPath(this,x,z,e.x,e.z)){float nx=e.x+dx/d*.6f,nz=e.z+dz/d*.6f;if(!blocked(nx,nz)){e.x=nx;e.z=nz;}}
 if(d<38&&!e.cooldown&&clearPath(this,x,z,e.x,e.z)){health-=8;e.cooldown=35;if(health<=0){health=0;phase=3;}}}}
static VxpeDungeonLight3D lights[5];
static void quad(VxpeToonTarget3D* t,VxpeToonCamera3D* c,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,VxpeVec3D e,uint16_t color,const VxpeSpriteA8* tex=0,bool repeat=false,bool emissive=false){
 VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,color);m.outline_px=0;m.fog565=rgb(22,11,32);m.fog_near_z=220;m.fog_far_z=700;m.fog_alpha=230;m.texture_wrap=repeat;
 if(!emissive){VxpeVec3D p={(a.x+b.x+d.x+e.x)/4,(a.y+b.y+d.y+e.y)/4,(a.z+b.z+d.z+e.z)/4};m.albedo565=vxpe_dungeon_light565(p,color,60,lights,5);}else m.fog_alpha=0;
 if(tex){int u=repeat?((b.x-a.x)+(b.z-a.z))*256:(tex->width-1)*256;int v=repeat?((d.y-b.y)+(d.z-b.z))*256:(tex->height-1)*256;
 VxpeToonVertex3D q[4]={{a,0,v},{b,u,v},{d,u,0},{e,0,0}};vxpe_toon3d_quad_textured(t,c,q,tex,&m,255);}else{VxpeVec3D q[4]={a,b,d,e};vxpe_toon3d_quad(t,c,q,&m,255);}}
static void box(VxpeToonTarget3D* t,VxpeToonCamera3D* c,int x,int y,int z,int w,int h,int len,uint16_t color,const VxpeSpriteA8* tex=0){
 int r=x+w,b=z+len,top=y+h;
 quad(t,c,{x,y,z},{r,y,z},{r,top,z},{x,top,z},color,tex,true);quad(t,c,{r,y,b},{x,y,b},{x,top,b},{r,top,b},color,tex,true);
 quad(t,c,{x,y,b},{x,y,z},{x,top,z},{x,top,b},color,tex,true);quad(t,c,{r,y,z},{r,y,b},{r,top,b},{r,top,z},color,tex,true);
 quad(t,c,{x,top,z},{r,top,z},{r,top,b},{x,top,b},color,tex,true);}
void DungeonScene::draw(uint16_t* fb){VxpeToonTarget3D target={fb,depth,240,320};vxpe_toon3d_clear(&target,0);vxpe_dungeon_mana_sky(fb,240,320,tick/2);
 VxpeToonCamera3D cam;vxpe_toon3d_camera_init(&cam,240,320);cam.position={(int)x,54,(int)z};cam.sin_yaw_q14=(int16_t)(sinf(yaw)*16384);cam.cos_yaw_q14=(int16_t)(cosf(yaw)*16384);cam.focal_px=165;cam.horizon_y=152;cam.near_z=3;cam.far_z=900;
 int flicker=210+(tick*13%31);lights[0]={{82,72,200},rgb(255,139,35),240,(uint8_t)flicker};lights[1]={{480,75,245},rgb(255,118,29),235,235};lights[2]={{292,75,435},rgb(140,68,255),250,220};lights[3]={{100,75,530},rgb(255,176,54),225,230};lights[4]={{(int)x,48,(int)z},rgb(175,171,152),135,125};
 const VxpeSpriteA8 stone={D_STONE,0,64,64,64,0,1},floor={D_FLOOR,0,64,64,64,0,1};
 for(int row=0;row<10;++row)for(int col=0;col<9;++col){int xx=col*64,zz=row*64;
 if(map[row][col]=='#')box(&target,&cam,xx,0,zz,64,112,64,0xffff,&stone);
 else{quad(&target,&cam,{xx,0,zz},{xx+64,0,zz},{xx+64,0,zz+64},{xx,0,zz+64},0xffff,&floor,true);
 if(row<5)quad(&target,&cam,{xx,116,zz+64},{xx+64,116,zz+64},{xx+64,116,zz},{xx,116,zz},rgb(138,125,99),&stone,true);}}
 // Distant castle towers rise above the open courtyard wall.
 for(int i=0;i<3;++i){int xx=80+i*185,zz=655+i%2*30;box(&target,&cam,xx,100,zz,64,130+i%2*40,64,rgb(156,141,171),&stone);
 VxpeToonMaterial3D roof;vxpe_toon3d_material_init(&roof,rgb(62,107,145));roof.outline_px=0;
 int yy=230+i%2*40;VxpeVec3D q[4]={{xx-5,yy,zz-5},{xx+69,yy,zz-5},{xx+69,yy,zz+69},{xx-5,yy,zz+69}};
 for(int k=0;k<4;++k)vxpe_toon3d_triangle(&target,&cam,q[k],q[(k+1)%4],{xx+32,yy+110,zz+32},&roof,(uint8_t)(145+k*25),0);}
 // Timber supports, torch brackets and the barred prison gate.
 for(int i=0;i<2;++i){int zz=155+i*110;box(&target,&cam,70,0,zz,8,105,10,rgb(145,100,63));box(&target,&cam,485,0,zz,8,105,10,rgb(145,100,63));box(&target,&cam,70,100,zz,425,9,10,rgb(125,87,58));}
 for(int i=0;i<4;++i){if(i==2)continue;int xx=lights[i].position.x,zz=lights[i].position.z;
 box(&target,&cam,xx-3,47,zz-3,6,22,6,rgb(108,69,39));
 quad(&target,&cam,{xx-6,69,zz},{xx+6,69,zz},{xx+2,88+tick%4,zz},{xx-2,88+tick%4,zz},rgb(255,174,38),0,false,true);
 quad(&target,&cam,{xx-2,69,zz-1},{xx+3,69,zz-1},{xx,81,zz-1},{xx-1,81,zz-1},rgb(255,243,157),0,false,true);}
 for(int i=0;i<7;++i)box(&target,&cam,430+i*9,0,78,3,90,4,rgb(116,108,95));box(&target,&cam,426,88,76,70,7,8,rgb(96,74,53));
 // Key pedestal and mana well in the open courtyard.
 box(&target,&cam,427,0,457,35,28,35,rgb(160,143,111),&stone);
 if(!keys){box(&target,&cam,440,31,466,4,16,4,rgb(255,226,92));box(&target,&cam,435,44,466,14,4,4,rgb(255,226,92));}
 box(&target,&cam,263,0,443,56,19,56,rgb(122,93,150),&stone);
 quad(&target,&cam,{267,20,447},{315,20,447},{315,20,495},{267,20,495},rgb(131,71,240),0,false,true);
 const VxpeSpriteA8 skeleton={D_SKELETON,D_SKELETON_A,64,96,64,64,0};
 VxpeToonMaterial3D bone;vxpe_toon3d_material_init(&bone,0xffff);bone.outline_px=0;bone.fog565=rgb(22,11,32);bone.fog_near_z=220;bone.fog_far_z=700;bone.fog_alpha=230;
 for(int i=0;i<3;++i)if(enemies[i].hp>0)vxpe_toon3d_billboard(&target,&cam,{(int)enemies[i].x,0,(int)enemies[i].z},44,87,&skeleton,&bone,200);
 // Foreground sword shares the generated Editor asset; A8 preserves the scene.
 const VxpeSpriteA8 sword={D_SWORD,D_SWORD_A,100,160,100,100,0};VxpeBlit565 op={};op.dst_x=slash?105+slash*3:140;op.dst_y=slash?158-slash*2:171;op.dst_w=100;op.dst_h=160;op.alpha=255;op.tint565=0xffff;vxpe2d_blit_a8(fb,240,320,&sword,&op);
 vxpe2d_fill_rect(fb,240,320,0,0,240,19,rgb(13,10,18));char text[48];sprintf(text,"HP %03d   KEY %d",health,keys);label(fb,10,6,text,rgb(232,209,151));label(fb,187,6,"MANA",rgb(185,140,233));
 vxpe2d_fill_rect(fb,240,320,0,288,240,32,rgb(13,10,18));label(fb,8,294,"2 8 MOVE  4 6 TURN  5 HIT",rgb(216,206,179));
 label(fb,8,308,"7 USE  9 PAUSE  BACK MENU",rgb(216,206,179));
 if(phase==0||phase==5){vxpe2d_fill_rect(fb,240,320,12,70,216,176,rgb(16,11,24));label(fb,30,84,"GNARLY",rgb(244,223,161),3);
 if(phase==0){label(fb,30,139,selected==0?"PLAY SELECTED":"PLAY",rgb(225,189,96),2);label(fb,30,171,selected==1?"GUIDE SELECTED":"GUIDE",rgb(174,142,214),2);label(fb,24,221,"2 8 SELECT  5 ENTER",rgb(199,186,167));}
 else{label(fb,24,137,"FIND KEY IN COURTYARD",rgb(225,213,178));label(fb,24,155,"USE KEY AT PRISON GATE",rgb(225,213,178));label(fb,24,173,"KEEP BONES AT SWORD RANGE",rgb(225,213,178));label(fb,24,221,"5 RETURN",rgb(177,136,225));}}
 if(phase==2||phase==3||phase==4){vxpe2d_fill_rect(fb,240,320,12,125,216,62,rgb(16,11,24));label(fb,25,139,phase==2?"PAUSED":phase==3?"FALLEN":"GATE OPEN",rgb(235,208,151),2);label(fb,25,168,phase==2?"9 CONTINUE":"5 RESTART",rgb(177,136,225));}
}
