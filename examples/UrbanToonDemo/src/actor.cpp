#include "actor.h"
#include <math.h>
#include <assert.h>

namespace {
struct P {float x,y,z;};
struct Model {
    VxpeToonVertex3D vertices[384];
    VxpeToonMeshFace3D faces[640];
    VxpeToonMaterial3D materials[8],flat[8];
    unsigned nv,nf;
    void reset(){nv=nf=0;}
    void triangle(int a,int b,int c,int material){assert(nf<640);faces[nf++]={{(uint16_t)a,(uint16_t)c,(uint16_t)b},(uint16_t)material,0,255};}
    void quad(int a,int b,int c,int d,int material){triangle(a,b,c,material);triangle(a,c,d,material);}
    // Six-sided tapered bone; shared vertices, outward winding and no internal ink.
    void bone(P a,P b,float rx0,float rz0,float rx1,float rz1,int material){
        P axis={b.x-a.x,b.y-a.y,b.z-a.z};float length=sqrtf(axis.x*axis.x+axis.y*axis.y+axis.z*axis.z);if(length<.01f)return;
        axis.x/=length;axis.y/=length;axis.z/=length;
        P right={1-axis.x*axis.x,-axis.x*axis.y,-axis.x*axis.z};
        float n=sqrtf(right.x*right.x+right.y*right.y+right.z*right.z);
        if(n<.05f){right={-axis.z*axis.x,-axis.z*axis.y,1-axis.z*axis.z};n=sqrtf(right.x*right.x+right.y*right.y+right.z*right.z);}
        right.x/=n;right.y/=n;right.z/=n;
        P forward={right.y*axis.z-right.z*axis.y,right.z*axis.x-right.x*axis.z,right.x*axis.y-right.y*axis.x};
        static const float cs[6]={1,.5f,-.5f,-1,-.5f,.5f},sn[6]={0,.8660254f,.8660254f,0,-.8660254f,-.8660254f};
        int base=(int)nv;assert(nv+12<=384);
        for(int end=0;end<2;++end){P center=end?b:a;float rx=end?rx1:rx0,rz=end?rz1:rz0;
            for(int i=0;i<6;++i){P v={center.x+right.x*rx*cs[i]+forward.x*rz*sn[i],center.y+right.y*rx*cs[i]+forward.y*rz*sn[i],center.z+right.z*rx*cs[i]+forward.z*rz*sn[i]};
                vertices[nv++]={{(int32_t)lroundf(v.x),(int32_t)lroundf(v.y),(int32_t)lroundf(v.z)},0,0};}}
        for(int i=0;i<6;++i){int next=(i+1)%6;quad(base+i,base+next,base+next+6,base+i+6,material);}
        for(int i=1;i<5;++i){triangle(base,base+i+1,base+i,material);triangle(base+6,base+6+i,base+7+i,material);}
    }
};
static Model model;
static uint16_t rgb(int r,int g,int b){return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
static void build(const UrbanActorPose* pose){
    model.reset();
    const uint16_t colors[8]={rgb(255,204,21),rgb(30,37,39),rgb(225,177,125),rgb(231,54,26),rgb(103,229,36),rgb(10,15,18),rgb(251,227,29),rgb(239,75,102)};
    for(int i=0;i<8;++i){vxpe_toon3d_material_init(&model.materials[i],colors[i]);model.materials[i].outline_px=0;model.materials[i].fog_alpha=0;
        model.materials[i].shadow_threshold=138;model.materials[i].highlight_threshold=200;model.materials[i].shadow_q8=140;model.materials[i].midtone_q8=210;}
    float phase=pose->tick*.24f,cycle=sinf(phase),lean=pose->lean*.5f;
    bool jump=pose->jump!=0,grind=pose->grind!=0;
    float crouch=grind?10.f:jump?4.f:2.f+cycle*1.5f;
    P hips={lean,76-crouch,13},chest={lean+(grind?8:0),102-crouch,23};
    model.bone(hips,chest,16,10,22,12,0);
    model.bone({chest.x,105-crouch,24},{chest.x,112-crouch,25},4,4,4,4,2);
    model.bone({chest.x,110-crouch,25},{chest.x,129-crouch,27},8,8,8,8,2);
    model.bone({chest.x,126-crouch,26},{chest.x,132-crouch,27},10,10,10,10,3);
    model.bone({chest.x-9,119-crouch,26},{chest.x-12,119-crouch,26},6,6,6,6,5);
    model.bone({chest.x-12,119-crouch,26},{chest.x-13,119-crouch,26},3,3,3,3,4);
    model.bone({chest.x+9,119-crouch,26},{chest.x+12,119-crouch,26},6,6,6,6,5);
    model.bone({chest.x+12,119-crouch,26},{chest.x+13,119-crouch,26},3,3,3,3,4);
    // Goggles, cap visor and the original two-stripe jersey graphic.
    model.bone({chest.x-7,123-crouch,34},{chest.x+7,123-crouch,34},2,3,2,3,5);
    model.bone({chest.x-9,128-crouch,35},{chest.x+9,128-crouch,35},2,6,2,6,3);
    model.bone({chest.x-8,93-crouch,11},{chest.x+7,99-crouch,11},2,2,2,2,5);
    model.bone({chest.x-5,87-crouch,9},{chest.x+10,93-crouch,9},2,2,2,2,5);
    for(int side=-1;side<=1;side+=2){
        float stride=jump?29:grind?(side<0?-5:11):side*cycle*15;
        P hip={hips.x+side*9,hips.y,hips.z},knee={lean+side*14,46-crouch+(jump?12:0),25+stride*.35f};
        P ankle={side*(grind?13.f:11.f),18.f+(jump?27.f:0.f),stride+4};
        model.bone(ankle,knee,5,6,8,8,1);model.bone(knee,hip,8,8,9,9,1);
        P heel={ankle.x,ankle.y-8,ankle.z-10},toe={ankle.x,ankle.y-8,ankle.z+16};
        model.bone(heel,toe,8,6,8,5,6);
        model.bone({heel.x,heel.y-3,heel.z},{toe.x,toe.y-3,toe.z},9,2,9,2,3);
        for(int wheel=0;wheel<3;++wheel){float z=heel.z+3+wheel*9;
            model.bone({ankle.x-8,ankle.y-12,z},{ankle.x+8,ankle.y-12,z},3.5f,3.5f,3.5f,3.5f,4);}
        P shoulder={chest.x+side*18,chest.y-1,chest.z},elbow,wrist;
        if(jump){elbow={chest.x+side*33,chest.y+3,chest.z-3};wrist={chest.x+side*48,chest.y+11,chest.z-7};}
        else if(grind){elbow={chest.x+side*34,chest.y-4,chest.z-4};wrist={chest.x+side*47,chest.y-11,chest.z-10};}
        else{elbow={chest.x+side*26,chest.y-13,chest.z+3};wrist={chest.x+side*18,chest.y-29,chest.z+6+side*cycle*8};}
        model.bone(shoulder,elbow,8,7,6,6,0);model.bone(elbow,wrist,4,4,3,3,2);
        model.bone(wrist,{wrist.x,wrist.y-5,wrist.z+1},3,3,3,3,5);
    }
}
}
int urban_actor_vertex_count(){return (int)model.nv;}
int urban_actor_face_count(){return (int)model.nf;}
void urban_actor_draw(VxpeToonTarget3D* target,const VxpeToonCamera3D* camera,VxpeVec3D position,const UrbanActorPose* pose,bool shadow,bool render_body){
    if(!pose)return;build(pose);
    VxpeToonMesh3D mesh={model.vertices,model.faces,model.materials,0,(uint16_t)model.nv,(uint16_t)model.nf,8};
    VxpeToonTransform3D transform;vxpe_toon3d_transform_init(&transform);transform.position=position;
    int cosine=(pose->cos_yaw_q14||pose->sin_yaw_q14)?pose->cos_yaw_q14:16384,sine=pose->sin_yaw_q14;
    transform.basis_q14[0]=(int16_t)cosine;transform.basis_q14[2]=(int16_t)sine;transform.basis_q14[6]=(int16_t)-sine;transform.basis_q14[8]=(int16_t)cosine;
    if(shadow){
        for(int i=0;i<8;++i){vxpe_toon3d_material_init(&model.flat[i],rgb(49,54,57));model.flat[i].outline_px=0;model.flat[i].fog_alpha=0;}
        mesh.materials=model.flat;
        VxpeToonTransform3D ground=transform;ground.position.y=2;
        ground.basis_q14[1]=10000;ground.basis_q14[3]=ground.basis_q14[4]=ground.basis_q14[5]=0;ground.basis_q14[7]=6000;
        vxpe_toon3d_mesh(target,camera,&mesh,&ground,0,VXPE_TOON_CULL_NONE);
    }
    if(!render_body)return;
    // Inverted hull: expanded back faces make ink around the 3D silhouette only.
    for(int i=0;i<8;++i){vxpe_toon3d_material_init(&model.flat[i],rgb(13,19,22));model.flat[i].outline_px=0;model.flat[i].fog_alpha=0;}
    mesh.materials=model.flat;transform.scale_q8=264;
    vxpe_toon3d_mesh(target,camera,&mesh,&transform,0,VXPE_TOON_CULL_FRONT);
    mesh.materials=model.materials;transform.scale_q8=256;
    VxpeToonLight3D light;vxpe_toon3d_light_init(&light);
    vxpe_toon3d_mesh(target,camera,&mesh,&transform,&light,VXPE_TOON_CULL_BACK);
}
