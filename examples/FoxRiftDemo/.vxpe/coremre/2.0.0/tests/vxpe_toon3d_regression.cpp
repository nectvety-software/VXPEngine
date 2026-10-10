#include "graphics/VxpToon3D.h"
#include "graphics/VxpArtStyle.h"
#include <cassert>
#include <cstring>
#include <cstdio>
#include <climits>

int main(){
    uint16_t pixels[64*48+2],depth[64*48+2];pixels[0]=pixels[64*48+1]=0x1234;depth[0]=depth[64*48+1]=0x5678;
    VxpeToonTarget3D target={pixels+1,depth+1,64,48};VxpeToonCamera3D camera;
    vxpe_toon3d_camera_init(&camera,64,48);camera.focal_px=32;camera.near_z=4;camera.far_z=300;
    VxpeToonMaterial3D red,blue;vxpe_toon3d_material_init(&red,0xf800);vxpe_toon3d_material_init(&blue,0x001f);red.fog_alpha=blue.fog_alpha=0;
    assert(vxpe_toon3d_shade(&red,0)!=vxpe_toon3d_shade(&red,100));assert(vxpe_toon3d_shade(&red,100)!=vxpe_toon3d_shade(&red,255));
    assert(vxpe_toon3d_shade(&red,0)==vxpe_toon3d_shade(&red,84));
    VxpeToonPoint3D p;assert(vxpe_toon3d_project(&camera,{0,0,32},&p)&&p.x==32&&p.y==24&&p.z==32);
    assert(!vxpe_toon3d_project(&camera,{0,0,-10},&p)&&!p.visible);
    camera.sin_yaw_q14=16384;camera.cos_yaw_q14=0;assert(vxpe_toon3d_project(&camera,{32,0,0},&p)&&p.x==32);camera.sin_yaw_q14=0;camera.cos_yaw_q14=16384;
    VxpeVec3D nearQuad[4]={{-16,16,32},{16,16,32},{16,-16,32},{-16,-16,32}};
    VxpeVec3D farQuad[4]={{-32,32,64},{32,32,64},{32,-32,64},{-32,-32,64}};
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_quad(&target,&camera,farQuad,&blue,255)>0);
    assert(vxpe_toon3d_quad(&target,&camera,nearQuad,&red,255)>0);assert(target.pixels[24*64+32]==0xf800);assert(target.depth[24*64+32]==32);
    // Shared diagonal is fill, never ink, and farther geometry cannot overwrite.
    assert(target.pixels[16*64+24]==0xf800);vxpe_toon3d_quad(&target,&camera,farQuad,&blue,255);assert(target.pixels[24*64+32]==0xf800);
    uint16_t reference[64*48];memcpy(reference,target.pixels,sizeof(reference));vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_quad(&target,&camera,nearQuad,&red,255);vxpe_toon3d_quad(&target,&camera,farQuad,&blue,255);assert(!memcmp(reference,target.pixels,sizeof(reference)));
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_triangle(&target,&camera,{-15,8,-8},{15,8,25},{0,-15,25},&red,190,7)>0);
    assert(vxpe_toon3d_triangle(&target,&camera,{0,0,-30},{0,8,-20},{8,0,-10},&red,255,7)==0);
    assert(vxpe_toon3d_triangle(&target,&camera,{0,0,400},{0,8,400},{8,0,400},&red,255,7)==0);
    assert(vxpe_toon3d_triangle(&target,&camera,{0,0,30},{0,0,30},{0,0,30},&red,255,7)==0);
    uint16_t spritePixels[4]={0x07e0,0x07e0,0x07e0,0x07e0};uint8_t alpha[4]={255,0,255,255};VxpeSpriteA8 sprite={spritePixels,alpha,2,2,2,2,0};
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_billboard(&target,&camera,{0,-8,32},16,16,&sprite,&red,255)>0);
    assert(target.pixels[20*64+28]==0x07e0);assert(target.pixels[20*64+36]==0); // Transparent corner.
    vxpe_toon3d_quad(&target,&camera,nearQuad,&blue,255);assert(vxpe_toon3d_billboard(&target,&camera,{0,-8,64},32,32,&sprite,&red,255)==0);
    VxpeArtStyleProfile style;vxpe_artstyle_init(&style,VXPE_ARTSTYLE_URBAN_TOON);assert(style.sprite_fx.outline_px==2&&style.trail_alpha&&style.fog_strength);
    assert(!strcmp(vxpe_artstyle_name(VXPE_ARTSTYLE_URBAN_TOON),"Urban Toon"));
    // Perspective-correct UV differs from affine UV at this analytically chosen pixel.
    uint16_t strip[8]={0x0800,0x1000,0x1800,0x2000,0x2800,0x3000,0x3800,0x4000};
    uint8_t stripAlpha[8]={255,255,255,255,255,255,255,255};VxpeSpriteA8 texture={strip,stripAlpha,8,1,8,8,0};
    VxpeToonMaterial3D white;vxpe_toon3d_material_init(&white,0xffff);white.fog_alpha=0;white.outline_px=0;
    VxpeToonVertex3D uv[3]={{{-16,16,32},0,0},{{32,32,64},7*256,0},{{-16,-16,32},0,0}};
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_triangle_textured(&target,&camera,uv,&texture,&white,255,0)>0);
    assert(target.pixels[12*64+32]==strip[2]);
    stripAlpha[2]=0;vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_triangle_textured(&target,&camera,uv,&texture,&white,255,0);
    assert(target.pixels[12*64+32]==0&&target.depth[12*64+32]==65535);
    // Texture attributes survive near-plane clipping and off-screen interpolation.
    uv[0].position.z=-8;assert(vxpe_toon3d_triangle_textured(&target,&camera,uv,&texture,&white,255,7)>0);
    // Extreme coordinates, narrow clips and off-screen sprites must stay within buffers.
    for(int i=0;i<80;++i){camera.near_z=(uint16_t)(1+i%10);red.outline_px=i%5;
        vxpe_toon3d_triangle(&target,&camera,{INT_MIN,INT_MAX,-20},{INT_MAX,INT_MIN,200},{0,0,30},&red,255,7);
        vxpe_toon3d_billboard(&target,&camera,{i*1000-40000,0,20},65535,65535,&sprite,&red,255);
        uv[0].u_q8=INT_MAX;uv[1].v_q8=INT_MIN;vxpe_toon3d_triangle_textured(&target,&camera,uv,&texture,&white,255,7);
    }
    assert(pixels[0]==0x1234&&pixels[64*48+1]==0x1234&&depth[0]==0x5678&&depth[64*48+1]==0x5678);
    camera.near_z=1;camera.far_z=65534;
    VxpeVec3D farLimit[4]={{-32767,32767,65534},{32767,32767,65534},{32767,-32767,65534},{-32767,-32767,65534}};
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_quad(&target,&camera,farLimit,&blue,255)>0);
    assert(target.depth[24*64+32]==65534);
    VxpeToonTransform3D transform;vxpe_toon3d_transform_init(&transform);
    transform.position={5,6,7};transform.scale_q8=512;
    VxpeVec3D moved=vxpe_toon3d_transform_point(&transform,{2,3,4});assert(moved.x==9&&moved.y==12&&moved.z==15);
    VxpeToonLight3D sun={0,0,-16384,40,200};
    assert(vxpe_toon3d_face_light({0,0,10},{0,8,10},{8,0,10},&sun)==240);
    assert(vxpe_toon3d_face_light({0,0,10},{8,0,10},{0,8,10},&sun)==40);
    vxpe_toon3d_camera_init(&camera,64,48);camera.focal_px=32;
    VxpeToonVertex3D meshVerts[3]={{{-8,-8,32},0,0},{{0,8,32},0,0},{{8,-8,32},0,0}};
    VxpeToonMeshFace3D meshFace={{0,1,2},0,0,255};VxpeToonMesh3D mesh={meshVerts,&meshFace,&blue,0,3,1,1};
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_mesh(&target,&camera,&mesh,0,0,VXPE_TOON_CULL_BACK)>0);
    assert(!vxpe_toon3d_mesh(&target,&camera,&mesh,0,0,VXPE_TOON_CULL_FRONT));
    VxpeToonPoint3D projected;
    assert(vxpe_toon3d_project(&camera,{0,0,32},&projected));int flatY=projected.y;
    camera.sin_pitch_q14=8192;camera.cos_pitch_q14=14189;
    assert(vxpe_toon3d_project(&camera,{0,0,32},&projected)&&projected.y<flatY);
    camera.near_z=0;assert(!vxpe_toon3d_triangle(&target,&camera,{0,0,8},{8,0,8},{0,8,8},&red,255,7));
    uint16_t tiny[4]={1,2,3,4},upscaled[18];upscaled[0]=upscaled[17]=0x1234;
    assert(vxpe2d_upscale2x565(upscaled+1,4,4,tiny,2,2));
    for(int yy=0;yy<4;++yy)for(int xx=0;xx<4;++xx)assert(upscaled[1+yy*4+xx]==tiny[(yy/2)*2+xx/2]);
    assert(!vxpe2d_upscale2x565(upscaled+1,3,4,tiny,2,2));assert(upscaled[0]==0x1234&&upscaled[17]==0x1234);
    uint16_t corners[9]={7,2,9,2,1,3,8,4,6},smooth[38];smooth[0]=smooth[37]=0x1234;
    assert(vxpe2d_scale2x565(smooth+1,6,6,corners,3,3));
    assert(smooth[1+2*6+2]==2&&smooth[1+2*6+3]==1&&smooth[1+3*6+2]==1&&smooth[1+3*6+3]==1);
    for(int yy=0;yy<6;++yy)for(int xx=0;xx<6;++xx){bool found=false;for(int i=0;i<9;++i)found|=smooth[1+yy*6+xx]==corners[i];assert(found);}
    assert(!vxpe2d_scale2x565(smooth+1,7,6,corners,3,3));assert(smooth[0]==0x1234&&smooth[37]==0x1234);
    uint16_t singleton=42,singleOut[4];assert(vxpe2d_scale2x565(singleOut,2,2,&singleton,1,1));for(int i=0;i<4;++i)assert(singleOut[i]==42);
    puts("PASS: toon bands, yaw, depth, quad seams, clipping, alpha, perspective UV, urban style and buffer guards");
}
