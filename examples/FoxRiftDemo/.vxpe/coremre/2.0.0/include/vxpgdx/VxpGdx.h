/*
 * VXPGDX - lightweight LibGDX-inspired facade for VXPEngine.
 * C++17, fixed-memory friendly, no mandatory heap allocation in render paths.
 */
#pragma once
#include <stdint.h>
#include <string.h>
#include "graphics/VxpRender2D.h"
#include "graphics/VxpSpriteFx.h"
#include "graphics/VxpVfx2D.h"
#include "graphics/VxpLight2D.h"
#include "graphics/VxpCinematic2D.h"

namespace vxpe { namespace gdx {

class Graphics {
public:
    void configure(uint16_t w,uint16_t h){w_=w;h_=h;}
    void beginFrame(uint16_t dt){
        dt_=dt;++frame_;accum_+=dt;++frames_;
        if(accum_>=1000u){fps_=(uint16_t)((uint32_t)frames_*1000u/accum_);accum_=0;frames_=0;}
    }
    uint16_t getWidth()const{return w_;}
    uint16_t getHeight()const{return h_;}
    uint16_t getDeltaTimeMs()const{return dt_;}
    float getDeltaTime()const{return (float)dt_/1000.0f;}
    uint16_t getFramesPerSecond()const{return fps_;}
    uint32_t getFrameId()const{return frame_;}
private:
    uint16_t w_=240,h_=320,dt_=33,fps_=0,frames_=0;
    uint32_t accum_=0,frame_=0;
};

class Input {
public:
    static constexpr uint8_t MaxKeys=32;
    void beginFrame(){
        memset(justPressed_,0,sizeof(justPressed_));
        memset(justReleased_,0,sizeof(justReleased_));
        touchJustPressed_=touchJustReleased_=false;
    }
    void setKey(uint8_t key,bool down){
        if(key>=MaxKeys)return;
        bool old=down_[key];down_[key]=down;
        if(!old&&down)justPressed_[key]=true;
        if(old&&!down)justReleased_[key]=true;
    }
    bool isKeyPressed(uint8_t key)const{return key<MaxKeys?down_[key]:false;}
    bool isKeyJustPressed(uint8_t key)const{return key<MaxKeys?justPressed_[key]:false;}
    bool isKeyJustReleased(uint8_t key)const{return key<MaxKeys?justReleased_[key]:false;}
    void setTouch(int16_t x,int16_t y,bool down){
        touchX_=x;touchY_=y;
        if(!touchDown_&&down)touchJustPressed_=true;
        if(touchDown_&&!down)touchJustReleased_=true;
        touchDown_=down;
    }
    bool isTouched()const{return touchDown_;}
    bool isTouchJustPressed()const{return touchJustPressed_;}
    bool isTouchJustReleased()const{return touchJustReleased_;}
    int16_t getX()const{return touchX_;}
    int16_t getY()const{return touchY_;}
private:
    bool down_[MaxKeys]{},justPressed_[MaxKeys]{},justReleased_[MaxKeys]{};
    bool touchDown_=false,touchJustPressed_=false,touchJustReleased_=false;
    int16_t touchX_=0,touchY_=0;
};

struct Context {
    Graphics* graphics=nullptr;
    Input* input=nullptr;
    VxpeLightmap2D* lightmap=nullptr;
    VxpeCinematic2D* cinematic=nullptr;
};

class Gdx {
public:
    static void bind(Context* c){ctx_=c;}
    static Context* context(){return ctx_;}
    static Graphics& graphics(){return *ctx_->graphics;}
    static Input& input(){return *ctx_->input;}
    static VxpeLightmap2D* lightmap(){return ctx_?ctx_->lightmap:nullptr;}
    static VxpeCinematic2D* cinematic(){return ctx_?ctx_->cinematic:nullptr;}
private:
    inline static Context* ctx_=nullptr;
};

class Texture {
public:
    bool loadVxa8(const void* data,uint32_t size){
        valid_=vxpe2d_sprite_a8_from_vxa8(data,size,&sprite_)!=0;return valid_;
    }
    bool isValid()const{return valid_;}
    void reset(){sprite_=VxpeSpriteA8{};valid_=false;}
    uint16_t getWidth()const{return sprite_.width;}
    uint16_t getHeight()const{return sprite_.height;}
    const VxpeSpriteA8* native()const{return valid_?&sprite_:nullptr;}
private:
    VxpeSpriteA8 sprite_{};
    bool valid_=false;
};

class TextureRegion {
public:
    TextureRegion()=default;
    explicit TextureRegion(const Texture& t):texture_(&t){
        rect_={0,0,(int16_t)t.getWidth(),(int16_t)t.getHeight()};
    }
    TextureRegion(const Texture& t,int x,int y,int w,int h):texture_(&t){
        rect_={(int16_t)x,(int16_t)y,(int16_t)w,(int16_t)h};
    }
    const Texture* texture()const{return texture_;}
    const VxpeRectI& rect()const{return rect_;}
    int getRegionWidth()const{return rect_.w;}
    int getRegionHeight()const{return rect_.h;}
private:
    const Texture* texture_=nullptr;
    VxpeRectI rect_{};
};

class OrthographicCamera {
public:
    OrthographicCamera()=default;
    OrthographicCamera(int w,int h):vw_((int16_t)w),vh_((int16_t)h){}
    void setToOrtho(int w,int h){vw_=(int16_t)w;vh_=(int16_t)h;xQ8_=yQ8_=0;}
    void setPosition(float x,float y){xQ8_=(int32_t)(x*256.0f);yQ8_=(int32_t)(y*256.0f);}
    void setPositionQ8(int32_t x,int32_t y){xQ8_=x;yQ8_=y;}
    void translate(float x,float y){xQ8_+=(int32_t)(x*256.0f);yQ8_+=(int32_t)(y*256.0f);}
    int screenX(int x)const{return x-(xQ8_>>8);}
    int screenY(int y)const{return y-(yQ8_>>8);}
    int worldX(int x)const{return x+(xQ8_>>8);}
    int worldY(int y)const{return y+(yQ8_>>8);}
    int32_t xQ8()const{return xQ8_;}
    int32_t yQ8()const{return yQ8_;}
    int viewportWidth()const{return vw_;}
    int viewportHeight()const{return vh_;}
private:
    int32_t xQ8_=0,yQ8_=0;
    int16_t vw_=240,vh_=320;
};

class SpriteBatch {
public:
    SpriteBatch(){vxpe2d_batch_init(&batch_);}
    void begin(uint16_t* fb,int w,int h){
        fb_=fb;fw_=w;fh_=h;drawing_=fb&&w>0&&h>0;vxpe2d_batch_init(&batch_);
        clipDepth_=1;clips_[0]={(int16_t)0,(int16_t)0,(int16_t)(w>0?w:0),(int16_t)(h>0?h:0)};
    }
    void setCamera(const OrthographicCamera* c){camera_=c;}
    bool draw(const Texture& t,int x,int y){
        TextureRegion r(t);return draw(r,x,y,r.getRegionWidth(),r.getRegionHeight());
    }
    bool draw(const TextureRegion& r,int x,int y,int w,int h,
              uint16_t tint=0xFFFFu,uint8_t alpha=255,uint8_t blend=VXPE_BLEND_ALPHA,
              bool flipX=false,bool flipY=false,int16_t z=0,bool flipD=false){
        if(!drawing_||!r.texture()||!r.texture()->isValid())return false;
        VxpeBlit565 op{};op.src=r.rect();
        op.dst_x=(int16_t)(camera_?camera_->screenX(x):x);
        op.dst_y=(int16_t)(camera_?camera_->screenY(y):y);
        op.dst_w=(uint16_t)(w>0?w:r.getRegionWidth());
        op.dst_h=(uint16_t)(h>0?h:r.getRegionHeight());
        op.tint565=tint;op.alpha=alpha;op.blend=blend;
        op.flip_x=flipX?1u:0u;op.flip_y=flipY?1u:0u;op.flip_d=flipD?1u:0u;
        applyClip(op);
        if(batch_.count>=VXPE_SPRITE_BATCH_MAX)flushNow();
        return vxpe2d_batch_push(&batch_,r.texture()->native(),&op,z,nullptr)!=0;
    }
    bool drawFx(const TextureRegion& r,int x,int y,int w,int h,
                const VxpeSpriteFxStyle& fx,int16_t z=0){
        if(!drawing_||!r.texture()||!r.texture()->isValid())return false;
        VxpeBlit565 op{};op.src=r.rect();
        op.dst_x=(int16_t)(camera_?camera_->screenX(x):x);
        op.dst_y=(int16_t)(camera_?camera_->screenY(y):y);
        op.dst_w=(uint16_t)w;op.dst_h=(uint16_t)h;
        op.tint565=0xFFFFu;op.alpha=255;op.blend=VXPE_BLEND_ALPHA;
        applyClip(op);
        if(batch_.count>=VXPE_SPRITE_BATCH_MAX)flushNow();
        return vxpe2d_batch_push(&batch_,r.texture()->native(),&op,z,&fx)!=0;
    }
    void flush(){flushNow();}
    void end(){
        if(!drawing_)return;
        flushNow();drawing_=false;
    }
    uint16_t* framebuffer()const{return fb_;}
    int framebufferWidth()const{return fw_;}
    int framebufferHeight()const{return fh_;}
    bool isDrawing()const{return drawing_;}
    int toScreenX(int worldX)const{return camera_?camera_->screenX(worldX):worldX;}
    int toScreenY(int worldY)const{return camera_?camera_->screenY(worldY):worldY;}

