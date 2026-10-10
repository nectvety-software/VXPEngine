// Original procedural martini study: geometry only, no video artwork/audio.
#include "ps1.h"
#include <math.h>
namespace {
const float PI=3.14159265358979f;
static uint16_t rgb(int r,int g,int b){return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
struct Painter {
 VxpeToonTarget3D* target;VxpeToonCamera3D camera;float yaw;
 VxpeVec3D vertex(float x,float y,float z)const{return {(int)(x*cosf(yaw)+z*sinf(yaw)),(int)y,(int)(z*cosf(yaw)-x*sinf(yaw))};}
 void tri(VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,uint16_t color,int cutout=0){VxpeToonMaterial3D m;vxpe_toon3d_material_init(&m,color);m.outline_px=0;m.fog_alpha=0;m.dither_cutout=(uint8_t)cutout;vxpe_toon3d_triangle(target,&camera,a,b,c,&m,255,0);}
 void quad(VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,VxpeVec3D d,uint16_t color,int cutout=0){tri(a,b,c,color,cutout);tri(a,c,d,color,cutout);}
 VxpeVec3D ring(int i,int n,float radius,float y)const{float angle=i*2*PI/n;return vertex(cosf(angle)*radius,y,sinf(angle)*radius);}
 void disk(float radius,float y,uint16_t color,int cutout=0){for(int i=0;i<16;++i)tri(vertex(0,y,0),ring(i,16,radius,y),ring(i+1,16,radius,y),color,cutout);}
 void tube(float radius,float y,float height,uint16_t color){for(int i=0;i<12;++i)quad(ring(i,12,radius,y),ring(i+1,12,radius,y),ring(i+1,12,radius,y+height),ring(i,12,radius,y+height),color);}
};
}
void urban_ps1_render(VxpeToonTarget3D* target,int tick,int steps,bool fixed){
 if(!target)return;vxpe_toon3d_clear(target,0);
 Painter p;p.target=target;p.yaw=steps*.14f+(fixed?.65f:tick*.025f);
 vxpe_toon3d_camera_init(&p.camera,target->width,target->height);p.camera.position={0,178,-300};
 p.camera.focal_px=(uint16_t)(target->width*4/3);p.camera.horizon_y=(int16_t)(target->height*53/100);
 p.camera.sin_pitch_q14=4096;p.camera.cos_pitch_q14=15864;
 if(fixed){p.camera.position={150,200,-260};p.camera.sin_yaw_q14=-8192;p.camera.cos_yaw_q14=14189;p.camera.sin_pitch_q14=5181;p.camera.cos_pitch_q14=15543;
  // Fixed-camera 2.5D diorama; counter stays still while the prop can turn.
  p.quad({-95,-5,-60},{95,-5,-60},{95,-5,90},{-95,-5,90},rgb(76,53,42));
  p.quad({-95,-18,-60},{95,-18,-60},{95,-5,-60},{-95,-5,-60},rgb(110,73,43));
  p.quad({95,-18,-60},{95,-18,90},{95,-5,90},{95,-5,-60},rgb(47,37,40));
 }
 // Opaque base, slim stem and greenish liquid are drawn before glass coverage.
 p.disk(34,4,rgb(41,54,51));p.tube(34,4,3,rgb(130,161,153));p.disk(30,8,rgb(27,38,35));
 p.tube(2,9,110,rgb(139,173,161));p.tube(1,9,110,rgb(217,231,211));
 p.disk(53,185,rgb(140,151,124));
 for(int i=0;i<16;++i){int light=(i%4)*11;p.quad(p.ring(i,16,3,118),p.ring(i+1,16,3,118),p.ring(i+1,16,53,185),p.ring(i,16,53,185),rgb(92+light,110+light,93+light),80);}
 // Olive: faceted ellipsoid, offset on a diagonally tilted wooden pick.
 const float ox=27,oy=192,oz=6;
 for(int band=0;band<3;++band){float a=-PI/2+band*PI/3,b=a+PI/3;
  for(int i=0;i<8;++i){float u=i*PI/4,v=u+PI/4;
   p.quad(p.vertex(ox+cosf(a)*cosf(u)*10,oy+sinf(a)*9,oz+cosf(a)*sinf(u)*9),p.vertex(ox+cosf(a)*cosf(v)*10,oy+sinf(a)*9,oz+cosf(a)*sinf(v)*9),p.vertex(ox+cosf(b)*cosf(v)*10,oy+sinf(b)*9,oz+cosf(b)*sinf(v)*9),p.vertex(ox+cosf(b)*cosf(u)*10,oy+sinf(b)*9,oz+cosf(b)*sinf(u)*9),rgb(110+(i%3)*22,144+(i%3)*17,21));}}
 p.quad(p.vertex(24,190,-3),p.vertex(28,190,-3),p.vertex(28,194,-3),p.vertex(24,194,-3),rgb(160,67,35));
 p.quad(p.vertex(8,163,5),p.vertex(10,163,5),p.vertex(62,239,7),p.vertex(60,239,7),rgb(188,157,96));
 p.quad(p.vertex(9,163,4),p.vertex(9,163,6),p.vertex(61,239,8),p.vertex(61,239,6),rgb(229,201,137));
 // Sparse glass facets leave checker holes through which liquid/olive remain visible.
 for(int i=0;i<16;++i){int shade=i%5;
  p.quad(p.ring(i,16,2,116),p.ring(i+1,16,2,116),p.ring(i+1,16,64,203),p.ring(i,16,64,203),rgb(153+shade*12,177+shade*9,166+shade*10),192);
  p.quad(p.ring(i,16,62,202),p.ring(i+1,16,62,202),p.ring(i+1,16,65,204),p.ring(i,16,65,204),rgb(185,211,195),32);}
 // Fine asymmetrical highlights and rim catch the light as the model turns.
 p.quad(p.vertex(-55,198,-21),p.vertex(-53,198,-21),p.vertex(-2,123,0),p.vertex(-4,123,0),rgb(202,228,210),48);
}
