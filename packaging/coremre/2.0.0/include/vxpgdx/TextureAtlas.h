/*
 * VXPGDX TextureAtlas - fixed-capacity VXA8 atlas metadata.
 * One VXA8 texture page + named regions. No heap allocation.
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "vxpgdx/VxpGdx.h"

namespace vxpe { namespace gdx {

#ifndef VXPGDX_ATLAS_NAME_MAX
#define VXPGDX_ATLAS_NAME_MAX 24
#endif

struct AtlasRegion {
    char name[VXPGDX_ATLAS_NAME_MAX]{};
    TextureRegion region{};
    uint16_t index=0;
    int16_t originalWidth=0;
    int16_t originalHeight=0;
    int16_t offsetX=0;
    int16_t offsetY=0;
};

template <uint16_t MaxRegions=128>
class TextureAtlas {
public:
    TextureAtlas()=default;

    void setTexture(const Texture& texture){texture_=&texture;}
    const Texture* texture()const{return texture_;}

    void clear(){count_=0;texture_=nullptr;}

    bool addRegion(const char* name,int x,int y,int w,int h,
                   int originalW=0,int originalH=0,int offsetX=0,int offsetY=0){
        if(!texture_||!texture_->isValid()||!name||count_>=MaxRegions||w<=0||h<=0)return false;
        if(x<0||y<0||x+w>texture_->getWidth()||y+h>texture_->getHeight())return false;
        AtlasRegion& a=regions_[count_];
        size_t nameLen=strlen(name);
        if(nameLen>VXPGDX_ATLAS_NAME_MAX-1) nameLen=VXPGDX_ATLAS_NAME_MAX-1;
        memcpy(a.name,name,nameLen);
        a.name[nameLen]='\0';
        a.region=TextureRegion(*texture_,x,y,w,h);
        a.index=count_;
        a.originalWidth=(int16_t)(originalW>0?originalW:w);
        a.originalHeight=(int16_t)(originalH>0?originalH:h);
        a.offsetX=(int16_t)offsetX;a.offsetY=(int16_t)offsetY;
        ++count_;return true;
    }

    AtlasRegion* findRegion(const char* name){
        if(!name)return nullptr;
        for(uint16_t i=0;i<count_;++i)if(strcmp(regions_[i].name,name)==0)return &regions_[i];
        return nullptr;
    }
    const AtlasRegion* findRegion(const char* name)const{
        if(!name)return nullptr;
        for(uint16_t i=0;i<count_;++i)if(strcmp(regions_[i].name,name)==0)return &regions_[i];
        return nullptr;
    }
    AtlasRegion* getRegion(uint16_t index){return index<count_?&regions_[index]:nullptr;}
    const AtlasRegion* getRegion(uint16_t index)const{return index<count_?&regions_[index]:nullptr;}
    uint16_t size()const{return count_;}
    static constexpr uint16_t capacity(){return MaxRegions;}

    /*
     * VXAT v1 descriptor, little-endian:
     *   0..3  "VXAT"
     *   4     version=1
     *   5     name_bytes (1..24)
     *   6..7  region_count
     *   entries:
     *     name[name_bytes], x,y,w,h, original_w,original_h, offset_x,offset_y
     *     all numeric fields signed/unsigned 16-bit LE as appropriate.
     * Texture pixels live in a separate VXA8 resource.
     */
    bool loadVxat(const Texture& texture,const void* data,uint32_t size){
        clear();setTexture(texture);
        if(!data||size<8||!texture.isValid())return false;
        const uint8_t* p=(const uint8_t*)data;
        if(p[0]!='V'||p[1]!='X'||p[2]!='A'||p[3]!='T'||p[4]!=1)return false;
        uint8_t nameBytes=p[5];uint16_t n=(uint16_t)(p[6]|((uint16_t)p[7]<<8));
        if(nameBytes==0||nameBytes>VXPGDX_ATLAS_NAME_MAX||n>MaxRegions)return false;
        uint32_t entry=(uint32_t)nameBytes+16u;
        if(8u+(uint32_t)n*entry>size)return false;
        const uint8_t* q=p+8;
        for(uint16_t i=0;i<n;++i,q+=entry){
            char name[VXPGDX_ATLAS_NAME_MAX]{};
            uint8_t copy=nameBytes<VXPGDX_ATLAS_NAME_MAX-1?nameBytes:VXPGDX_ATLAS_NAME_MAX-1;
            memcpy(name,q,copy);name[copy]='\0';
            auto u16=[&](uint32_t o)->uint16_t{return (uint16_t)(q[o]|((uint16_t)q[o+1]<<8));};
            auto s16=[&](uint32_t o)->int16_t{return (int16_t)u16(o);};
            uint32_t b=nameBytes;
            int x=u16(b+0),y=u16(b+2),w=u16(b+4),h=u16(b+6);
            int ow=u16(b+8),oh=u16(b+10),ox=s16(b+12),oy=s16(b+14);
            if(!addRegion(name,x,y,w,h,ow,oh,ox,oy)){clear();return false;}
        }
        return true;
    }

private:
    const Texture* texture_=nullptr;
    AtlasRegion regions_[MaxRegions]{};
    uint16_t count_=0;
};

}} // namespace vxpe::gdx