    bool pushClipRect(int worldX,int worldY,int w,int h){
        if(!drawing_||w<=0||h<=0||clipDepth_>=MaxClipDepth)return false;
        int x0=toScreenX(worldX),y0=toScreenY(worldY),x1=x0+w,y1=y0+h;
        const VxpeRectI& p=clips_[clipDepth_-1];
        int px1=p.x+p.w,py1=p.y+p.h;
        if(x0<p.x)x0=p.x;
        if(y0<p.y)y0=p.y;
        if(x1>px1)x1=px1;
        if(y1>py1)y1=py1;
        if(x1<x0)x1=x0;
        if(y1<y0)y1=y0;
        clips_[clipDepth_++]={(int16_t)x0,(int16_t)y0,(int16_t)(x1-x0),(int16_t)(y1-y0)};
        return x1>x0&&y1>y0;
    }
    void popClipRect(){if(clipDepth_>1)--clipDepth_;}
    VxpeRectI clipRect()const{return clipDepth_?clips_[clipDepth_-1]:VxpeRectI{0,0,0,0};}
    int clipX()const{return clipDepth_?clips_[clipDepth_-1].x:0;}
    int clipY()const{return clipDepth_?clips_[clipDepth_-1].y:0;}
    int clipWidth()const{return clipDepth_?clips_[clipDepth_-1].w:0;}
    int clipHeight()const{return clipDepth_?clips_[clipDepth_-1].h:0;}
    uint16_t getDroppedDraws()const{return batch_.dropped;}
private:
    static constexpr uint8_t MaxClipDepth=4;
    void applyClip(VxpeBlit565& op)const{
        if(!clipDepth_)return;
        const VxpeRectI& c=clips_[clipDepth_-1];
        op.clip_x=c.x;op.clip_y=c.y;op.clip_w=(uint16_t)c.w;op.clip_h=(uint16_t)c.h;
    }
    void flushNow(){
        if(drawing_&&batch_.count)vxpe2d_batch_flush(&batch_,fb_,fw_,fh_);
    }
    VxpeSpriteBatch batch_{};
    uint16_t* fb_=nullptr;int fw_=0,fh_=0;bool drawing_=false;
    const OrthographicCamera* camera_=nullptr;
    VxpeRectI clips_[MaxClipDepth]{};
    uint8_t clipDepth_=0;
};

class Animation {
public:
    Animation()=default;
    Animation(const Texture& t,const VxpeRectI* frames,uint16_t count,uint16_t frameMs,
              bool loop=true,bool pingPong=false):texture_(&t){
        clip_.frames=frames;clip_.frame_count=count;clip_.frame_ms=frameMs;
        clip_.durations_ms=nullptr;clip_.loop=loop?1u:0u;clip_.ping_pong=pingPong?1u:0u;
        vxpe2d_anim_reset(&state_);
    }
    void setDurations(const uint16_t* d){clip_.durations_ms=d;}
    void reset(){vxpe2d_anim_reset(&state_);}
    void update(uint16_t dt){vxpe2d_anim_update(&state_,&clip_,dt);}
    bool isFinished()const{return state_.finished!=0;}
    uint16_t getKeyFrameIndex()const{return state_.frame;}
    TextureRegion getKeyFrame()const{
        if(!texture_||!clip_.frames||!clip_.frame_count)return TextureRegion();
        VxpeRectI r=vxpe2d_anim_frame_rect(&state_,&clip_);
        return TextureRegion(*texture_,r.x,r.y,r.w,r.h);
    }
private:
    const Texture* texture_=nullptr;
    VxpeAnimClip clip_{};
    VxpeAnimState state_{};
};

/* -------------------------------------------------------------------------- */
/* Fixed-capacity AssetManager                                                  */
/* -------------------------------------------------------------------------- */

template <uint8_t MaxAssets=12,uint8_t MaxName=32>
class AssetManager {
public:
    using LoadFn=void* (*)(const char* name,uint32_t* outSize);
    using FreeFn=void (*)(void* data);

