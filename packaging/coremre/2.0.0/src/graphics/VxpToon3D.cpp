#include "graphics/VxpToon3D.h"
#include <string.h>
#include <stdlib.h>
#include <limits.h>

namespace {
static const int64_t INV_ONE=1<<24;
struct View { int64_t x,y,z; uint8_t incoming_ink; int64_t u,v; uint8_t light; };
struct Screen { int64_t x,y,inv,u_over_z,v_over_z,light_over_z,z; uint8_t light; };
static int bound(int64_t v,int lo,int hi){return v<lo?lo:v>hi?hi:(int)v;}
static int biased_z(int z,int bias){int v=z+bias;return v<1?1:v>65534?65534:v;}
static bool valid(const VxpeToonCamera3D* c){return c&&c->near_z&&c->far_z>c->near_z&&c->far_z<65535&&c->focal_px&&c->focal_px<=4096;}
static bool target(const VxpeToonTarget3D* t){return t&&t->pixels&&t->depth&&t->width&&t->height&&t->width<=2048&&t->height<=2048;}
static View view(const VxpeToonCamera3D* c,VxpeVec3D p){
    int64_t dx=(int64_t)p.x-c->position.x,dz=(int64_t)p.z-c->position.z;
    View v={(dx*c->cos_yaw_q14-dz*c->sin_yaw_q14)/16384,(int64_t)p.y-c->position.y,
            (dx*c->sin_yaw_q14+dz*c->cos_yaw_q14)/16384,0,0,0,0};
    // Bound input before clipping/interpolation to keep all products within int64.
    if(c->sin_pitch_q14||c->cos_pitch_q14){
        int64_t y=(v.y*c->cos_pitch_q14+v.z*c->sin_pitch_q14)/16384;
        v.z=(-v.y*c->sin_pitch_q14+v.z*c->cos_pitch_q14)/16384;v.y=y;
    }
    v.x=bound(v.x,-1048576,1048576);v.y=bound(v.y,-1048576,1048576);v.z=bound(v.z,-1048576,1048576);return v;
}
static Screen project(const VxpeToonCamera3D* c,View v){
    Screen s={bound(c->center_x+v.x*c->focal_px/v.z,-262144,262144),
              bound(c->horizon_y-v.y*c->focal_px/v.z,-262144,262144),INV_ONE/v.z,
              v.u*(INV_ONE/v.z),v.v*(INV_ONE/v.z),v.light*(INV_ONE/v.z),v.z,v.light};return s;
}
static int64_t edge(Screen a,Screen b,int64_t x,int64_t y){return (b.x-a.x)*(y-a.y)-(b.y-a.y)*(x-a.x);}
static inline int64_t floor_quotient(int64_t numerator,int64_t denominator,int64_t& remainder){
    int64_t quotient=numerator/denominator;remainder=numerator%denominator;
    if(remainder<0){--quotient;remainder+=denominator;}return quotient;
}
static inline void step_quotient(int64_t& quotient,int64_t& remainder,int64_t stepQ,int64_t stepR,int64_t denominator){
    quotient+=stepQ;remainder+=stepR;
    if(remainder>=denominator){++quotient;remainder-=denominator;}
}
static uint16_t mix(uint16_t a,uint16_t b,int alpha){
    int inv=255-alpha;
    return (uint16_t)(((((a>>11)*inv+(b>>11)*alpha)/255)<<11)|
            (((((a>>5)&63)*inv+((b>>5)&63)*alpha)/255)<<5)|
            (((a&31)*inv+(b&31)*alpha)/255));
}
static uint8_t band(const VxpeToonMaterial3D* m,uint8_t light){return light<m->shadow_threshold?m->shadow_q8:light<m->highlight_threshold?m->midtone_q8:m->highlight_q8;}
static uint16_t multiply(uint16_t c,int factor){return (uint16_t)((((c>>11)*factor/255)<<11)|((((c>>5)&63)*factor/255)<<5)|((c&31)*factor/255));}
static int fog_alpha(const VxpeToonMaterial3D* m,int z){
    if(m->fog_far_z<=m->fog_near_z||z<=m->fog_near_z)return 0;
    return bound((int64_t)(z-m->fog_near_z)*m->fog_alpha/(m->fog_far_z-m->fog_near_z),0,m->fog_alpha);
}
static int clip(const View* in,int n,View* out,int z,bool near,bool cutInk){
    int count=0;View previous=in[n-1];bool previousInside=near?previous.z>=z:previous.z<=z;
    for(int i=0;i<n;++i){View current=in[i];bool inside=near?current.z>=z:current.z<=z;
        if(inside!=previousInside){int64_t numerator=z-previous.z,denominator=current.z-previous.z;
            View p={previous.x+(current.x-previous.x)*numerator/denominator,previous.y+(current.y-previous.y)*numerator/denominator,z,
                    (uint8_t)(inside?cutInk:current.incoming_ink),
                    previous.u+(current.u-previous.u)*numerator/denominator,
                    previous.v+(current.v-previous.v)*numerator/denominator,
                    (uint8_t)bound((int64_t)previous.light+((int64_t)current.light-previous.light)*numerator/denominator,0,255)};out[count++]=p;}
        if(inside)out[count++]=current;
        previous=current;previousInside=inside;
    }return count;
}
static bool covered(const VxpeSpriteA8* sprite,int x,int y);
static int raster(VxpeToonTarget3D* t,Screen a,Screen b,Screen c,const VxpeToonMaterial3D* m,uint16_t fill,uint16_t ink,uint8_t mask,const VxpeSpriteA8* texture){
    int64_t area=edge(a,b,c.x,c.y);if(!area)return 0;
    if(area<0){Screen p=b;b=c;c=p;area=-area;mask=(mask&2)|((mask&1)<<2)|((mask&4)>>2);}
    /* Top-left fill rule. In this screen space (y down) a positive-area triangle
     * keeps the interior on the right of every directed edge, so a pixel lying
     * exactly on an edge belongs to the triangle that owns it: the edge directed
     * downwards, or a horizontal edge directed to the left. Two triangles that
     * share an edge traverse it in opposite directions, so exactly one of them
     * keeps the boundary pixels. Without this both triangles of a quad cover their
     * shared diagonal and the visible pixel is whichever was submitted last, so
     * seams and coincident faces change with draw order instead of geometry. */
    const bool ownBC=(c.y-b.y)>0||((c.y-b.y)==0&&(c.x-b.x)<0);
    const bool ownCA=(a.y-c.y)>0||((a.y-c.y)==0&&(a.x-c.x)<0);
    const bool ownAB=(b.y-a.y)>0||((b.y-a.y)==0&&(b.x-a.x)<0);
    const int64_t rawMinX=a.x<b.x?(a.x<c.x?a.x:c.x):(b.x<c.x?b.x:c.x);
    const int64_t rawMaxX=a.x>b.x?(a.x>c.x?a.x:c.x):(b.x>c.x?b.x:c.x);
    const int64_t rawMinY=a.y<b.y?(a.y<c.y?a.y:c.y):(b.y<c.y?b.y:c.y);
    const int64_t rawMaxY=a.y>b.y?(a.y>c.y?a.y:c.y):(b.y>c.y?b.y:c.y);
    if(rawMaxX<0||rawMinX>=t->width||rawMaxY<0||rawMinY>=t->height)return 0;
    int minX=bound(rawMinX,0,t->width-1);
    int maxX=bound(rawMaxX,0,t->width-1);
    int minY=bound(rawMinY,0,t->height-1);
    int maxY=bound(rawMaxY,0,t->height-1);
    int width=bound(m->outline_px,0,4),drawn=0;
    int64_t limits[3]={width*(llabs(c.x-b.x)+llabs(c.y-b.y)),width*(llabs(a.x-c.x)+llabs(a.y-c.y)),width*(llabs(b.x-a.x)+llabs(b.y-a.y))};
    // Edge values form an affine plane in screen space. Start once per row,
    // then step with additions instead of evaluating three 64-bit products
    // for every covered candidate pixel (important on S30+ ARM without an FPU).
    const int64_t stepX0=-(c.y-b.y),stepX1=-(a.y-c.y),stepX2=-(b.y-a.y);
    const int64_t stepY0=c.x-b.x,stepY1=a.x-c.x,stepY2=b.x-a.x;
    int64_t rowW0=edge(b,c,minX,minY),rowW1=edge(c,a,minX,minY),rowW2=edge(a,b,minX,minY);
    const bool smoothLight=a.light!=b.light||b.light!=c.light;
    const bool affineDepth=m->affine_depth&&!texture&&!smoothLight&&!m->fog_alpha;
    // Carry exact barycentric quotients/remainders across x/y on 32-bit ARM.
    // This preserves integer results while removing software 64-bit divides
    // from both exact-depth and perspective-texture pixel loops.
#if defined(VXPE_TOON3D_STEPPED_RECIPROCAL) || (defined(__arm__) && !defined(__aarch64__))
    const bool steppedReciprocal=!affineDepth&&!smoothLight;
#else
    const bool steppedReciprocal=false;
#endif
    const bool steppedTextureWeights=steppedReciprocal&&texture;
    const int64_t zStepX=affineDepth?(stepX0*a.z+stepX1*b.z+stepX2*c.z)/area:0;
    const int64_t zStepY=affineDepth?(stepY0*a.z+stepY1*b.z+stepY2*c.z)/area:0;
    int64_t rowZ=affineDepth?(rowW0*a.z+rowW1*b.z+rowW2*c.z)/area:0;
    const int64_t reciprocalGradientX=steppedReciprocal?stepX0*a.inv+stepX1*b.inv+stepX2*c.inv:0;
    const int64_t reciprocalGradientY=steppedReciprocal?stepY0*a.inv+stepY1*b.inv+stepY2*c.inv:0;
    int64_t reciprocalStepX=0,reciprocalRemStepX=0,reciprocalStepY=0,reciprocalRemStepY=0;
    int64_t rowReciprocal=0,rowReciprocalRem=0;
    int64_t weightStepX0=0,weightRemStepX0=0,weightStepX1=0,weightRemStepX1=0;
    int64_t weightStepY0=0,weightRemStepY0=0,weightStepY1=0,weightRemStepY1=0;
    int64_t rowWeight0=0,rowWeightRem0=0,rowWeight1=0,rowWeightRem1=0;
    if(steppedReciprocal){
        reciprocalStepX=floor_quotient(reciprocalGradientX,area,reciprocalRemStepX);
        reciprocalStepY=floor_quotient(reciprocalGradientY,area,reciprocalRemStepY);
        int64_t rowNumerator=rowW0*a.inv+rowW1*b.inv+rowW2*c.inv;
        rowReciprocal=floor_quotient(rowNumerator,area,rowReciprocalRem);
    }
    if(steppedTextureWeights){
        weightStepX0=floor_quotient(stepX0*4096,area,weightRemStepX0);
        weightStepX1=floor_quotient(stepX1*4096,area,weightRemStepX1);
        weightStepY0=floor_quotient(stepY0*4096,area,weightRemStepY0);
        weightStepY1=floor_quotient(stepY1*4096,area,weightRemStepY1);
        rowWeight0=floor_quotient(rowW0*4096,area,rowWeightRem0);
        rowWeight1=floor_quotient(rowW1*4096,area,rowWeightRem1);
    }
    for(int y=minY;y<=maxY;++y){
      int64_t w0=rowW0,w1=rowW1,w2=rowW2;
      int64_t z=rowZ;
      int64_t reciprocal=rowReciprocal,reciprocalRem=rowReciprocalRem;
      int64_t q0=rowWeight0,q0Rem=rowWeightRem0,q1=rowWeight1,q1Rem=rowWeightRem1;
      for(int x=minX;x<=maxX;++x,w0+=stepX0,w1+=stepX1,w2+=stepX2,z+=zStepX,
          (steppedReciprocal?(step_quotient(reciprocal,reciprocalRem,reciprocalStepX,reciprocalRemStepX,area),0):0),
          (steppedTextureWeights?(step_quotient(q0,q0Rem,weightStepX0,weightRemStepX0,area),0):0),
          (steppedTextureWeights?(step_quotient(q1,q1Rem,weightStepX1,weightRemStepX1,area),0):0)){
        if(w0<0||w1<0||w2<0)continue;
        if((!ownBC&&!w0)||(!ownCA&&!w1)||(!ownAB&&!w2))continue;
        if(!steppedReciprocal&&!affineDepth)reciprocal=(w0*a.inv+w1*b.inv+w2*c.inv)/area;
        if(!affineDepth&&reciprocal<=0)continue;
        int pixelZ=affineDepth?bound(z,1,65534):bound(INV_ONE/reciprocal,1,65534);int index=y*t->width+x;
        int testZ=biased_z(pixelZ,m->depth_bias);
        if(testZ>t->depth[index])continue;
        static const uint8_t bayer[16]={0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
        if(m->dither_cutout&&bayer[(y&3)*4+(x&3)]*16<m->dither_cutout)continue;
        uint8_t pixelLight=a.light;
        if(smoothLight){int64_t lq0=w0*4096/area,lq1=w1*4096/area,lq2=4096-lq0-lq1;
            int64_t lz=(lq0*a.light_over_z+lq1*b.light_over_z+lq2*c.light_over_z)/4096;
            pixelLight=(uint8_t)bound(lz/reciprocal,0,255);}
        bool outline=width&&(((mask&2)&&w0<limits[0])||((mask&4)&&w1<limits[1])||((mask&1)&&w2<limits[2]));
        if(texture){
            // Normalize barycentric weights first: avoids large UV*area products.
            if(!steppedTextureWeights){q0=w0*4096/area;q1=w1*4096/area;}
            int64_t q2=4096-q0-q1;
            int64_t u=(q0*a.u_over_z+q1*b.u_over_z+q2*c.u_over_z)/4096/reciprocal;
            int64_t v=(q0*a.v_over_z+q1*b.v_over_z+q2*c.v_over_z)/4096/reciprocal;
            int64_t ux=u>=0?u/256:-((-u+255)/256),vy=v>=0?v/256:-((-v+255)/256);
            int tx,ty;
            if(m->texture_wrap){
                tx=(texture->width&(texture->width-1))?(int)(ux%texture->width):((int)ux&(texture->width-1));
                ty=(texture->height&(texture->height-1))?(int)(vy%texture->height):((int)vy&(texture->height-1));
                if(tx<0)tx+=texture->width;
                if(ty<0)ty+=texture->height;
            }else{tx=bound(ux,0,texture->width-1);ty=bound(vy,0,texture->height-1);}
            if(!covered(texture,tx,ty))continue;
            uint16_t color=texture->pixels[ty*(texture->stride?texture->stride:texture->width)+tx];
            fill=multiply(vxpe2d_tint565(color,m->albedo565),band(m,pixelLight));
        }
        uint16_t color=outline?ink:(texture?fill:(smoothLight?vxpe_toon3d_shade(m,pixelLight):fill));int fog=fog_alpha(m,pixelZ);
        t->pixels[index]=fog?mix(color,m->fog565,fog):color;t->depth[index]=(uint16_t)testZ;++drawn;
      }
      rowW0+=stepY0;rowW1+=stepY1;rowW2+=stepY2;rowZ+=zStepY;
      if(steppedReciprocal)step_quotient(rowReciprocal,rowReciprocalRem,reciprocalStepY,reciprocalRemStepY,area);
      if(steppedTextureWeights){
        step_quotient(rowWeight0,rowWeightRem0,weightStepY0,weightRemStepY0,area);
        step_quotient(rowWeight1,rowWeightRem1,weightStepY1,weightRemStepY1,area);
      }
    }return drawn;
}
static bool covered(const VxpeSpriteA8* sprite,int x,int y){
    if(x<0||y<0||x>=sprite->width||y>=sprite->height)return false;
    return sprite->opaque||!sprite->alpha||sprite->alpha[y*(sprite->alpha_stride?sprite->alpha_stride:sprite->width)+x]>=128;
}
static bool valid_sprite(const VxpeSpriteA8* s){return s&&s->pixels&&s->width&&s->height&&(!s->stride||s->stride>=s->width)&&(!s->alpha_stride||s->alpha_stride>=s->width);}
static int render_triangle(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,View original[3],const VxpeSpriteA8* texture,const VxpeToonMaterial3D* m,uint8_t light,uint8_t mask,const uint8_t* vertexLight=0){
    View nearPoly[6],polygon[6];
    for(int i=0;i<3;++i)original[i].light=vertexLight?vertexLight[i]:light;
    original[0].incoming_ink=(mask&4)!=0;original[1].incoming_ink=(mask&1)!=0;original[2].incoming_ink=(mask&2)!=0;
    int n=clip(original,3,nearPoly,c->near_z,true,mask!=0);if(n<3)return 0;
    n=clip(nearPoly,n,polygon,c->far_z,false,mask!=0);if(n<3)return 0;
    uint16_t fill=vxpe_toon3d_shade(m,light),ink=m->ink565;int drawn=0;
    for(int i=1;i<n-1;++i){
        uint8_t edges=(uint8_t)((i==1&&polygon[i].incoming_ink?1:0)|(polygon[i+1].incoming_ink?2:0)|(i==n-2&&polygon[0].incoming_ink?4:0));
        drawn+=raster(t,project(c,polygon[0]),project(c,polygon[i]),project(c,polygon[i+1]),m,fill,ink,edges,texture);
    }return drawn;
}
}

void vxpe_toon3d_camera_init(VxpeToonCamera3D* c,int w,int h){
    if(!c)return;
    memset(c,0,sizeof(*c));c->cos_yaw_q14=16384;c->center_x=(int16_t)bound(w/2,-32768,32767);c->horizon_y=(int16_t)bound(h/2,-32768,32767);
    c->focal_px=(uint16_t)bound((int64_t)w*3/5,1,4096);c->near_z=8;c->far_z=4096;
    c->cos_pitch_q14=16384;
}
void vxpe_toon3d_transform_init(VxpeToonTransform3D* transform){
    if(!transform)return;
    memset(transform,0,sizeof(*transform));transform->basis_q14[0]=transform->basis_q14[4]=transform->basis_q14[8]=16384;transform->scale_q8=256;
}
VxpeVec3D vxpe_toon3d_transform_point(const VxpeToonTransform3D* t,VxpeVec3D p){
    if(!t)return p;
    int64_t x=(((int64_t)t->basis_q14[0]*p.x+(int64_t)t->basis_q14[1]*p.y+(int64_t)t->basis_q14[2]*p.z)/256)*t->scale_q8/16384;
    int64_t y=(((int64_t)t->basis_q14[3]*p.x+(int64_t)t->basis_q14[4]*p.y+(int64_t)t->basis_q14[5]*p.z)/256)*t->scale_q8/16384;
    int64_t z=(((int64_t)t->basis_q14[6]*p.x+(int64_t)t->basis_q14[7]*p.y+(int64_t)t->basis_q14[8]*p.z)/256)*t->scale_q8/16384;
    VxpeVec3D result={bound(x+t->position.x,INT_MIN,INT_MAX),bound(y+t->position.y,INT_MIN,INT_MAX),bound(z+t->position.z,INT_MIN,INT_MAX)};return result;
}
void vxpe_toon3d_light_init(VxpeToonLight3D* light){
    if(!light)return;
    light->x_q14=-8192;light->y_q14=12288;light->z_q14=-6144;light->ambient=100;light->diffuse=155;
}
namespace {
static uint32_t integer_sqrt(uint64_t n){
    uint64_t result=0,bit=(uint64_t)1<<62;while(bit>n)bit>>=2;
    while(bit){if(n>=result+bit){n-=result+bit;result=(result>>1)+bit;}else result>>=1;bit>>=2;}return (uint32_t)result;
}
static void normal(VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,int64_t& nx,int64_t& ny,int64_t& nz){
    int64_t ux=bound((int64_t)b.x-a.x,-32767,32767),uy=bound((int64_t)b.y-a.y,-32767,32767),uz=bound((int64_t)b.z-a.z,-32767,32767);
    int64_t vx=bound((int64_t)c.x-a.x,-32767,32767),vy=bound((int64_t)c.y-a.y,-32767,32767),vz=bound((int64_t)c.z-a.z,-32767,32767);
    nx=uy*vz-uz*vy;ny=uz*vx-ux*vz;nz=ux*vy-uy*vx;
}
static int64_t facing(const VxpeToonCamera3D* c,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d){
    View va=view(c,a),vb=view(c,b),vd=view(c,d);
    VxpeVec3D pa={bound(va.x,-32767,32767),bound(va.y,-32767,32767),bound(va.z,-32767,32767)};
    VxpeVec3D pb={bound(vb.x,-32767,32767),bound(vb.y,-32767,32767),bound(vb.z,-32767,32767)};
    VxpeVec3D pd={bound(vd.x,-32767,32767),bound(vd.y,-32767,32767),bound(vd.z,-32767,32767)};
    int64_t nx,ny,nz;normal(pa,pb,pd,nx,ny,nz);return nx*pa.x+ny*pa.y+nz*pa.z;
}
}
uint8_t vxpe_toon3d_face_light(VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,const VxpeToonLight3D* light){
    if(!light)return 255;
    int64_t nx,ny,nz;normal(a,b,c,nx,ny,nz);
    uint64_t square=(uint64_t)(nx*nx)+(uint64_t)(ny*ny)+(uint64_t)(nz*nz);
    uint32_t length=integer_sqrt(square);if(!length)return light->ambient;
    int64_t dot=nx*light->x_q14+ny*light->y_q14+nz*light->z_q14;
    if(dot<=0)return light->ambient;
    return (uint8_t)bound(light->ambient+dot*light->diffuse/((int64_t)length*16384),0,255);
}
int vxpe_toon3d_mesh(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeToonMesh3D* mesh,const VxpeToonTransform3D* transform,const VxpeToonLight3D* light,VxpeToonCull3D cull){
    if(!target(t)||!valid(c)||!mesh||!mesh->vertices||!mesh->faces||!mesh->materials||!mesh->vertex_count||!mesh->material_count)return 0;
    int64_t drawn=0;
    for(uint32_t i=0;i<mesh->face_count;++i){const VxpeToonMeshFace3D& face=mesh->faces[i];
        if(face.material>=mesh->material_count||face.indices[0]>=mesh->vertex_count||face.indices[1]>=mesh->vertex_count||face.indices[2]>=mesh->vertex_count)continue;
        VxpeToonVertex3D vertices[3];for(int j=0;j<3;++j){vertices[j]=mesh->vertices[face.indices[j]];vertices[j].position=vxpe_toon3d_transform_point(transform,vertices[j].position);}
        int64_t side=facing(c,vertices[0].position,vertices[1].position,vertices[2].position);
        if((cull==VXPE_TOON_CULL_BACK&&side>=0)||(cull==VXPE_TOON_CULL_FRONT&&side<=0))continue;
        uint8_t illumination=light?vxpe_toon3d_face_light(vertices[0].position,vertices[1].position,vertices[2].position,light):face.illumination;
        const VxpeSpriteA8* texture=mesh->textures?mesh->textures[face.material]:0;
        if(texture)drawn+=vxpe_toon3d_triangle_textured(t,c,vertices,texture,&mesh->materials[face.material],illumination,face.edge_mask);
        else drawn+=vxpe_toon3d_triangle(t,c,vertices[0].position,vertices[1].position,vertices[2].position,&mesh->materials[face.material],illumination,face.edge_mask);
    }return bound(drawn,0,INT_MAX);
}
void vxpe_toon3d_material_init(VxpeToonMaterial3D* m,uint16_t color){
    if(!m)return;
    memset(m,0,sizeof(*m));m->albedo565=color;m->ink565=0x0842;m->fog565=0x8ddd;
    m->shadow_threshold=85;m->highlight_threshold=190;m->shadow_q8=105;m->midtone_q8=190;m->highlight_q8=255;m->outline_px=1;
    m->fog_near_z=600;m->fog_far_z=1800;m->fog_alpha=100;
}
void vxpe_toon3d_clear(VxpeToonTarget3D* t,uint16_t background){
    if(!target(t))return;
    const uint32_t count=(uint32_t)t->width*t->height;
    for(uint32_t i=0;i<count;++i)t->pixels[i]=background;
    vxpe_toon3d_clear_depth(t);
}
void vxpe_toon3d_clear_depth(VxpeToonTarget3D* t){
    if(!target(t))return;
    memset(t->depth,0xFF,(size_t)t->width*t->height*sizeof(uint16_t));
}
uint16_t vxpe_toon3d_shade(const VxpeToonMaterial3D* m,uint8_t light){return m?multiply(m->albedo565,band(m,light)):0;}
int vxpe_toon3d_project(const VxpeToonCamera3D* c,VxpeVec3D p,VxpeToonPoint3D* out){
    if(!out)return 0;
    memset(out,0,sizeof(*out));if(!valid(c))return 0;View v=view(c,p);if(v.z<c->near_z||v.z>c->far_z)return 0;
    Screen s=project(c,v);out->x=(int32_t)s.x;out->y=(int32_t)s.y;out->z=(uint16_t)v.z;out->visible=1;return 1;
}
int vxpe_toon3d_triangle(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,const VxpeToonMaterial3D* m,uint8_t light,uint8_t mask){
    if(!target(t)||!valid(c)||!m)return 0;
    View original[3]={view(c,a),view(c,b),view(c,d)};
    return render_triangle(t,c,original,0,m,light,mask);
}
int vxpe_toon3d_triangle_gouraud(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,VxpeVec3D a,VxpeVec3D b,VxpeVec3D d,const VxpeToonMaterial3D* m,const uint8_t light[3],uint8_t mask){
    if(!target(t)||!valid(c)||!m||!light)return 0;
    View original[3]={view(c,a),view(c,b),view(c,d)};
    return render_triangle(t,c,original,0,m,light[0],mask,light);
}
int vxpe_toon3d_quad(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeVec3D* v,const VxpeToonMaterial3D* m,uint8_t light){
    if(!v)return 0;
    return vxpe_toon3d_triangle(t,c,v[0],v[1],v[2],m,light,3)+vxpe_toon3d_triangle(t,c,v[0],v[2],v[3],m,light,6);
}
int vxpe_toon3d_quad_gouraud(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeVec3D* v,const VxpeToonMaterial3D* m,const uint8_t light[4]){
    if(!v||!light)return 0;
    const uint8_t first[3]={light[0],light[1],light[2]},second[3]={light[0],light[2],light[3]};
    return vxpe_toon3d_triangle_gouraud(t,c,v[0],v[1],v[2],m,first,3)+vxpe_toon3d_triangle_gouraud(t,c,v[0],v[2],v[3],m,second,6);
}
int vxpe_toon3d_triangle_textured(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeToonVertex3D* vertices,const VxpeSpriteA8* texture,const VxpeToonMaterial3D* m,uint8_t light,uint8_t mask){
    if(!target(t)||!valid(c)||!m||!vertices||!valid_sprite(texture))return 0;
    View original[3];for(int i=0;i<3;++i){original[i]=view(c,vertices[i].position);original[i].u=bound(vertices[i].u_q8,-16776960,16776960);original[i].v=bound(vertices[i].v_q8,-16776960,16776960);}
    return render_triangle(t,c,original,texture,m,light,mask);
}
int vxpe_toon3d_quad_textured(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeToonVertex3D* v,const VxpeSpriteA8* texture,const VxpeToonMaterial3D* m,uint8_t light){
    if(!v)return 0;
    VxpeToonVertex3D a[3]={v[0],v[1],v[2]},b[3]={v[0],v[2],v[3]};
    return vxpe_toon3d_triangle_textured(t,c,a,texture,m,light,3)+vxpe_toon3d_triangle_textured(t,c,b,texture,m,light,6);
}
int vxpe_toon3d_triangle_gouraud_textured(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeToonVertex3D* vertices,const VxpeSpriteA8* texture,const VxpeToonMaterial3D* m,const uint8_t light[3],uint8_t mask){
    if(!target(t)||!valid(c)||!m||!vertices||!light||!valid_sprite(texture))return 0;
    View original[3];for(int i=0;i<3;++i){original[i]=view(c,vertices[i].position);original[i].u=bound(vertices[i].u_q8,-16776960,16776960);original[i].v=bound(vertices[i].v_q8,-16776960,16776960);}
    return render_triangle(t,c,original,texture,m,light[0],mask,light);
}
int vxpe_toon3d_quad_gouraud_textured(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,const VxpeToonVertex3D* v,const VxpeSpriteA8* texture,const VxpeToonMaterial3D* m,const uint8_t light[4]){
    if(!v||!light)return 0;
    VxpeToonVertex3D a[3]={v[0],v[1],v[2]},b[3]={v[0],v[2],v[3]};
    const uint8_t la[3]={light[0],light[1],light[2]},lb[3]={light[0],light[2],light[3]};
    return vxpe_toon3d_triangle_gouraud_textured(t,c,a,texture,m,la,3)+vxpe_toon3d_triangle_gouraud_textured(t,c,b,texture,m,lb,6);
}
int vxpe_toon3d_billboard(VxpeToonTarget3D* t,const VxpeToonCamera3D* c,VxpeVec3D p,uint16_t ww,uint16_t wh,const VxpeSpriteA8* s,const VxpeToonMaterial3D* m,uint8_t light){
    if(!target(t)||!valid(c)||!m||!s||!s->pixels||!s->width||!s->height||!ww||!wh||(s->stride&&s->stride<s->width)||(s->alpha_stride&&s->alpha_stride<s->width))return 0;
    View v=view(c,p);if(v.z<c->near_z||v.z>c->far_z)return 0;Screen center=project(c,v);
    int w=bound((int64_t)ww*c->focal_px/v.z,1,32768),h=bound((int64_t)wh*c->focal_px/v.z,1,32768),left=(int)center.x-w/2,top=(int)center.y-h;
    int inkWidth=bound(m->outline_px,0,4),drawn=0;int factor=band(m,light),fog=fog_alpha(m,(int)v.z);
    for(int y=bound(top-inkWidth,0,t->height);y<bound(top+h+inkWidth,0,t->height);++y)
        for(int x=bound(left-inkWidth,0,t->width);x<bound(left+w+inkWidth,0,t->width);++x){
            int index=y*t->width+x;int testZ=biased_z((int)v.z,m->depth_bias);if(testZ>t->depth[index])continue;
            int sx=(int)((int64_t)(x-left)*s->width/w),sy=(int)((int64_t)(y-top)*s->height/h);
            // C++ division truncates negative coordinates towards zero: exclude exterior explicitly.
            bool inside=x>=left&&x<left+w&&y>=top&&y<top+h&&covered(s,sx,sy),outline=false;
            if(!inside&&inkWidth)for(int dy=-inkWidth;dy<=inkWidth&&!outline;++dy)for(int dx=-inkWidth;dx<=inkWidth;++dx){
                int nx=x+dx,ny=y+dy;if(nx>=left&&nx<left+w&&ny>=top&&ny<top+h&&covered(s,(int)((int64_t)(nx-left)*s->width/w),(int)((int64_t)(ny-top)*s->height/h))){outline=true;break;}}
            if(!inside&&!outline)continue;
            uint16_t color=outline?m->ink565:multiply(s->pixels[sy*(s->stride?s->stride:s->width)+sx],factor);
            t->pixels[index]=mix(color,m->fog565,fog);t->depth[index]=(uint16_t)testZ;++drawn;
        }return drawn;
}
