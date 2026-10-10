/* VXPGDX StrategyRPG - fixed-memory UI/gameplay primitives for 240x320 strategy RPGs. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "vxpgdx/Scene2DUI.h"
#include "vxpgdx/TextureAtlas.h"

namespace vxpe { namespace gdx { namespace strategy {

using scene2d::ui::BitmapFont5x7;
using scene2d::ui::uiFillRect;
using scene2d::ui::uiOverlayRect;

enum class Locale:uint8_t { Vietnamese=0, English, Chinese, Korean, Thai, Count };

struct LocalizedEntry {
    const char* key=nullptr;
    const char* text[(uint8_t)Locale::Count]{};
};

template <uint16_t MaxEntries=96>
class LocalizationTable {
public:
    bool add(const LocalizedEntry& entry){
        if(!entry.key||count_>=MaxEntries)return false;
        entries_[count_++]=entry;return true;
    }
    const char* get(const char* key,Locale locale,const char* fallback="")const{
        if(!key)return fallback?fallback:"";
        uint8_t li=(uint8_t)locale;
        if(li>=(uint8_t)Locale::Count)li=(uint8_t)Locale::English;
        for(uint16_t i=0;i<count_;++i){
            if(entries_[i].key&&strcmp(entries_[i].key,key)==0){
                const char* t=entries_[i].text[li];
                if(t&&*t)return t;
                t=entries_[i].text[(uint8_t)Locale::English];
                return (t&&*t)?t:(fallback?fallback:key);
            }
        }
        return fallback&&*fallback?fallback:key;
    }
    uint16_t size()const{return count_;}
    void clear(){count_=0;}
private:
    LocalizedEntry entries_[MaxEntries]{};
    uint16_t count_=0;
};


struct Utf8Glyph {
    uint32_t codepoint=0;
    uint16_t atlasRegion=0;
    int8_t xAdvance=6;
    int8_t xOffset=0;
    int8_t yOffset=0;
};

template <uint16_t MaxGlyphs=192,uint16_t AtlasRegions=256>
class Utf8GlyphFont {
public:
    bool add(uint32_t codepoint,uint16_t atlasRegion,int xAdvance=6,int xOffset=0,int yOffset=0){
        if(!codepoint||count_>=MaxGlyphs||atlasRegion>=AtlasRegions)return false;
        glyphs_[count_++]={codepoint,atlasRegion,(int8_t)xAdvance,(int8_t)xOffset,(int8_t)yOffset};
        return true;
    }
    void clear(){count_=0;}
    uint16_t size()const{return count_;}
    void setFallbackCodepoint(uint32_t cp){fallback_=cp;}

    const Utf8Glyph* find(uint32_t cp)const{
        for(uint16_t i=0;i<count_;++i)if(glyphs_[i].codepoint==cp)return &glyphs_[i];
        if(fallback_&&cp!=fallback_)for(uint16_t i=0;i<count_;++i)if(glyphs_[i].codepoint==fallback_)return &glyphs_[i];
        return nullptr;
    }

    static uint32_t decodeOne(const char*& p){
        const uint8_t* s=(const uint8_t*)p;
        if(!s||!*s)return 0;
        uint32_t cp=0;uint8_t n=0;
        if(s[0]<0x80){cp=s[0];n=1;}
        else if((s[0]&0xE0)==0xC0){cp=s[0]&0x1Fu;n=2;}
        else if((s[0]&0xF0)==0xE0){cp=s[0]&0x0Fu;n=3;}
        else if((s[0]&0xF8)==0xF0){cp=s[0]&0x07u;n=4;}
        else{++p;return 0xFFFDu;}
        for(uint8_t i=1;i<n;++i){
            if((s[i]&0xC0)!=0x80){++p;return 0xFFFDu;}
            cp=(cp<<6)|(s[i]&0x3Fu);
        }
        p+=(ptrdiff_t)n;
        return cp;
    }

    int textWidth(const char* text,uint8_t scale=1)const{
        if(!text)return 0;
        if(!scale)scale=1;
        int line=0,best=0;
        const char* p=text;
        while(*p){
            if(*p=='\n'){if(line>best)best=line;line=0;++p;continue;}
            uint32_t cp=decodeOne(p);const Utf8Glyph* g=find(cp);
            line+=(g?g->xAdvance:6)*scale;
        }
        return line>best?line:best;
    }

    void draw(SpriteBatch& batch,const TextureAtlas<AtlasRegions>& atlas,const char* text,
              int x,int y,uint16_t tint=0xFFFFu,uint8_t alpha=255,uint8_t scale=1)const{
        if(!text||!scale)return;
        int cx=x,cy=y;const char* p=text;
        while(*p){
            if(*p=='\n'){cx=x;cy+=10*scale;++p;continue;}
            uint32_t cp=decodeOne(p);const Utf8Glyph* g=find(cp);
            if(!g){cx+=6*scale;continue;}
            const AtlasRegion* ar=atlas.getRegion(g->atlasRegion);
            if(!ar){cx+=g->xAdvance*scale;continue;}
            int w=ar->region.getRegionWidth()*scale,h=ar->region.getRegionHeight()*scale;
            batch.draw(ar->region,cx+g->xOffset*scale,cy+g->yOffset*scale,w,h,tint,alpha,VXPE_BLEND_ALPHA);
            cx+=g->xAdvance*scale;
        }
    }

private:
    Utf8Glyph glyphs_[MaxGlyphs]{};
    uint16_t count_=0;
    uint32_t fallback_='?';
};

struct NinePatch {
    TextureRegion region{};
    uint8_t left=3,right=3,top=3,bottom=3;
    uint16_t tint565=0xFFFFu;
    uint8_t alpha=255;
    uint8_t blend=VXPE_BLEND_ALPHA;

    bool valid()const{
        return region.texture()&&region.getRegionWidth()>left+right&&region.getRegionHeight()>top+bottom;
    }

    void draw(SpriteBatch& batch,int x,int y,int w,int h,int16_t z=0)const{
        if(!valid()||w<=0||h<=0)return;
        const VxpeRectI r=region.rect();
        int dl=left,dr=right,dt=top,db=bottom;
        if(dl+dr>w){dl=w/2;dr=w-dl;}
        if(dt+db>h){dt=h/2;db=h-dt;}
        int smw=r.w-left-right,smh=r.h-top-bottom;
        int dmw=w-dl-dr,dmh=h-dt-db;
        const Texture& tex=*region.texture();

        TextureRegion tl(tex,r.x,r.y,left,top);
        TextureRegion tm(tex,r.x+left,r.y,smw,top);
        TextureRegion tr(tex,r.x+r.w-right,r.y,right,top);
        TextureRegion ml(tex,r.x,r.y+top,left,smh);
        TextureRegion mm(tex,r.x+left,r.y+top,smw,smh);
        TextureRegion mr(tex,r.x+r.w-right,r.y+top,right,smh);
        TextureRegion bl(tex,r.x,r.y+r.h-bottom,left,bottom);
        TextureRegion bm(tex,r.x+left,r.y+r.h-bottom,smw,bottom);
        TextureRegion br(tex,r.x+r.w-right,r.y+r.h-bottom,right,bottom);

        batch.draw(tl,x,y,dl,dt,tint565,alpha,blend,false,false,z);
        if(dmw>0)batch.draw(tm,x+dl,y,dmw,dt,tint565,alpha,blend,false,false,z);
        batch.draw(tr,x+w-dr,y,dr,dt,tint565,alpha,blend,false,false,z);
        if(dmh>0)batch.draw(ml,x,y+dt,dl,dmh,tint565,alpha,blend,false,false,z);
        if(dmw>0&&dmh>0)batch.draw(mm,x+dl,y+dt,dmw,dmh,tint565,alpha,blend,false,false,z);
        if(dmh>0)batch.draw(mr,x+w-dr,y+dt,dr,dmh,tint565,alpha,blend,false,false,z);
        batch.draw(bl,x,y+h-db,dl,db,tint565,alpha,blend,false,false,z);
        if(dmw>0)batch.draw(bm,x+dl,y+h-db,dmw,db,tint565,alpha,blend,false,false,z);
        batch.draw(br,x+w-dr,y+h-db,dr,db,tint565,alpha,blend,false,false,z);
    }
};

enum class ScreenTransition:uint8_t { None=0, Fade, SlideLeft, SlideRight };

struct ScreenState {
    uint16_t id=0;
    ScreenTransition transition=ScreenTransition::None;
    uint16_t transitionMs=0;
    uint16_t elapsedMs=0;
};

template <uint8_t MaxScreens=8>
class ScreenStack {
public:
    bool push(uint16_t id,ScreenTransition transition=ScreenTransition::None,uint16_t ms=0){
        if(count_>=MaxScreens)return false;
        states_[count_++]={id,transition,ms,0};return true;
    }
    bool replace(uint16_t id,ScreenTransition transition=ScreenTransition::None,uint16_t ms=0){
        if(!count_)return push(id,transition,ms);
        states_[count_-1]={id,transition,ms,0};return true;
    }
    bool pop(){if(count_<=1)return false;--count_;return true;}
    void clear(){count_=0;}
    uint8_t size()const{return count_;}
    ScreenState* current(){return count_?&states_[count_-1]:nullptr;}
    const ScreenState* current()const{return count_?&states_[count_-1]:nullptr;}
    const ScreenState* previous()const{return count_>1?&states_[count_-2]:nullptr;}
    void update(uint16_t dt){
        ScreenState* s=current();if(!s||!s->transitionMs)return;
        uint32_t e=(uint32_t)s->elapsedMs+dt;
        s->elapsedMs=(uint16_t)(e>s->transitionMs?s->transitionMs:e);
    }
    uint8_t transitionAlpha()const{
        const ScreenState* s=current();
        if(!s||!s->transitionMs||s->elapsedMs>=s->transitionMs)return 255;
        return (uint8_t)(((uint32_t)s->elapsedMs*255u)/s->transitionMs);
    }
private:
    ScreenState states_[MaxScreens]{};
    uint8_t count_=0;
};

enum GridCellFlags:uint8_t {
    GridNone=0,
    GridMove=1u<<0,
    GridAttack=1u<<1,
    GridSkill=1u<<2,
    GridOccupied=1u<<3
};

template <uint8_t MaxW=12,uint8_t MaxH=12>
class StrategyGrid {
public:
    StrategyGrid(){clear();}
    void configure(int x,int y,uint8_t cols,uint8_t rows,uint8_t cellW,uint8_t cellH){
        x_=x;y_=y;cols_=cols>MaxW?MaxW:cols;rows_=rows>MaxH?MaxH:rows;cellW_=cellW;cellH_=cellH;
        if(selX_>=cols_)selX_=cols_?cols_-1:0;
        if(selY_>=rows_)selY_=rows_?rows_-1:0;
    }
    void clear(){memset(flags_,0,sizeof(flags_));selX_=selY_=0;}
    bool inBounds(int x,int y)const{return x>=0&&y>=0&&x<cols_&&y<rows_;}
    void setFlag(uint8_t x,uint8_t y,uint8_t flag,bool on=true){
        if(!inBounds(x,y))return;
        uint8_t& f=flags_[y][x];
        if(on)f|=flag;
        else f&=(uint8_t)~flag;
    }
    uint8_t flags(uint8_t x,uint8_t y)const{return inBounds(x,y)?flags_[y][x]:0;}
    void setSelected(uint8_t x,uint8_t y){if(inBounds(x,y)){selX_=x;selY_=y;}}
    uint8_t selectedX()const{return selX_;} uint8_t selectedY()const{return selY_;}
    bool moveSelection(int dx,int dy){
        int nx=(int)selX_+dx,ny=(int)selY_+dy;if(!inBounds(nx,ny))return false;selX_=(uint8_t)nx;selY_=(uint8_t)ny;return true;
    }
    void drawOverlay(SpriteBatch& batch,bool gridLines=true)const{
        static const uint16_t moveC=0x07E0u,attackC=0xF800u,skillC=0x001Fu,gridC=0x7BEFu,selectC=0xFFE0u;
        for(uint8_t gy=0;gy<rows_;++gy)for(uint8_t gx=0;gx<cols_;++gx){
            int sx=x_+gx*cellW_,sy=y_+gy*cellH_;uint8_t f=flags_[gy][gx];
            if(f&GridMove)uiOverlayRect(batch,sx,sy,cellW_,cellH_,moveC,48);
            if(f&GridAttack)uiOverlayRect(batch,sx,sy,cellW_,cellH_,attackC,62);
            if(f&GridSkill)uiOverlayRect(batch,sx,sy,cellW_,cellH_,skillC,54);
            if(gridLines){
                uiFillRect(batch,sx,sy,cellW_,1,gridC);uiFillRect(batch,sx,sy,1,cellH_,gridC);
            }
        }
        int sx=x_+selX_*cellW_,sy=y_+selY_*cellH_;
        const int k=5;
        uiFillRect(batch,sx,sy,k,2,selectC);uiFillRect(batch,sx,sy,2,k,selectC);
        uiFillRect(batch,sx+cellW_-k,sy,k,2,selectC);uiFillRect(batch,sx+cellW_-2,sy,2,k,selectC);
        uiFillRect(batch,sx,sy+cellH_-2,k,2,selectC);uiFillRect(batch,sx,sy+cellH_-k,2,k,selectC);
        uiFillRect(batch,sx+cellW_-k,sy+cellH_-2,k,2,selectC);uiFillRect(batch,sx+cellW_-2,sy+cellH_-k,2,k,selectC);
    }
private:
    int16_t x_=0,y_=0;uint8_t cols_=0,rows_=0,cellW_=16,cellH_=16,selX_=0,selY_=0;
    uint8_t flags_[MaxH][MaxW]{};
};

enum class WorldNodeState:uint8_t { Locked=0, Open=1, Cleared=2 };

struct WorldNode {
    int16_t x=0,y=0;
    uint8_t stage=0;
    WorldNodeState state=WorldNodeState::Locked;
    uint8_t stars=0;
};

template <uint8_t MaxNodes=24>
class WorldMap {
public:
    bool add(const WorldNode& n){if(count_>=MaxNodes)return false;nodes_[count_++]=n;return true;}
    void clear(){count_=0;selected_=0;}
    uint8_t size()const{return count_;}
    const WorldNode* node(uint8_t i)const{return i<count_?&nodes_[i]:nullptr;}
    void select(uint8_t i){if(i<count_)selected_=i;}
    uint8_t selected()const{return selected_;}
    bool selectNextOpen(int dir){
        if(!count_||!dir)return false;
        int i=selected_;
        for(uint8_t n=0;n<count_;++n){i=(i+(dir>0?1:-1)+count_)%count_;if(nodes_[i].state!=WorldNodeState::Locked){selected_=(uint8_t)i;return true;}}
        return false;
    }
    void draw(SpriteBatch& batch)const{
        for(uint8_t i=1;i<count_;++i){
            int x0=nodes_[i-1].x,y0=nodes_[i-1].y,x1=nodes_[i].x,y1=nodes_[i].y;
            int steps=(x1>x0?x1-x0:x0-x1);int dy=(y1>y0?y1-y0:y0-y1);if(dy>steps)steps=dy;if(steps<1)steps=1;
            for(int s=0;s<=steps;s+=3){int x=x0+(x1-x0)*s/steps,y=y0+(y1-y0)*s/steps;uiFillRect(batch,x,y,2,2,0x8C51u);}
        }
        for(uint8_t i=0;i<count_;++i){
            const WorldNode& n=nodes_[i];uint16_t c=n.state==WorldNodeState::Locked?0x4208u:(n.state==WorldNodeState::Cleared?0x07E0u:0xFFE0u);
            uiFillRect(batch,n.x-4,n.y-4,9,9,0x0000u);uiFillRect(batch,n.x-3,n.y-3,7,7,c);
            if(i==selected_){uiFillRect(batch,n.x-6,n.y-6,13,1,0xFFFFu);uiFillRect(batch,n.x-6,n.y+6,13,1,0xFFFFu);}
            for(uint8_t s=0;s<n.stars&&s<3;++s)uiFillRect(batch,n.x-4+s*4,n.y+7,3,2,0xFFE0u);
        }
    }
private:
    WorldNode nodes_[MaxNodes]{};
    uint8_t count_=0,selected_=0;
};

struct RPGTheme {
    uint16_t panel=0x10A2u;
    uint16_t panelAlt=0x18E3u;
    uint16_t border=0xC618u;
    uint16_t gold=0xFD20u;
    uint16_t text=0xFFFFu;
    uint16_t muted=0xAD55u;
    uint16_t selected=0xFBE0u;
    uint16_t parchment=0xEED0u;
    uint16_t parchmentText=0x31A6u;
};

inline void drawSoftkeyBar(SpriteBatch& batch,const RPGTheme& theme,const char* left,const char* right){
    int w=batch.framebufferWidth(),h=batch.framebufferHeight(),y=h-22;
    uiFillRect(batch,0,y,w,22,theme.panel);uiFillRect(batch,0,y,w,2,theme.gold);
    if(left)BitmapFont5x7::drawScreen(batch,left,8,y+7,theme.text,1);
    if(right){int tw=BitmapFont5x7::textWidth(right,1);BitmapFont5x7::drawScreen(batch,right,w-tw-8,y+7,theme.text,1);}
}

inline void drawDialogueBox(SpriteBatch& batch,const RPGTheme& theme,int x,int y,int w,int h,const char* speaker,const char* text){
    uiFillRect(batch,x,y,w,h,theme.parchment);uiFillRect(batch,x,y,w,2,theme.gold);
    uiFillRect(batch,x,y,2,h,theme.border);uiFillRect(batch,x+w-2,y,2,h,theme.border);uiFillRect(batch,x,y+h-2,w,2,theme.border);
    if(speaker&&*speaker){uiFillRect(batch,x+8,y-8,64,10,theme.panel);BitmapFont5x7::drawScreen(batch,speaker,x+11,y-6,theme.gold,1);}
    if(text)BitmapFont5x7::drawScreen(batch,text,x+8,y+10,theme.parchmentText,1);
}

inline void drawResultPanel(SpriteBatch& batch,const RPGTheme& theme,int x,int y,int w,int h,uint16_t gold,uint16_t exp,uint8_t items){
    uiFillRect(batch,x,y,w,h,theme.panel);uiFillRect(batch,x,y,w,2,theme.gold);
    BitmapFont5x7::drawScreen(batch,"VICTORY",x+(w-BitmapFont5x7::textWidth("VICTORY",2))/2,y+8,theme.gold,2);
    char a[6]={'0',0,0,0,0,0},b[6]={'0',0,0,0,0,0},c[3]={'0',0,0};
    auto writeNum=[](char* out,uint16_t v){char t[6];int n=0;do{t[n++]=(char)('0'+v%10);v/=10;}while(v&&n<5);for(int i=0;i<n;++i)out[i]=t[n-1-i];out[n]=0;};
    writeNum(a,gold);writeNum(b,exp);writeNum(c,items);
    BitmapFont5x7::drawScreen(batch,"GOLD",x+14,y+38,theme.text,1);BitmapFont5x7::drawScreen(batch,a,x+w-42,y+38,theme.gold,1);
    BitmapFont5x7::drawScreen(batch,"EXP",x+14,y+52,theme.text,1);BitmapFont5x7::drawScreen(batch,b,x+w-42,y+52,0x07E0u,1);
    BitmapFont5x7::drawScreen(batch,"ITEM",x+14,y+66,theme.text,1);BitmapFont5x7::drawScreen(batch,c,x+w-42,y+66,theme.text,1);
}

}}} // namespace vxpe::gdx::strategy