    void configure(LoadFn loadFn,FreeFn freeFn){load_=loadFn;free_=freeFn;}

    bool loadTexture(const char* name){
        if(!name||!load_)return false;
        int old=find(name);if(old>=0)return slots_[old].texture.isValid();
        int slot=freeSlot();if(slot<0)return false;
        uint32_t size=0;void* data=load_(name,&size);if(!data||!size)return false;
        if(!slots_[slot].texture.loadVxa8(data,size)){
            if(free_) free_(data);
            return false;
        }
        slots_[slot].data=data;slots_[slot].size=size;slots_[slot].used=true;
        size_t nameLen=strlen(name);
        if(nameLen>MaxName-1) nameLen=MaxName-1;
        memcpy(slots_[slot].name,name,nameLen);
        slots_[slot].name[nameLen]='\0';
        ++count_;return true;
    }

    Texture* getTexture(const char* name){
        int i=find(name);return i>=0?&slots_[i].texture:nullptr;
    }
    const Texture* getTexture(const char* name)const{
        int i=find(name);return i>=0?&slots_[i].texture:nullptr;
    }

    bool isLoaded(const char* name)const{return find(name)>=0;}

    void unload(const char* name){
        int i=find(name);if(i<0)return;release(i);
    }
    void clear(){
        for(uint8_t i=0;i<MaxAssets;++i)if(slots_[i].used)release(i);
    }
    uint8_t getLoadedCount()const{return count_;}
    static constexpr uint8_t getCapacity(){return MaxAssets;}

private:
    struct Slot{
        char name[MaxName]{};
        void* data=nullptr;uint32_t size=0;Texture texture{};bool used=false;
    };
    Slot slots_[MaxAssets]{};
    LoadFn load_=nullptr;FreeFn free_=nullptr;uint8_t count_=0;

