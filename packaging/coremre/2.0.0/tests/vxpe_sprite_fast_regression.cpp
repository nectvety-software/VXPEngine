#include "graphics/VxpSpriteFx.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>

static uint16_t blend(uint16_t dst,uint16_t src,uint8_t a) {
    unsigned inv=255-a;
    return (uint16_t)((((((src>>11)&31)*a+((dst>>11)&31)*inv+127)/255)<<11) |
        (((((src>>5)&63)*a+((dst>>5)&63)*inv+127)/255)<<5) |
        (((src&31)*a+(dst&31)*inv+127)/255));
}
static void reference(uint16_t* fb,int w,int h,const VxpeSpriteA8& s,const VxpeBlit565& op) {
    for(int y=0;y<h;++y) for(int x=0;x<w;++x) {
        if(x<op.dst_x || y<op.dst_y || x>=op.dst_x+op.dst_w || y>=op.dst_y+op.dst_h) continue;
        if(op.clip_w && op.clip_h && (x<op.clip_x || y<op.clip_y ||
            x>=op.clip_x+op.clip_w || y>=op.clip_y+op.clip_h)) continue;
        int lx=x-op.dst_x,ly=y-op.dst_y;
        if(op.flip_x)lx=op.dst_w-1-lx;
        if(op.flip_y)ly=op.dst_h-1-ly;
        int sx=op.src.x+lx*op.src.w/op.dst_w,sy=op.src.y+ly*op.src.h/op.dst_h;
        uint8_t a=s.opaque||!s.alpha?255:s.alpha[sy*s.alpha_stride+sx];
        if(a)fb[y*w+x]=blend(fb[y*w+x],s.pixels[sy*s.stride+sx],a);
    }
}
int main() {
    uint16_t px[11*9]; uint8_t alpha[13*9];
    for(int i=0;i<99;++i)px[i]=(uint16_t)(i*977);
    for(int i=0;i<117;++i)alpha[i]=(uint8_t)((i%4)==0?0:((i%4)==1?255:i*37));
    VxpeSpriteA8 sprite={px,alpha,9,9,11,13,0};
    uint16_t actual[19*17+2],expected[19*17+2];
    const int widths[]={3,7,12,19}, heights[]={2,8,17};
    for(int opaque=0;opaque<2;++opaque) for(int flip=0;flip<4;++flip)
    for(int width: widths) for(int height: heights) for(int clip=0;clip<2;++clip) {
        sprite.opaque=(uint8_t)opaque;
        for(int i=0;i<19*17+2;++i)actual[i]=expected[i]=(uint16_t)(i*41+3);
        VxpeBlit565 op={};op.src={1,2,7,6};op.dst_x=-2;op.dst_y=-1;
        op.dst_w=(uint16_t)width;op.dst_h=(uint16_t)height;
        op.flip_x=(uint8_t)(flip&1);op.flip_y=(uint8_t)(flip>>1);
        op.alpha=255;op.tint565=0xFFFF;op.blend=VXPE_BLEND_ALPHA;
        if(clip) { op.clip_x=2;op.clip_y=3;op.clip_w=11;op.clip_h=9; }
        reference(expected+1,19,17,sprite,op);
        vxpe2d_blit_a8(actual+1,19,17,&sprite,&op);
        assert(!memcmp(actual,expected,sizeof(actual)));
    }
    // Unscaled opaque subrectangle uses clipped row memcpy, with padded stride.
    sprite.opaque=1;
    VxpeBlit565 op={};op.src={2,1,6,7};op.dst_x=-1;op.dst_y=12;
    op.dst_w=6;op.dst_h=7;op.tint565=0xFFFF;op.alpha=255;op.blend=VXPE_BLEND_COPY;
    memset(actual,0x23,sizeof(actual));memcpy(expected,actual,sizeof(actual));
    reference(expected+1,19,17,sprite,op);
    vxpe2d_blit_a8(actual+1,19,17,&sprite,&op);
    assert(!memcmp(actual,expected,sizeof(actual)));
    // Maximum source extent and negative destination must not overflow signed
    // multiplication in the column map, even though only 320 pixels are drawn.
    static uint16_t wide_pixels[65535];
    for(int i=0;i<65535;++i)wide_pixels[i]=(uint16_t)(i^0xABCD);
    VxpeSpriteA8 wide={wide_pixels,0,65535,1,65535,0,1};
    uint16_t row[322];memset(row,0x45,sizeof(row));
    VxpeBlit565 wide_op={};wide_op.dst_x=-32768;wide_op.dst_w=65534;wide_op.dst_h=1;
    wide_op.alpha=255;wide_op.tint565=0xFFFF;wide_op.blend=VXPE_BLEND_COPY;
    vxpe2d_blit_a8(row+1,320,1,&wide,&wide_op);
    assert(row[0]==0x4545 && row[321]==0x4545);
    for(int x=0;x<320;++x)assert(row[x+1]==wide_pixels[((uint64_t)(x+32768)*65535)/65534]);
    puts("PASS: fast A8 parity across alpha, padded strides, scale, flips, crop and clipping");
}
