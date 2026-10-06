/*
 * VXPGDX TiledMap - fixed-memory atlas-backed map runtime.
 * v1/v2 remain supported; v3 adds the Tiled diagonal transform bit.
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "vxpgdx/TextureAtlas.h"

namespace vxpe { namespace gdx {

enum class TiledMapOrientation:uint8_t { Orthogonal=0, Isometric=1 };

enum TiledTileFlags:uint8_t {
    TileFlagNone=0,
    TileFlagSolid=1u<<0,
    TileFlagTrigger=1u<<1,
    TileFlagDamage=1u<<2,
    TileFlagWater=1u<<3,
    TileFlagLadder=1u<<4
};

struct TiledMapCell {
    uint16_t raw=0xFFFFu;
    static constexpr uint16_t Empty=0xFFFFu;
    static constexpr uint16_t FlipX=0x8000u;
    static constexpr uint16_t FlipY=0x4000u;
    static constexpr uint16_t FlipD=0x2000u;
    static constexpr uint16_t IdMaskLegacy=0x3FFFu;
    static constexpr uint16_t IdMaskV3=0x1FFFu;
    bool empty()const{return raw==Empty;}
    bool flipX()const{return !empty()&&(raw&FlipX)!=0;}
    bool flipY()const{return !empty()&&(raw&FlipY)!=0;}
    bool flipD(bool v3)const{return v3&&!empty()&&(raw&FlipD)!=0;}
    uint16_t tileId(bool v3)const{return raw&(v3?IdMaskV3:IdMaskLegacy);}
    uint16_t tileId()const{return raw&IdMaskLegacy;}
};

struct TiledMapTileset {
    uint16_t firstGid=0;
    uint16_t tileCount=0;
    uint16_t atlasFirstRegion=0;
    const uint8_t* tileFlags=nullptr;
    bool contains(uint16_t gid)const{
        return tileCount&&gid>=firstGid&&(uint32_t)gid<(uint32_t)firstGid+tileCount;
    }
    uint8_t flagsFor(uint16_t gid)const{
        return contains(gid)&&tileFlags?tileFlags[gid-firstGid]:0;
    }
};

struct TiledAnimationFrame {
    uint16_t gid=0;
    uint16_t durationMs=0;
};

struct TiledAnimatedTile {
    uint16_t baseGid=0;
    uint16_t frameCount=0;
    const TiledAnimationFrame* frames=nullptr;
};

struct TiledMapTileLayer {
    const uint16_t* cells=nullptr;
    uint16_t width=0,height=0;
    uint16_t tileWidth=16,tileHeight=16;
    int16_t offsetX=0,offsetY=0;
    int16_t z=0;
    uint16_t parallaxXQ8=256,parallaxYQ8=256;
    uint16_t tint565=0xFFFFu;
    uint8_t opacity=255;
    uint8_t visible=1;
    char name[16]{};

    TiledMapCell getCell(int x,int y)const{
        TiledMapCell c{};
        if(!cells||x<0||y<0||x>=width||y>=height){c.raw=TiledMapCell::Empty;return c;}
        c.raw=cells[y*width+x];return c;
    }
};

struct TiledMapObject {
    uint16_t id=0;
    uint16_t flags=0;
    int16_t x=0,y=0,width=0,height=0,rotation=0;
    char name[14]{};
    char type[12]{};
};

struct TiledMapObjectLayer {
    const TiledMapObject* objects=nullptr;
    uint16_t objectCount=0;
    int16_t z=0;
    uint8_t opacity=255;
    uint8_t visible=1;
    char name[16]{};

    const TiledMapObject* getObject(uint16_t i)const{return i<objectCount?&objects[i]:nullptr;}
    const TiledMapObject* findObject(const char* objectName)const{
        if(!objectName||!objects)return nullptr;
        for(uint16_t i=0;i<objectCount;++i)if(strcmp(objects[i].name,objectName)==0)return &objects[i];
        return nullptr;
    }
};

template <uint8_t MaxLayers=8,uint8_t MaxTilesets=4,uint8_t MaxObjectLayers=4,
          uint16_t MaxObjects=64,uint8_t MaxAnimations=32>
class TiledMap {
public:
    void clear(){
        layerCount_=tilesetCount_=objectLayerCount_=animationCount_=0;
        objectCount_=0;orientation_=TiledMapOrientation::Orthogonal;
        mapWidth_=mapHeight_=tileWidth_=tileHeight_=0;diagonalCells_=false;
    }

    bool addLayer(const TiledMapTileLayer& layer){
        if(layerCount_>=MaxLayers||!layer.cells||!layer.width||!layer.height)return false;
        if(layerCount_==0){mapWidth_=layer.width;mapHeight_=layer.height;tileWidth_=layer.tileWidth;tileHeight_=layer.tileHeight;}
        if(layer.width!=mapWidth_||layer.height!=mapHeight_||layer.tileWidth!=tileWidth_||layer.tileHeight!=tileHeight_)return false;
        layers_[layerCount_++]=layer;return true;
    }
    bool addTileset(const TiledMapTileset& ts){
        if(tilesetCount_>=MaxTilesets||!ts.tileCount)return false;
        tilesets_[tilesetCount_++]=ts;return true;
    }
    bool addObjectLayer(const TiledMapObjectLayer& layer){
        if(objectLayerCount_>=MaxObjectLayers)return false;
        objectLayers_[objectLayerCount_++]=layer;return true;
    }
    bool addAnimation(const TiledAnimatedTile& animation){
        if(animationCount_>=MaxAnimations||!animation.frames||!animation.frameCount)return false;
        animations_[animationCount_++]=animation;return true;
    }

    void setOrientation(TiledMapOrientation o){orientation_=o;}
    TiledMapOrientation orientation()const{return orientation_;}
    uint8_t getLayerCount()const{return layerCount_;}
    uint8_t getTilesetCount()const{return tilesetCount_;}
    uint8_t getObjectLayerCount()const{return objectLayerCount_;}
    uint8_t getAnimationCount()const{return animationCount_;}
    TiledMapTileLayer* getLayer(uint8_t i){return i<layerCount_?&layers_[i]:nullptr;}
    const TiledMapTileLayer* getLayer(uint8_t i)const{return i<layerCount_?&layers_[i]:nullptr;}
    const TiledMapTileset* getTileset(uint8_t i)const{return i<tilesetCount_?&tilesets_[i]:nullptr;}
    const TiledMapObjectLayer* getObjectLayer(uint8_t i)const{return i<objectLayerCount_?&objectLayers_[i]:nullptr;}
    uint16_t getWidth()const{return mapWidth_;}
    uint16_t getHeight()const{return mapHeight_;}
    uint16_t getTileWidth()const{return tileWidth_;}
    uint16_t getTileHeight()const{return tileHeight_;}
    bool usesDiagonalCells()const{return diagonalCells_;}
    void setDiagonalCells(bool enabled){diagonalCells_=enabled;}
    uint16_t cellTileId(const TiledMapCell& c)const{return c.tileId(diagonalCells_);}
    bool cellFlipD(const TiledMapCell& c)const{return c.flipD(diagonalCells_);}

    const TiledMapTileLayer* findLayer(const char* name)const{
        if(!name) return nullptr;
        for(uint8_t i=0;i<layerCount_;++i)
            if(strcmp(layers_[i].name,name)==0) return &layers_[i];
        return nullptr;
    }
    const TiledMapObjectLayer* findObjectLayer(const char* name)const{
        if(!name) return nullptr;
        for(uint8_t i=0;i<objectLayerCount_;++i)
            if(strcmp(objectLayers_[i].name,name)==0) return &objectLayers_[i];
        return nullptr;
    }

    uint16_t resolveAnimatedGid(uint16_t gid,uint32_t timeMs)const{
        for(uint8_t i=0;i<animationCount_;++i){
            const TiledAnimatedTile& a=animations_[i];if(a.baseGid!=gid||!a.frames||!a.frameCount)continue;
            uint32_t total=0;for(uint16_t f=0;f<a.frameCount;++f)total+=a.frames[f].durationMs;
            if(!total) return gid;
            uint32_t t=timeMs%total;
            for(uint16_t f=0;f<a.frameCount;++f){uint16_t d=a.frames[f].durationMs;if(t<d)return a.frames[f].gid;t-=d;}
        }
        return gid;
    }
    uint16_t resolveAtlasRegion(uint16_t gid,uint32_t timeMs=0)const{
        gid=resolveAnimatedGid(gid,timeMs);
        for(uint8_t i=0;i<tilesetCount_;++i)if(tilesets_[i].contains(gid))
            return (uint16_t)(tilesets_[i].atlasFirstRegion+(gid-tilesets_[i].firstGid));
        return gid; // v1/manual direct-index compatibility
    }
    uint8_t getTileFlags(uint16_t gid)const{
        for(uint8_t i=0;i<tilesetCount_;++i)if(tilesets_[i].contains(gid))return tilesets_[i].flagsFor(gid);
        return 0;
    }
    uint8_t getCellFlags(uint8_t layerIndex,int x,int y)const{
        const TiledMapTileLayer* l=getLayer(layerIndex);if(!l)return 0;
        TiledMapCell c=l->getCell(x,y);return c.empty()?0:getTileFlags(cellTileId(c));
    }
    bool cellHasFlags(uint8_t layerIndex,int x,int y,uint8_t mask)const{return (getCellFlags(layerIndex,x,y)&mask)!=0;}

    bool loadVxtm(const void* data,uint32_t size){
        clear();if(!data||size<16)return false;
        const uint8_t* p=(const uint8_t*)data;
        if(p[0]!='V'||p[1]!='X'||p[2]!='T'||p[3]!='M')return false;
        if(p[4]==1){diagonalCells_=false;return loadV1(p,size);}
        if(p[4]==2){diagonalCells_=false;return loadV2(p,size);}
        if(p[4]==3){diagonalCells_=true;return loadV2(p,size);}
        return false;
    }

private:
    TiledMapTileLayer layers_[MaxLayers]{};
    TiledMapTileset tilesets_[MaxTilesets]{};
    TiledMapObjectLayer objectLayers_[MaxObjectLayers]{};
    TiledMapObject objectPool_[MaxObjects]{};
    TiledAnimatedTile animations_[MaxAnimations]{};
    uint8_t layerCount_=0,tilesetCount_=0,objectLayerCount_=0,animationCount_=0;
    uint16_t objectCount_=0;
    TiledMapOrientation orientation_=TiledMapOrientation::Orthogonal;
    uint16_t mapWidth_=0,mapHeight_=0,tileWidth_=0,tileHeight_=0;
    bool diagonalCells_=false;

    static uint16_t U16(const uint8_t* p,uint32_t o){return (uint16_t)(p[o]|((uint16_t)p[o+1]<<8));}
    static int16_t S16(const uint8_t* p,uint32_t o){return (int16_t)U16(p,o);}

    bool loadV1(const uint8_t* p,uint32_t size){
        uint8_t orient=p[5],n=p[6];if(n>MaxLayers||orient>1)return false;
        uint16_t mw=U16(p,8),mh=U16(p,10),tw=U16(p,12),th=U16(p,14);
        if(!mw||!mh||!tw||!th)return false;
        uint64_t cellBytes=(uint64_t)mw*mh*2u,need=16u+(uint64_t)n*(24u+cellBytes);if(need>size)return false;
        orientation_=(TiledMapOrientation)orient;
        const uint8_t* q=p+16;
        for(uint8_t i=0;i<n;++i){
            TiledMapTileLayer l{};memcpy(l.name,q,12);l.name[15]='\0';l.visible=q[12];l.opacity=q[13];
            l.z=S16(q,14);l.offsetX=S16(q,16);l.offsetY=S16(q,18);
            l.width=mw;l.height=mh;l.tileWidth=tw;l.tileHeight=th;l.cells=(const uint16_t*)(q+24);
            if(!addLayer(l)){clear();return false;}q+=24+(uint32_t)cellBytes;
        }
        return true;
    }

    bool loadV2(const uint8_t* p,uint32_t size){
        if(size<24)return false;
        uint8_t orient=p[5],nl=p[6],nts=p[7],nol=p[16],na=p[17];
        uint16_t totalObjects=U16(p,18),mw=U16(p,8),mh=U16(p,10),tw=U16(p,12),th=U16(p,14);
        if(orient>1||nl>MaxLayers||nts>MaxTilesets||nol>MaxObjectLayers||na>MaxAnimations||totalObjects>MaxObjects||!mw||!mh||!tw||!th)return false;
        orientation_=(TiledMapOrientation)orient;mapWidth_=mw;mapHeight_=mh;tileWidth_=tw;tileHeight_=th;
        const uint8_t* q=p+24,*end=p+size;

        for(uint8_t i=0;i<nts;++i){
            if(q+8>end){clear();return false;}
            TiledMapTileset ts{};ts.firstGid=U16(q,0);ts.tileCount=U16(q,2);ts.atlasFirstRegion=U16(q,4);
            uint8_t hasFlags=q[6];q+=8;
            if(hasFlags){if(q+ts.tileCount>end){clear();return false;}ts.tileFlags=q;q+=ts.tileCount;if(((uintptr_t)q)&1u)++q;}
            if(!addTileset(ts)){clear();return false;}
        }

        uint64_t cellBytes=(uint64_t)mw*mh*2u;
        for(uint8_t i=0;i<nl;++i){
            if(q+28>end||q+28+cellBytes>end){clear();return false;}
            TiledMapTileLayer l{};memcpy(l.name,q,12);l.name[15]='\0';l.visible=q[12];l.opacity=q[13];
            l.z=S16(q,14);l.offsetX=S16(q,16);l.offsetY=S16(q,18);
            l.parallaxXQ8=U16(q,20);l.parallaxYQ8=U16(q,22);l.tint565=U16(q,24);
            l.width=mw;l.height=mh;l.tileWidth=tw;l.tileHeight=th;l.cells=(const uint16_t*)(q+28);
            if(!addLayer(l)){clear();return false;}q+=28+(uint32_t)cellBytes;
        }

        objectCount_=0;
        for(uint8_t i=0;i<nol;++i){
            if(q+20>end){clear();return false;}
            TiledMapObjectLayer ol{};memcpy(ol.name,q,12);ol.name[15]='\0';ol.visible=q[12];ol.opacity=q[13];
            ol.z=S16(q,14);uint16_t count=U16(q,16);q+=20;
            if((uint32_t)objectCount_+count>MaxObjects||q+(uint64_t)count*40u>end){clear();return false;}
            uint16_t start=objectCount_;
            for(uint16_t j=0;j<count;++j,q+=40){
                TiledMapObject& o=objectPool_[objectCount_++];o.id=U16(q,0);o.flags=U16(q,2);
                o.x=S16(q,4);o.y=S16(q,6);o.width=S16(q,8);o.height=S16(q,10);o.rotation=S16(q,12);
                memcpy(o.name,q+14,14);o.name[13]='\0';memcpy(o.type,q+28,12);o.type[11]='\0';
            }
            ol.objects=&objectPool_[start];ol.objectCount=count;if(!addObjectLayer(ol)){clear();return false;}
        }

        for(uint8_t i=0;i<na;++i){
            if(q+4>end){clear();return false;}
            TiledAnimatedTile a{};a.baseGid=U16(q,0);a.frameCount=U16(q,2);q+=4;
            if(!a.frameCount||q+(uint64_t)a.frameCount*4u>end){clear();return false;}
            a.frames=(const TiledAnimationFrame*)q;q+=(uint32_t)a.frameCount*4u;
            if(!addAnimation(a)){clear();return false;}
        }
        return true;
    }
};

template <uint16_t AtlasRegions=128>
class TiledMapRenderer {
public:
    void setView(const OrthographicCamera& camera){camera_=&camera;}
    void setMaxTilesPerFrame(uint16_t n){maxTiles_=n?n:1;}
    void setAnimationTime(uint32_t ms){animationTimeMs_=ms;}
    uint16_t getLastTileCount()const{return lastTiles_;}

    template <uint8_t L,uint8_t TS,uint8_t OL,uint16_t O,uint8_t A>
    void render(const TiledMap<L,TS,OL,O,A>& map,const TextureAtlas<AtlasRegions>& atlas,SpriteBatch& batch){
        lastTiles_=0;if(!camera_)return;
        batch.setCamera(nullptr);
        if(map.orientation()==TiledMapOrientation::Orthogonal)renderOrthogonal(map,atlas,batch);
        else renderIsometric(map,atlas,batch);
        batch.setCamera(camera_);
    }

private:
    const OrthographicCamera* camera_=nullptr;
    uint16_t maxTiles_=320,lastTiles_=0;
    uint32_t animationTimeMs_=0;

    static int floorDiv(int a,int b){int q=a/b,r=a%b;if(r&&((r<0)!=(b<0)))--q;return q;}
    static int cameraScaled(int32_t cameraQ8,uint16_t factorQ8){return (int)(((int64_t)cameraQ8*factorQ8)>>16);}

    template <typename MapT>
    void renderOrthogonal(const MapT& map,const TextureAtlas<AtlasRegions>& atlas,SpriteBatch& batch){
        for(uint8_t li=0;li<map.getLayerCount()&&lastTiles_<maxTiles_;++li){
            const TiledMapTileLayer* l=map.getLayer(li);if(!l||!l->visible||!l->cells)continue;
            int camx=cameraScaled(camera_->xQ8(),l->parallaxXQ8),camy=cameraScaled(camera_->yQ8(),l->parallaxYQ8);
            int left=camx,top=camy,right=left+camera_->viewportWidth(),bottom=top+camera_->viewportHeight();
            int x0=floorDiv(left-l->offsetX,l->tileWidth),y0=floorDiv(top-l->offsetY,l->tileHeight);
            int x1=floorDiv(right-l->offsetX+l->tileWidth-1,l->tileWidth),y1=floorDiv(bottom-l->offsetY+l->tileHeight-1,l->tileHeight);
            if(x0<0) x0=0;
            if(y0<0) y0=0;
            if(x1>=l->width) x1=l->width-1;
            if(y1>=l->height) y1=l->height-1;
            for(int y=y0;y<=y1&&lastTiles_<maxTiles_;++y)for(int x=x0;x<=x1&&lastTiles_<maxTiles_;++x){
                TiledMapCell c=l->getCell(x,y);if(c.empty())continue;
                uint16_t rid=map.resolveAtlasRegion(map.cellTileId(c),animationTimeMs_);
                const AtlasRegion* ar=atlas.getRegion(rid);if(!ar)continue;
                int sx=l->offsetX+x*l->tileWidth-camx,sy=l->offsetY+y*l->tileHeight-camy;
                batch.draw(ar->region,sx,sy,l->tileWidth,l->tileHeight,l->tint565,l->opacity,
                           VXPE_BLEND_ALPHA,c.flipX(),c.flipY(),l->z,map.cellFlipD(c));++lastTiles_;
            }
        }
    }

    template <typename MapT>
    void renderIsometric(const MapT& map,const TextureAtlas<AtlasRegions>& atlas,SpriteBatch& batch){
        for(uint8_t li=0;li<map.getLayerCount()&&lastTiles_<maxTiles_;++li){
            const TiledMapTileLayer* l=map.getLayer(li);if(!l||!l->visible||!l->cells)continue;
            int camx=cameraScaled(camera_->xQ8(),l->parallaxXQ8),camy=cameraScaled(camera_->yQ8(),l->parallaxYQ8);
            int hw=l->tileWidth/2,hh=l->tileHeight/2;if(hw<=0||hh<=0)continue;
            for(int d=0;d<(int)l->width+(int)l->height-1&&lastTiles_<maxTiles_;++d){
                int y0=d-((int)l->width-1);if(y0<0)y0=0;int y1=d;if(y1>=l->height)y1=l->height-1;
                for(int my=y0;my<=y1&&lastTiles_<maxTiles_;++my){
                    int mx=d-my;if(mx<0||mx>=l->width)continue;
                    int sx=l->offsetX+(mx-my)*hw-camx,sy=l->offsetY+(mx+my)*hh-camy;
                    if(sx+l->tileWidth<0||sy+l->tileHeight<0||sx>=camera_->viewportWidth()||sy>=camera_->viewportHeight())continue;
                    TiledMapCell c=l->getCell(mx,my);if(c.empty())continue;
                    uint16_t rid=map.resolveAtlasRegion(map.cellTileId(c),animationTimeMs_);
                    const AtlasRegion* ar=atlas.getRegion(rid);if(!ar)continue;
                    batch.draw(ar->region,sx,sy,l->tileWidth,l->tileHeight,l->tint565,l->opacity,
                               VXPE_BLEND_ALPHA,c.flipX(),c.flipY(),l->z,map.cellFlipD(c));++lastTiles_;
                }
            }
        }
    }
};

}} // namespace vxpe::gdx