    int find(const char* name)const{
        if(!name)return -1;
        for(uint8_t i=0;i<MaxAssets;++i)
            if(slots_[i].used&&strcmp(slots_[i].name,name)==0)return i;
        return -1;
    }
    int freeSlot()const{
        for(uint8_t i=0;i<MaxAssets;++i)if(!slots_[i].used)return i;
        return -1;
    }
    void release(int i){
        if(i<0||i>=MaxAssets||!slots_[i].used)return;
        if(free_&&slots_[i].data)free_(slots_[i].data);
        slots_[i].texture.reset();slots_[i].data=nullptr;slots_[i].size=0;
        slots_[i].name[0]='\0';slots_[i].used=false;if(count_)--count_;
    }
};

/* -------------------------------------------------------------------------- */
/* ShapeRenderer                                                               */
/* -------------------------------------------------------------------------- */

class ShapeRenderer {
public:
    void begin(uint16_t* fb,int w,int h){fb_=fb;fw_=w;fh_=h;drawing_=fb&&w>0&&h>0;}
    void end(){drawing_=false;}
    void setColor(uint16_t color565){color_=color565;}
    void setAlpha(uint8_t alpha){alpha_=alpha;}
    void setBlendMode(uint8_t blend){blend_=blend;}

    void filledRect(int x,int y,int w,int h){
        if(!drawing_)return;
        if(alpha_==255&&blend_==VXPE_BLEND_COPY)vxpe2d_fill_rect(fb_,fw_,fh_,x,y,w,h,color_);
        else vxpe2d_overlay_rect(fb_,fw_,fh_,x,y,w,h,color_,alpha_,blend_);
    }
    void rect(int x,int y,int w,int h,int thickness=1){
        if(!drawing_||w<=0||h<=0||thickness<=0)return;
        filledRect(x,y,w,thickness);filledRect(x,y+h-thickness,w,thickness);
        filledRect(x,y+thickness,thickness,h-thickness*2);
        filledRect(x+w-thickness,y+thickness,thickness,h-thickness*2);
    }
    void line(int x0,int y0,int x1,int y1,int width=1){
        if(!drawing_)return;
        VxpeBeamStyle s{};s.outer_color=color_;s.core_color=color_;s.hot_color=color_;
        s.outer_width=0;s.core_width=(uint8_t)(width>0?width:1);s.hot_width=0;
        s.alpha=alpha_;s.blend=blend_;
        vxpe2d_draw_beam(fb_,fw_,fh_,x0,y0,x1,y1,&s);
    }
    void ring(int cx,int cy,int radius,int thickness=1){
        if(!drawing_)return;
        vxpe2d_draw_ring(fb_,fw_,fh_,cx,cy,radius,thickness,color_,alpha_,blend_);
    }

private:
    uint16_t* fb_=nullptr;int fw_=0,fh_=0;bool drawing_=false;
    uint16_t color_=0xFFFFu;uint8_t alpha_=255;uint8_t blend_=VXPE_BLEND_ALPHA;
};

class Screen {
public:
    virtual ~Screen()=default;
    virtual void show(){}
    virtual void render(float delta)=0;
    virtual void resize(int w,int h){(void)w;(void)h;}
    virtual void pause(){}
    virtual void resume(){}
    virtual void hide(){}
    virtual void dispose(){}
};

class ApplicationAdapter {
public:
    virtual ~ApplicationAdapter()=default;
    virtual void create(){}
    virtual void render(){}
    virtual void resize(int w,int h){(void)w;(void)h;}
    virtual void pause(){}
    virtual void resume(){}
    virtual void dispose(){}
};

class Game:public ApplicationAdapter {
public:
    Screen* getScreen()const{return screen_;}
    void setScreen(Screen* next){
        if(screen_==next)return;
        if(screen_)screen_->hide();
        screen_=next;
        if(screen_){
            screen_->show();
            if(Gdx::context()&&Gdx::context()->graphics)
                screen_->resize(Gdx::graphics().getWidth(),Gdx::graphics().getHeight());
        }
    }
    void render()override{
        if(screen_&&Gdx::context()&&Gdx::context()->graphics)
            screen_->render(Gdx::graphics().getDeltaTime());
    }
    void resize(int w,int h)override{if(screen_)screen_->resize(w,h);}
    void pause()override{if(screen_)screen_->pause();}
    void resume()override{if(screen_)screen_->resume();}
    void dispose()override{
        if(screen_){screen_->hide();screen_->dispose();screen_=nullptr;}
    }
private:
    Screen* screen_=nullptr;
};

}} // namespace vxpe::gdx

/* Optional high-level VXPGDX modules. */
#include "vxpgdx/TextureAtlas.h"
#include "vxpgdx/TiledMap.h"
#include "vxpgdx/Scene2D.h"
#include "vxpgdx/Scene2DUI.h"
