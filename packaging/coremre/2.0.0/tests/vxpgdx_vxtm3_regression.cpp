#include "vxpgdx/VxpGdx.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <vector>

using namespace vxpe::gdx;

namespace {

struct Bin {
    std::vector<uint8_t> v;
    void u8(uint8_t x){v.push_back(x);}
    void u16(uint16_t x){v.push_back((uint8_t)x);v.push_back((uint8_t)(x>>8));}
    void s16(int16_t x){u16((uint16_t)x);}
    void zero(size_t n){v.insert(v.end(),n,0);}
    void raw(const char* s,size_t n){v.insert(v.end(),s,s+n);}
    void name(const char* s,size_t n){
        size_t len=strlen(s);if(len>n)len=n;
        v.insert(v.end(),s,s+len);zero(n-len);
    }
};

std::vector<uint8_t> makeV1(){
    Bin b;b.raw("VXTM",4);b.u8(1);b.u8(0);b.u8(1);b.u8(0);
    b.u16(2);b.u16(1);b.u16(16);b.u16(16);
    b.name("legacy",12);b.u8(1);b.u8(255);b.s16(3);b.s16(4);b.s16(5);b.zero(4);
    b.u16(0x8002u);b.u16(0x4003u);
    return b.v;
}

std::vector<uint8_t> makeV2(){
    Bin b;b.raw("VXTM",4);b.u8(2);b.u8(0);b.u8(1);b.u8(1);
    b.u16(2);b.u16(2);b.u16(16);b.u16(16);
    b.u8(0);b.u8(0);b.u16(0);b.zero(4);
    b.u16(1);b.u16(4);b.u16(10);b.u8(1);b.u8(0);
    b.u8(TileFlagSolid);b.u8(TileFlagWater);b.u8(TileFlagDamage);b.u8(0);
    b.name("ground",12);b.u8(1);b.u8(240);b.s16(2);b.s16(6);b.s16(7);
    b.u16(128);b.u16(192);b.u16(0xFFFFu);b.zero(2);
    b.u16(0xC001u);b.u16(0x0002u);b.u16(0xFFFFu);b.u16(0x0003u);
    return b.v;
}

std::vector<uint8_t> makeV3(){
    Bin b;b.raw("VXTM",4);b.u8(3);b.u8(0);b.u8(1);b.u8(1);
    b.u16(4);b.u16(2);b.u16(16);b.u16(16);
    b.u8(1);b.u8(1);b.u16(1);b.zero(4);

    b.u16(1);b.u16(3);b.u16(5);b.u8(1);b.u8(0);
    b.u8(TileFlagSolid);b.u8(TileFlagWater);b.u8(TileFlagDamage);b.u8(0);

    b.name("diag",12);b.u8(1);b.u8(255);b.s16(0);b.s16(0);b.s16(0);
    b.u16(256);b.u16(256);b.u16(0xFFFFu);b.zero(2);
    const uint16_t cells[8]={
        0x0001u,0x8001u,0x4001u,0xC001u,
        0x2001u,0xA001u,0x6001u,0xE001u
    };
    for(uint16_t c:cells)b.u16(c);

    b.name("objects",12);b.u8(1);b.u8(255);b.s16(4);b.u16(1);b.zero(2);
    b.u16(7);b.u16(1);b.s16(48);b.s16(64);b.s16(16);b.s16(20);b.s16(0);
    b.name("spawn",14);b.name("PlayerSpawn",12);

    b.u16(2);b.u16(2);
    b.u16(2);b.u16(100);
    b.u16(3);b.u16(100);
    return b.v;
}

void testV1Compatibility(){
    auto bytes=makeV1();
    TiledMap<2,2,1,4,2> map;
    assert(map.loadVxtm(bytes.data(),(uint32_t)bytes.size()));
    assert(!map.usesDiagonalCells());
    assert(map.getWidth()==2&&map.getHeight()==1);
    const TiledMapTileLayer* layer=map.getLayer(0);assert(layer);
    TiledMapCell a=layer->getCell(0,0),c=layer->getCell(1,0);
    assert(map.cellTileId(a)==2&&a.flipX()&&!a.flipY()&&!map.cellFlipD(a));
    assert(map.cellTileId(c)==3&&!c.flipX()&&c.flipY()&&!map.cellFlipD(c));
    assert(layer->offsetX==4&&layer->offsetY==5&&layer->z==3);
}

void testV2Compatibility(){
    auto bytes=makeV2();
    TiledMap<2,2,1,4,2> map;
    assert(map.loadVxtm(bytes.data(),(uint32_t)bytes.size()));
    assert(!map.usesDiagonalCells());
    assert(map.getTilesetCount()==1&&map.getLayerCount()==1);
    const TiledMapTileLayer* layer=map.findLayer("ground");assert(layer);
    TiledMapCell c=layer->getCell(0,0);
    assert(c.flipX()&&c.flipY()&&!map.cellFlipD(c)&&map.cellTileId(c)==1);
    assert(map.resolveAtlasRegion(1)==10);
    assert((map.getTileFlags(1)&TileFlagSolid)!=0);
    assert((map.getTileFlags(2)&TileFlagWater)!=0);
    assert((map.getTileFlags(3)&TileFlagDamage)!=0);
    assert(layer->parallaxXQ8==128&&layer->parallaxYQ8==192);
}

void testV3FormatAndGameplay(){
    auto bytes=makeV3();
    TiledMap<2,2,2,8,4> map;
    assert(map.loadVxtm(bytes.data(),(uint32_t)bytes.size()));
    assert(map.usesDiagonalCells());
    assert(map.getWidth()==4&&map.getHeight()==2);
    assert(map.getTilesetCount()==1&&map.getObjectLayerCount()==1&&map.getAnimationCount()==1);

    const uint16_t rawExpected[8]={
        0x0001u,0x8001u,0x4001u,0xC001u,
        0x2001u,0xA001u,0x6001u,0xE001u
    };
    const TiledMapTileLayer* layer=map.findLayer("diag");assert(layer);
    for(int i=0;i<8;++i){
        TiledMapCell c=layer->getCell(i&3,i>>2);
        assert(c.raw==rawExpected[i]);
        assert(map.cellTileId(c)==1);
        assert(c.flipX()==((i&1)!=0));
        assert(c.flipY()==((i&2)!=0));
        assert(map.cellFlipD(c)==((i&4)!=0));
        assert((map.getCellFlags(0,i&3,i>>2)&TileFlagSolid)!=0);
    }

    assert(map.resolveAnimatedGid(2,50)==2);
    assert(map.resolveAnimatedGid(2,150)==3);
    assert(map.resolveAtlasRegion(2,150)==7);
    assert((map.getTileFlags(2)&TileFlagWater)!=0);

    const TiledMapObjectLayer* objects=map.findObjectLayer("objects");assert(objects);
    const TiledMapObject* spawn=objects->findObject("spawn");assert(spawn);
    assert(spawn->id==7&&spawn->x==48&&spawn->y==64);
    assert(strcmp(spawn->type,"PlayerSpawn")==0);
}

void expect4(const uint16_t* fb,uint16_t a,uint16_t b,uint16_t c,uint16_t d){
    assert(fb[0]==a&&fb[1]==b&&fb[2]==c&&fb[3]==d);
}

void testEightRenderTransforms(){
    const uint16_t A=0xF800u,B=0x07E0u,C=0x001Fu,D=0xFFFFu;
    const uint16_t pixels[4]={A,B,C,D};
    VxpeSpriteA8 sprite{};
    sprite.pixels=pixels;sprite.width=2;sprite.height=2;sprite.stride=2;sprite.opaque=1;
    VxpeBlit565 op{};op.src={0,0,2,2};op.dst_w=2;op.dst_h=2;
    op.tint565=0xFFFFu;op.alpha=255;op.blend=VXPE_BLEND_COPY;
    struct Case{uint8_t h,v,d;uint16_t e[4];};
    const Case cases[]={
        {0,0,0,{A,B,C,D}},
        {1,0,0,{B,A,D,C}},
        {0,1,0,{C,D,A,B}},
        {1,1,0,{D,C,B,A}},
        {0,0,1,{A,C,B,D}},
        {1,0,1,{C,A,D,B}},
        {0,1,1,{B,D,A,C}},
        {1,1,1,{D,B,C,A}}
    };
    uint16_t fb[4];
    for(const Case& q:cases){
        memset(fb,0,sizeof(fb));
        op.flip_x=q.h;op.flip_y=q.v;op.flip_d=q.d;
        vxpe2d_blit_a8(fb,2,2,&sprite,&op);
        expect4(fb,q.e[0],q.e[1],q.e[2],q.e[3]);
    }
}

void testMalformedInputs(){
    auto v3=makeV3();
    TiledMap<2,2,2,8,4> map;
    assert(!map.loadVxtm(v3.data(),12));
    std::vector<uint8_t> bad=v3;bad[4]=99;
    assert(!map.loadVxtm(bad.data(),(uint32_t)bad.size()));
    bad=v3;bad.resize(bad.size()-3);
    assert(!map.loadVxtm(bad.data(),(uint32_t)bad.size()));
    TiledMapCell empty;empty.raw=TiledMapCell::Empty;
    assert(empty.empty());
}

} // namespace

int main(){
    testV1Compatibility();
    testV2Compatibility();
    testV3FormatAndGameplay();
    testEightRenderTransforms();
    testMalformedInputs();
    puts("VXPGDX_VXTM3_REGRESSION_PASS");
    return 0;
}
