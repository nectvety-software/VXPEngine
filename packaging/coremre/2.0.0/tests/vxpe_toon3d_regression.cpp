#include "graphics/VxpToon3D.h"
#include "graphics/VxpArtStyle.h"
#include <cassert>
#include <cstring>
#include <cstdio>
#include <climits>

int main(){
    uint16_t pixels[64*48+2],depth[64*48+2];pixels[0]=pixels[64*48+1]=0x1234;depth[0]=depth[64*48+1]=0x5678;
    VxpeToonTarget3D target={pixels+1,depth+1,64,48};VxpeToonCamera3D camera;
    for(int i=0;i<64*48;++i){pixels[i+1]=0x1357;depth[i+1]=0x2468;}
    vxpe_toon3d_clear_depth(&target);for(int i=0;i<64*48;++i)assert(depth[i+1]==65535&&pixels[i+1]==0x1357);
    assert(depth[0]==0x5678&&depth[64*48+1]==0x5678);
    vxpe_toon3d_camera_init(&camera,64,48);camera.focal_px=32;camera.near_z=4;camera.far_z=300;
    VxpeToonMaterial3D red,blue;vxpe_toon3d_material_init(&red,0xf800);vxpe_toon3d_material_init(&blue,0x001f);red.fog_alpha=blue.fog_alpha=0;
    assert(red.affine_depth==0);
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
    assert(vxpe_toon3d_triangle(&target,&camera,{10000,8,32},{10016,8,32},{10008,-8,32},&red,255,7)==0);
    assert(vxpe_toon3d_triangle(&target,&camera,{-10016,8,32},{-10000,8,32},{-10008,-8,32},&red,255,7)==0);
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
    // Low-power affine-depth mode preserves exact ordering for flat mall walls
    // and floors while removing reciprocal division from each covered pixel.
    camera.near_z=4;camera.far_z=300;red.affine_depth=blue.affine_depth=1;
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_quad(&target,&camera,farQuad,&blue,255)>0);
    assert(vxpe_toon3d_quad(&target,&camera,nearQuad,&red,255)>0);
    assert(target.pixels[24*64+32]==0xf800&&target.depth[24*64+32]==32);
    vxpe_toon3d_quad(&target,&camera,farQuad,&blue,255);assert(target.pixels[24*64+32]==0xf800);
    red.affine_depth=0;blue.affine_depth=0;
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
    // Gouraud input crosses cel bands over one face, exposing broad form highlights.
    VxpeToonMaterial3D smoothMat;vxpe_toon3d_material_init(&smoothMat,0xFFFF);smoothMat.fog_alpha=0;smoothMat.outline_px=0;
    uint8_t vertexLight[3]={0,255,255};camera.near_z=1;vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_triangle_gouraud(&target,&camera,{-20,-16,32},{20,-16,32},{0,16,32},&smoothMat,vertexLight,0)>0);
    int shadowPixels=0,highlightPixels=0;uint16_t shadowShade=vxpe_toon3d_shade(&smoothMat,0),highlightShade=vxpe_toon3d_shade(&smoothMat,255);
    for(int i=0;i<64*48;++i){shadowPixels+=target.pixels[i]==shadowShade;highlightPixels+=target.pixels[i]==highlightShade;}
    assert(shadowPixels>0&&highlightPixels>0);
    // Interpolated lighting remains valid when a triangle crosses the near plane.
    vxpe_toon3d_clear(&target,0);assert(vxpe_toon3d_triangle_gouraud(&target,&camera,{-24,-18,-8},{24,-18,32},{0,24,32},&smoothMat,vertexLight,0)>0);
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
    vxpe_toon3d_camera_init(&camera,64,48);camera.focal_px=32;vxpe_toon3d_clear(&target,0);
    VxpeVec3D glassQuad[4]={{-16,-12,32},{16,-12,32},{16,12,32},{-16,12,32}};
    white.outline_px=0;white.fog_alpha=0;white.dither_cutout=128;
    assert(vxpe_toon3d_quad(&target,&camera,glassQuad,&white,255)>0);
    int holes=0,solid=0;for(int yy=16;yy<32;++yy)for(int xx=24;xx<40;++xx){int index=yy*64+xx;
        if(target.depth[index]==65535){++holes;assert(target.pixels[index]==0);}else ++solid;}
    assert(holes==128&&solid==128);
    white.dither_cutout=255;vxpe_toon3d_clear(&target,0);assert(!vxpe_toon3d_quad(&target,&camera,glassQuad,&white,255));
    white.dither_cutout=0;assert(vxpe_toon3d_quad(&target,&camera,glassQuad,&white,255)>0);
    // Textured Gouraud: the flat textured path picks a single band for the whole
    // face, so a gradient that crosses the shadow and highlight thresholds must
    // produce strictly more distinct band colours than the flat path can.
    camera.near_z=1;camera.far_z=300;camera.focal_px=32;
    uint16_t ramp[8]={0xFFFF,0xFFFF,0xFFFF,0xFFFF,0xFFFF,0xFFFF,0xFFFF,0xFFFF};
    uint8_t rampAlpha[8]={255,255,255,255,255,255,255,255};
    VxpeSpriteA8 rampSprite={ramp,rampAlpha,8,1,8,8,0};
    VxpeToonVertex3D litUV[3]={{{-20,-14,32},0,0},{{20,-14,32},7*256,0},{{0,18,32},0,0}};
    uint8_t litRange[3]={0,255,255};
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_triangle_gouraud_textured(&target,&camera,litUV,&rampSprite,&white,litRange,0)>0);
    int gradColors=0;uint16_t gradSeen[8];int gradCount=0;
    for(int i=0;i<64*48;++i){uint16_t c=target.pixels[i];if(!c)continue;bool known=false;
        for(int k=0;k<gradCount;++k)known|=gradSeen[k]==c;
        if(!known&&gradCount<8){gradSeen[gradCount++]=c;}}
    gradColors=gradCount;
    // Flat lit textured at 0 and 255 each yield exactly one band colour.
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_triangle_textured(&target,&camera,litUV,&rampSprite,&white,0,0)>0);
    uint16_t flatShade=0;int flatColors=0;
    for(int i=0;i<64*48;++i)if(target.pixels[i]){flatShade=target.pixels[i];flatColors=1;break;}
    (void)flatShade;
    assert(gradColors>=2&&flatColors==1);

    // Textured Gouraud must stay perspective-correct: same UV as the flat path
    // at the face centre, where lighting is uniform and bands cannot differ.
    uint8_t sameLight[3]={200,200,200};
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_triangle_gouraud_textured(&target,&camera,litUV,&rampSprite,&white,sameLight,0)>0);
    uint16_t uniformCenter=target.pixels[24*64+32];
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_triangle_textured(&target,&camera,litUV,&rampSprite,&white,200,0)>0);
    assert(target.pixels[24*64+32]==uniformCenter);

    // The quad wrapper must match two triangles drawn by hand.
    VxpeToonVertex3D quadUV[4]={{{-20,-14,32},0,0},{{20,-14,32},7*256,0},{{20,18,32},7*256,7*256},{{-20,18,32},0,7*256}};
    uint8_t quadLight[4]={0,255,255,255},quadLightA[3]={0,255,255},quadLightB[3]={0,255,255};
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_quad_gouraud_textured(&target,&camera,quadUV,&rampSprite,&white,quadLight)>0);
    uint16_t quadImage[64*48];memcpy(quadImage,target.pixels,sizeof(quadImage));
    vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_triangle_gouraud_textured(&target,&camera,quadUV,&rampSprite,&white,quadLightA,3);
    VxpeToonVertex3D second[3]={quadUV[0],quadUV[2],quadUV[3]};
    vxpe_toon3d_triangle_gouraud_textured(&target,&camera,second,&rampSprite,&white,quadLightB,6);
    assert(!memcmp(quadImage,target.pixels,sizeof(quadImage)));

    // Guards: null inputs and disabled materials must be rejected, not crash.
    assert(!vxpe_toon3d_triangle_gouraud_textured(&target,&camera,litUV,&rampSprite,&white,0,0));
    assert(!vxpe_toon3d_triangle_gouraud_textured(&target,&camera,litUV,0,&white,litRange,0));
    assert(!vxpe_toon3d_quad_gouraud_textured(&target,&camera,quadUV,&rampSprite,&white,0));
    /* Top-left fill rule: two triangles that share a diagonal must tile it exactly
     * once, so the drawn counts add up to the covered pixels and swapping their
     * submission order cannot change a single pixel. Without the rule the shared
     * edge is covered twice and the winner is whichever triangle came last. */
    vxpe_toon3d_camera_init(&camera,64,48);camera.focal_px=32;camera.near_z=4;camera.far_z=300;
    VxpeVec3D tiled[4]={{-12,12,32},{12,12,32},{12,-12,32},{-12,-12,32}};
    VxpeToonMaterial3D left,right;vxpe_toon3d_material_init(&left,0xf800);vxpe_toon3d_material_init(&right,0x001f);
    left.fog_alpha=right.fog_alpha=0;left.outline_px=right.outline_px=0;
    vxpe_toon3d_clear(&target,0);
    int drawnA=vxpe_toon3d_triangle(&target,&camera,tiled[0],tiled[1],tiled[2],&left,255,0);
    int drawnB=vxpe_toon3d_triangle(&target,&camera,tiled[0],tiled[2],tiled[3],&right,255,3);
    int covered=0;for(int i=0;i<64*48;++i)covered+=target.pixels[i]!=0;
    assert(drawnA>0&&drawnB>0&&drawnA+drawnB==covered);
    uint16_t tiledImage[64*48];memcpy(tiledImage,target.pixels,sizeof(tiledImage));
    vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_triangle(&target,&camera,tiled[0],tiled[2],tiled[3],&right,255,3);
    vxpe_toon3d_triangle(&target,&camera,tiled[0],tiled[1],tiled[2],&left,255,0);
    assert(!memcmp(tiledImage,target.pixels,sizeof(tiledImage)));
    /* depth_bias is polygon offset: a coincident face pulled towards the camera
     * must win whoever was submitted first, so coplanar decals stop flickering. */
    assert(left.depth_bias==0);
    VxpeVec3D coplanar[4]={{-8,8,32},{8,8,32},{8,-8,32},{-8,-8,32}};
    VxpeToonMaterial3D under,decal;vxpe_toon3d_material_init(&under,0xf800);vxpe_toon3d_material_init(&decal,0x001f);
    under.fog_alpha=decal.fog_alpha=0;under.outline_px=decal.outline_px=0;decal.depth_bias=-3;
    vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_quad(&target,&camera,coplanar,&under,255);
    vxpe_toon3d_quad(&target,&camera,coplanar,&decal,255);
    assert(target.pixels[24*64+32]==0x001f);
    vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_quad(&target,&camera,coplanar,&decal,255);
    vxpe_toon3d_quad(&target,&camera,coplanar,&under,255);
    assert(target.pixels[24*64+32]==0x001f);
    /* Dithered gradient: the plain fill repeats a row whenever the destination
     * channel has not stepped a whole 565 level yet, which a tall sky shows as
     * stripes. The dithered version must break those constant rows while keeping
     * the endpoints and staying inside the buffer. */
    for(int i=0;i<64*48;++i)pixels[i+1]=0x1357;
    vxpe2d_gradient_vertical(pixels+1,64,48,0,0,64,64,0x0000,0x001F);
    int plainFlat=0;for(int y=1;y<48;++y){int same=1;for(int x=0;x<64;++x)same&=pixels[1+y*64+x]==pixels[1+(y-1)*64+x];plainFlat+=same;}
    uint16_t plainTop=pixels[1],plainBottom=pixels[1+47*64];
    for(int i=0;i<64*48;++i)pixels[i+1]=0x1357;
    vxpe2d_gradient_vertical_dithered(pixels+1,64,48,0,0,64,64,0x0000,0x001F);
    int ditheredFlat=0;for(int y=1;y<48;++y){int same=1;for(int x=0;x<64;++x)same&=pixels[1+y*64+x]==pixels[1+(y-1)*64+x];ditheredFlat+=same;}
    const int topDelta=(int)(pixels[1]&31u)-(int)(plainTop&31u),bottomDelta=(int)(pixels[1+47*64]&31u)-(int)(plainBottom&31u);
    assert(topDelta>=-1&&topDelta<=1&&bottomDelta>=-1&&bottomDelta<=1);
    assert(plainFlat>8&&ditheredFlat<plainFlat/2);
    printf("dithered gradient: rows identical to the row above  plain=%d dithered=%d\n",plainFlat,ditheredFlat);
    assert(pixels[0]==0x1234&&pixels[64*48+1]==0x1234);
    /* Untextured Gouraud quad wrapper must match two triangles drawn by hand and
     * must cross cel bands where a flat quad can only show one. */
    vxpe_toon3d_camera_init(&camera,64,48);camera.focal_px=32;camera.near_z=1;camera.far_z=300;
    VxpeVec3D litQuad[4]={{-18,-14,32},{18,-14,32},{18,14,32},{-18,14,32}};
    uint8_t litCorners[4]={0,255,255,0},litFirst[3]={0,255,255},litSecond[3]={0,255,0};
    vxpe_toon3d_clear(&target,0);
    assert(vxpe_toon3d_quad_gouraud(&target,&camera,litQuad,&smoothMat,litCorners)>0);
    uint16_t litImage[64*48];memcpy(litImage,target.pixels,sizeof(litImage));
    vxpe_toon3d_clear(&target,0);
    vxpe_toon3d_triangle_gouraud(&target,&camera,litQuad[0],litQuad[1],litQuad[2],&smoothMat,litFirst,3);
    vxpe_toon3d_triangle_gouraud(&target,&camera,litQuad[0],litQuad[2],litQuad[3],&smoothMat,litSecond,6);
    assert(!memcmp(litImage,target.pixels,sizeof(litImage)));
    int litShadow=0,litHighlight=0;
    for(int i=0;i<64*48;++i){litShadow+=litImage[i]==vxpe_toon3d_shade(&smoothMat,0);litHighlight+=litImage[i]==vxpe_toon3d_shade(&smoothMat,255);}
    assert(litShadow>0&&litHighlight>0);
    assert(!vxpe_toon3d_quad_gouraud(&target,&camera,litQuad,&smoothMat,0));
    assert(!vxpe_toon3d_quad_gouraud(&target,&camera,0,&smoothMat,litCorners));
    puts("PASS: toon bands, yaw, depth, depth-only clear, frustum reject, quad seams, fill rule, depth bias, dithered gradient, gouraud quad, clipping, alpha, perspective UV, textured gouraud, urban style and buffer guards");
}
