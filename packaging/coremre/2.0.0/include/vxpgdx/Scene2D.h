/*
 * VXPGDX Scene2D - lightweight Stage/Actor graph for MRE/VXP.
 * Non-owning child pointers, fixed-capacity groups, no heap allocation required.
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include "vxpgdx/VxpGdx.h"

namespace vxpe { namespace gdx { namespace scene2d {

enum class Touchable:uint8_t { Enabled=0, Disabled=1, ChildrenOnly=2 };

class Actor;

class InputListener {
public:
    virtual ~InputListener()=default;
    virtual bool touchDown(Actor& actor,float x,float y,uint8_t pointer,uint8_t button){
        (void)actor;(void)x;(void)y;(void)pointer;(void)button;return false;
    }
    virtual void touchUp(Actor& actor,float x,float y,uint8_t pointer,uint8_t button){
        (void)actor;(void)x;(void)y;(void)pointer;(void)button;
    }
    virtual void touchDragged(Actor& actor,float x,float y,uint8_t pointer){
        (void)actor;(void)x;(void)y;(void)pointer;
    }
    virtual bool keyDown(Actor& actor,uint8_t key){(void)actor;(void)key;return false;}
    virtual bool keyUp(Actor& actor,uint8_t key){(void)actor;(void)key;return false;}
};

class Actor {
public:
    virtual ~Actor()=default;

    virtual void act(float delta){(void)delta;}
    virtual void draw(SpriteBatch& batch,uint8_t parentAlpha){(void)batch;(void)parentAlpha;}

    virtual Actor* hit(float stageX,float stageY,bool touchable=true){
        if(!visible_)return nullptr;
        if(touchable&&touchable_!=Touchable::Enabled)return nullptr;
        return contains(stageX,stageY)?this:nullptr;
    }

    void setBounds(float x,float y,float w,float h){x_=x;y_=y;width_=w;height_=h;}
    void setPosition(float x,float y){x_=x;y_=y;}
    void moveBy(float dx,float dy){x_+=dx;y_+=dy;}
    void setSize(float w,float h){width_=w;height_=h;}
    void setVisible(bool v){visible_=v;}
    bool isVisible()const{return visible_;}
    void setTouchable(Touchable t){touchable_=t;}
    Touchable getTouchable()const{return touchable_;}
    void setColorAlpha(uint8_t a){alpha_=a;}
    uint8_t getColorAlpha()const{return alpha_;}
    void setName(const char* n){name_=n;}
    const char* getName()const{return name_;}
    float getX()const{return x_;}
    float getY()const{return y_;}
    float getWidth()const{return width_;}
    float getHeight()const{return height_;}

    float getStageX()const{return parent_?parent_->getStageX()+x_:x_;}
    float getStageY()const{return parent_?parent_->getStageY()+y_:y_;}
    float stageToLocalX(float sx)const{return sx-getStageX();}
    float stageToLocalY(float sy)const{return sy-getStageY();}

    bool contains(float sx,float sy)const{
        float x=getStageX(),y=getStageY();
        return sx>=x&&sy>=y&&sx<x+width_&&sy<y+height_;
    }

    void setInputListener(InputListener* listener){listener_=listener;}
    InputListener* getInputListener()const{return listener_;}
    Actor* getParent()const{return parent_;}

    bool fireTouchDown(float sx,float sy,uint8_t pointer,uint8_t button){
        if(!listener_)return false;
        return listener_->touchDown(*this,stageToLocalX(sx),stageToLocalY(sy),pointer,button);
    }
    void fireTouchUp(float sx,float sy,uint8_t pointer,uint8_t button){
        if(listener_)listener_->touchUp(*this,stageToLocalX(sx),stageToLocalY(sy),pointer,button);
    }
    void fireTouchDragged(float sx,float sy,uint8_t pointer){
        if(listener_)listener_->touchDragged(*this,stageToLocalX(sx),stageToLocalY(sy),pointer);
    }
    bool fireKeyDown(uint8_t key){return listener_?listener_->keyDown(*this,key):false;}
    bool fireKeyUp(uint8_t key){return listener_?listener_->keyUp(*this,key):false;}

protected:
    friend class Group;
    Actor* parent_=nullptr;
    float x_=0,y_=0,width_=0,height_=0;
    uint8_t alpha_=255;
    bool visible_=true;
    Touchable touchable_=Touchable::Enabled;
    const char* name_=nullptr;
    InputListener* listener_=nullptr;
};

#ifndef VXPGDX_SCENE2D_MAX_CHILDREN
#define VXPGDX_SCENE2D_MAX_CHILDREN 24
#endif

class Group:public Actor {
public:
    static constexpr uint8_t MaxChildren=VXPGDX_SCENE2D_MAX_CHILDREN;

    bool addActor(Actor& actor){
        if(count_>=MaxChildren||actor.parent_==this)return false;
        if(actor.parent_)return false;
        children_[count_++]=&actor;actor.parent_=this;return true;
    }
    bool removeActor(Actor& actor){
        for(uint8_t i=0;i<count_;++i)if(children_[i]==&actor){
            for(uint8_t j=i+1;j<count_;++j)children_[j-1]=children_[j];
            children_[--count_]=nullptr;actor.parent_=nullptr;return true;
        }
        return false;
    }
    void clearChildren(){
        for(uint8_t i=0;i<count_;++i)if(children_[i])children_[i]->parent_=nullptr;
        count_=0;
    }
    uint8_t getChildrenCount()const{return count_;}
    Actor* getChild(uint8_t i)const{return i<count_?children_[i]:nullptr;}

    bool setZIndex(Actor& actor,uint8_t index){
        if(index>=count_)index=(uint8_t)(count_-1);
        int old=-1;for(uint8_t i=0;i<count_;++i)if(children_[i]==&actor){old=i;break;}
        if(old<0||old==index)return old>=0;
        Actor* p=children_[old];
        if(old<index)for(int i=old;i<index;++i)children_[i]=children_[i+1];
        else for(int i=old;i>index;--i)children_[i]=children_[i-1];
        children_[index]=p;return true;
    }
    bool toFront(Actor& actor){return count_?setZIndex(actor,(uint8_t)(count_-1)):false;}

    void act(float delta)override{
        Actor::act(delta);
        for(uint8_t i=0;i<count_;++i)if(children_[i]&&children_[i]->isVisible())children_[i]->act(delta);
    }
    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        if(!visible_)return;
        uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
        for(uint8_t i=0;i<count_;++i)if(children_[i]&&children_[i]->isVisible())children_[i]->draw(batch,a);
    }
    Actor* hit(float sx,float sy,bool touchable=true)override{
        if(!visible_||touchable_==Touchable::Disabled)return nullptr;
        for(int i=(int)count_-1;i>=0;--i){
            Actor* child=children_[i];if(!child)continue;
            Actor* h=child->hit(sx,sy,touchable);if(h)return h;
        }
        if(touchable_==Touchable::ChildrenOnly)return nullptr;
        return Actor::hit(sx,sy,touchable);
    }

private:
    Actor* children_[MaxChildren]{};
    uint8_t count_=0;
};

class Image:public Actor {
public:
    Image()=default;
    explicit Image(const TextureRegion& region):region_(region){
        width_=(float)region.getRegionWidth();height_=(float)region.getRegionHeight();
    }
    void setRegion(const TextureRegion& r){region_=r;if(width_<=0)width_=(float)r.getRegionWidth();if(height_<=0)height_=(float)r.getRegionHeight();}
    const TextureRegion& getRegion()const{return region_;}
    void setTint(uint16_t tint){tint_=tint;}
    void setBlendMode(uint8_t blend){blend_=blend;}
    void setFlip(bool x,bool y){flipX_=x;flipY_=y;}

    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        if(!visible_||!region_.texture())return;
        uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
        batch.draw(region_,(int)getStageX(),(int)getStageY(),(int)width_,(int)height_,
                   tint_,a,blend_,flipX_,flipY_,0);
    }

private:
    TextureRegion region_{};
    uint16_t tint_=0xFFFFu;
    uint8_t blend_=VXPE_BLEND_ALPHA;
    bool flipX_=false,flipY_=false;
};

class ClickListener:public InputListener {
public:
    bool touchDown(Actor& actor,float x,float y,uint8_t pointer,uint8_t button)override{
        (void)actor;(void)x;(void)y;(void)button;
        pressed_=true;pointer_=pointer;return true;
    }
    void touchUp(Actor& actor,float x,float y,uint8_t pointer,uint8_t button)override{
        (void)button;
        bool was=pressed_&&pointer==pointer_;pressed_=false;
        if(was&&x>=0&&y>=0&&x<actor.getWidth()&&y<actor.getHeight())clicked(actor);
    }
    virtual void clicked(Actor& actor){(void)actor;}
    bool isPressed()const{return pressed_;}
private:
    bool pressed_=false;uint8_t pointer_=0;
};

class Stage {
public:
    Stage(){root_.setTouchable(Touchable::ChildrenOnly);}
    explicit Stage(int viewportW,int viewportH):camera_(viewportW,viewportH){
        root_.setTouchable(Touchable::ChildrenOnly);
    }

    Group& getRoot(){return root_;}
    const Group& getRoot()const{return root_;}
    OrthographicCamera& getCamera(){return camera_;}
    SpriteBatch& getBatch(){return batch_;}

    bool addActor(Actor& actor){return root_.addActor(actor);}
    bool removeActor(Actor& actor){
        if(captured_==&actor)captured_=nullptr;
        if(keyboardFocus_==&actor)keyboardFocus_=nullptr;
        return root_.removeActor(actor);
    }

    void act(float delta){root_.act(delta);}

    void draw(uint16_t* framebuffer,int width,int height){
        batch_.setCamera(&camera_);
        batch_.begin(framebuffer,width,height);
        root_.draw(batch_,255);
        batch_.end();
    }

    Actor* hit(float screenX,float screenY,bool touchable=true){
        float sx=(float)camera_.worldX((int)screenX);
        float sy=(float)camera_.worldY((int)screenY);
        return root_.hit(sx,sy,touchable);
    }

    bool touchDown(int screenX,int screenY,uint8_t pointer=0,uint8_t button=0){
        float sx=(float)camera_.worldX(screenX),sy=(float)camera_.worldY(screenY);
        Actor* target=root_.hit(sx,sy,true);if(!target)return false;
        if(target->fireTouchDown(sx,sy,pointer,button)){captured_=target;capturedPointer_=pointer;return true;}
        return false;
    }
    void touchDragged(int screenX,int screenY,uint8_t pointer=0){
        if(!captured_||pointer!=capturedPointer_)return;
        captured_->fireTouchDragged((float)camera_.worldX(screenX),(float)camera_.worldY(screenY),pointer);
    }
    void touchUp(int screenX,int screenY,uint8_t pointer=0,uint8_t button=0){
        if(!captured_||pointer!=capturedPointer_)return;
        Actor* target=captured_;captured_=nullptr;
        target->fireTouchUp((float)camera_.worldX(screenX),(float)camera_.worldY(screenY),pointer,button);
    }

    void setKeyboardFocus(Actor* actor){keyboardFocus_=actor;}
    Actor* getKeyboardFocus()const{return keyboardFocus_;}
    Actor* getTouchFocus()const{return captured_;}
    void cancelTouchFocus(){captured_=nullptr;}

    bool keyDown(uint8_t key){return keyboardFocus_?keyboardFocus_->fireKeyDown(key):false;}
    bool keyUp(uint8_t key){return keyboardFocus_?keyboardFocus_->fireKeyUp(key):false;}

private:
    Group root_{};
    OrthographicCamera camera_{240,320};
    SpriteBatch batch_{};
    Actor* captured_=nullptr;
    Actor* keyboardFocus_=nullptr;
    uint8_t capturedPointer_=0;
};

}}} // namespace vxpe::gdx::scene2d
