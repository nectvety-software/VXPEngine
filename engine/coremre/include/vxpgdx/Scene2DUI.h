/*
 * VXPGDX Scene2D UI - fixed-memory widgets for QVGA/MRE.
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include "vxpgdx/Scene2D.h"
#include "vxpgdx/TinyFont5x7.h"

namespace vxpe { namespace gdx { namespace scene2d { namespace ui {

enum class Align:uint8_t { Left=0, Center=1, Right=2 };

struct LabelStyle {
    uint16_t textColor=0xFFFFu;
    uint16_t shadowColor=0x0000u;
    uint8_t scale=1;
    uint8_t shadow=0;
};

struct ButtonStyle {
    uint16_t upColor=0x3186u;
    uint16_t downColor=0x18E3u;
    uint16_t disabledColor=0x2104u;
    uint16_t borderColor=0xFFFFu;
    uint16_t textColor=0xFFFFu;
    uint8_t borderPx=1;
    uint8_t textScale=1;
};

inline bool uiClipRect(const SpriteBatch& batch,int& x,int& y,int& w,int& h){
    if(w<=0||h<=0)return false;
    VxpeRectI c=batch.clipRect();
    int x1=x+w,y1=y+h,cx1=c.x+c.w,cy1=c.y+c.h;
    if(x<c.x)x=c.x;
    if(y<c.y)y=c.y;
    if(x1>cx1)x1=cx1;
    if(y1>cy1)y1=cy1;
    w=x1-x;h=y1-y;return w>0&&h>0;
}
inline void uiFillRect(SpriteBatch& batch,int x,int y,int w,int h,uint16_t color){
    if(!batch.framebuffer()||!uiClipRect(batch,x,y,w,h))return;
    vxpe2d_fill_rect(batch.framebuffer(),batch.framebufferWidth(),batch.framebufferHeight(),x,y,w,h,color);
}
inline void uiOverlayRect(SpriteBatch& batch,int x,int y,int w,int h,
                          uint16_t color,uint8_t alpha,uint8_t blend=VXPE_BLEND_ALPHA){
    if(!batch.framebuffer()||!alpha||!uiClipRect(batch,x,y,w,h))return;
    vxpe2d_overlay_rect(batch.framebuffer(),batch.framebufferWidth(),batch.framebufferHeight(),
                        x,y,w,h,color,alpha,blend);
}

class BitmapFont5x7 {
public:
    static int textWidth(const char* text,uint8_t scale=1){
        if(!text) return 0;
        if(scale==0) scale=1;
        int line=0,best=0;
        for(const char* p=text;*p;++p){
            if(*p=='\n'){if(line>best)best=line;line=0;}
            else line+=6*scale;
        }
        if(line>best)best=line;
        return best?best-scale:0;
    }
    static int textHeight(const char* text,uint8_t scale=1){
        if(!text) return 0;
        if(scale==0) scale=1;
        int lines=1;for(const char* p=text;*p;++p)if(*p=='\n')++lines;
        return lines*8*scale-scale;
    }
    static void draw(SpriteBatch& batch,const char* text,int worldX,int worldY,
                     uint16_t color,uint8_t scale=1){
        drawScreen(batch,text,batch.toScreenX(worldX),batch.toScreenY(worldY),color,scale);
    }
    static void drawScreen(SpriteBatch& batch,const char* text,int screenX,int screenY,
                           uint16_t color,uint8_t scale=1){
        if(!text||!batch.isDrawing()||!batch.framebuffer())return;
        if(scale==0)scale=1;
        if(scale>4)scale=4;
        batch.flush();
        uint16_t* fb=batch.framebuffer();
        const int fw=batch.framebufferWidth(),fh=batch.framebufferHeight();
        const VxpeRectI clip=batch.clipRect();
        int cx0=clip.x,cy0=clip.y,cx1=clip.x+clip.w,cy1=clip.y+clip.h;
        if(cx0<0)cx0=0;
        if(cy0<0)cy0=0;
        if(cx1>fw)cx1=fw;
        if(cy1>fh)cy1=fh;
        int ox=screenX,x=ox,y=screenY;
        for(const char* p=text;*p;++p){
            unsigned char ch=(unsigned char)*p;
            if(ch=='\n'){x=ox;y+=8*scale;continue;}
            if(ch<32||ch>126)ch='?';
            if(x>=cx1){x+=6*scale;continue;}
            if(x+5*scale<=cx0){x+=6*scale;continue;}
            const uint8_t* rows=detail::kFont5x7[ch-32];
            for(int gy=0;gy<7;++gy){
                int py0=y+gy*scale,py1=py0+scale;
                if(py1<=cy0||py0>=cy1)continue;
                if(py0<cy0)py0=cy0;
                if(py1>cy1)py1=cy1;
                uint8_t bits=rows[gy];
                for(int gx=0;gx<5;++gx){
                    if((bits&(1u<<(4-gx)))==0)continue;
                    int px0=x+gx*scale,px1=px0+scale;
                    if(px1<=cx0||px0>=cx1)continue;
                    if(px0<cx0)px0=cx0;
                    if(px1>cx1)px1=cx1;
                    for(int py=py0;py<py1;++py){
                        uint16_t* row=fb+py*fw;
                        for(int px=px0;px<px1;++px)row[px]=color;
                    }
                }
            }
            x+=6*scale;
        }
    }
};

class Widget:public Actor {
public:
    virtual float getPrefWidth()const{return width_;}
    virtual float getPrefHeight()const{return height_;}
    virtual int getPrefWidthPx()const{return (int)getPrefWidth();}
    virtual int getPrefHeightPx()const{return (int)getPrefHeight();}
    virtual void layout(){}
    void invalidate(){needsLayout_=true;++layoutRevision_;}
    void validate(){if(needsLayout_){layout();needsLayout_=false;}}
    uint16_t getLayoutRevision()const{return layoutRevision_;}
    void act(float delta)override{Actor::act(delta);validate();}
protected:
    void markLayoutChanged(){++layoutRevision_;}
    bool needsLayout_=true;
    uint16_t layoutRevision_=1;
};

class Label:public Widget {
public:
    Label(){setTouchable(Touchable::Disabled);}
    explicit Label(const char* text):text_(text){setTouchable(Touchable::Disabled);pack();}
    Label(const char* text,const LabelStyle& style):text_(text),style_(style){setTouchable(Touchable::Disabled);pack();}

    void setText(const char* text){text_=text;invalidate();}
    const char* getText()const{return text_?text_:"";}
    void setStyle(const LabelStyle& s){style_=s;invalidate();}
    void setAlignment(Align a){align_=a;}
    void setPadding(uint8_t x,uint8_t y){padX_=x;padY_=y;invalidate();}
    void pack(){width_=getPrefWidth();height_=getPrefHeight();needsLayout_=false;}

    float getPrefWidth()const override{return (float)(BitmapFont5x7::textWidth(getText(),style_.scale)+padX_*2);}
    float getPrefHeight()const override{return (float)(BitmapFont5x7::textHeight(getText(),style_.scale)+padY_*2);}

    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        (void)parentAlpha;if(!visible_)return;
        int tw=BitmapFont5x7::textWidth(getText(),style_.scale);
        int x=(int)getStageX()+padX_;
        if(align_==Align::Center)x=(int)getStageX()+((int)width_-tw)/2;
        else if(align_==Align::Right)x=(int)(getStageX()+width_)-tw-padX_;
        int y=(int)getStageY()+padY_;
        if(style_.shadow)BitmapFont5x7::draw(batch,getText(),x+1,y+1,style_.shadowColor,style_.scale);
        BitmapFont5x7::draw(batch,getText(),x,y,style_.textColor,style_.scale);
    }

private:
    const char* text_="";
    LabelStyle style_{};
    Align align_=Align::Left;
    uint8_t padX_=0,padY_=0;
};

class Panel:public Group {
public:
    void setBackground(uint16_t color){background_=color;hasBackground_=true;}
    void setBorder(uint16_t color,uint8_t px=1){border_=color;borderPx_=px;hasBorder_=px>0;}
    void clearBackground(){hasBackground_=false;}
    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        if(!visible_)return;
        batch.flush();
        uint16_t* fb=batch.framebuffer();if(fb){
            int x=batch.toScreenX((int)getStageX()),y=batch.toScreenY((int)getStageY());
            uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
            if(hasBackground_)uiOverlayRect(batch,x,y,(int)width_,(int)height_,background_,a,VXPE_BLEND_ALPHA);
            if(hasBorder_&&borderPx_){
                uiFillRect(batch,x,y,(int)width_,borderPx_,border_);
                uiFillRect(batch,x,y+(int)height_-borderPx_,(int)width_,borderPx_,border_);
                uiFillRect(batch,x,y,borderPx_,(int)height_,border_);
                uiFillRect(batch,x+(int)width_-borderPx_,y,borderPx_,(int)height_,border_);
            }
        }
        Group::draw(batch,parentAlpha);
    }
private:
    uint16_t background_=0,border_=0xFFFFu;
    uint8_t borderPx_=0;bool hasBackground_=false,hasBorder_=false;
};

class Button:public Widget {
public:
    using Callback=void(*)(Button& button,void* user);

    Button():input_(this){setInputListener(&input_);}
    Button(const Button&)=delete;Button& operator=(const Button&)=delete;

    void setStyle(const ButtonStyle& s){style_=s;}
    const ButtonStyle& getStyle()const{return style_;}
    void setDisabled(bool v){disabled_=v;setTouchable(v?Touchable::Disabled:Touchable::Enabled);}
    bool isDisabled()const{return disabled_;}
    bool isPressed()const{return pressed_;}
    void setCallback(Callback cb,void* user=nullptr){callback_=cb;user_=user;}

    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        if(!visible_) return;
        batch.flush();
        uint16_t* fb=batch.framebuffer();if(!fb)return;
        int x=batch.toScreenX((int)getStageX()),y=batch.toScreenY((int)getStageY());
        uint16_t bg=disabled_?style_.disabledColor:(pressed_?style_.downColor:style_.upColor);
        uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
        uiOverlayRect(batch,x,y,(int)width_,(int)height_,bg,a,VXPE_BLEND_ALPHA);
        uint8_t b=style_.borderPx;
        if(b){
            uiFillRect(batch,x,y,(int)width_,b,style_.borderColor);
            uiFillRect(batch,x,y+(int)height_-b,(int)width_,b,style_.borderColor);
            uiFillRect(batch,x,y,b,(int)height_,style_.borderColor);
            uiFillRect(batch,x+(int)width_-b,y,b,(int)height_,style_.borderColor);
        }
    }

protected:
    virtual void clicked(){if(callback_)callback_(*this,user_);}
    ButtonStyle style_{};
    bool pressed_=false,disabled_=false;

private:
    class InternalInput:public InputListener{
    public:
        explicit InternalInput(Button* owner):owner_(owner){}
        bool touchDown(Actor&,float,float,uint8_t,uint8_t)override{
            if(owner_->disabled_) return false;
            owner_->pressed_=true;
            return true;
        }
        void touchDragged(Actor&,float x,float y,uint8_t)override{
            owner_->pressed_=x>=0&&y>=0&&x<owner_->width_&&y<owner_->height_;
        }
        void touchUp(Actor&,float x,float y,uint8_t,uint8_t)override{
            bool hit=owner_->pressed_&&x>=0&&y>=0&&x<owner_->width_&&y<owner_->height_;
            owner_->pressed_=false;if(hit)owner_->clicked();
        }
    private:Button* owner_;
    } input_;
    Callback callback_=nullptr;void* user_=nullptr;
};

class TextButton:public Button {
public:
    TextButton()=default;
    explicit TextButton(const char* text):text_(text){pack();}
    TextButton(const char* text,const ButtonStyle& style):text_(text){style_=style;pack();}
    void setText(const char* t){text_=t;pack();}
    const char* getText()const{return text_?text_:"";}
    void setPadding(uint8_t x,uint8_t y){padX_=x;padY_=y;pack();}
    float getPrefWidth()const override{return (float)(BitmapFont5x7::textWidth(getText(),style_.textScale)+padX_*2+style_.borderPx*2);}
    float getPrefHeight()const override{return (float)(7*style_.textScale+padY_*2+style_.borderPx*2);}
    void pack(){width_=getPrefWidth();height_=getPrefHeight();}
    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        Button::draw(batch,parentAlpha);
        int tw=BitmapFont5x7::textWidth(getText(),style_.textScale);
        int th=7*style_.textScale;
        BitmapFont5x7::draw(batch,getText(),(int)getStageX()+((int)width_-tw)/2,
                            (int)getStageY()+((int)height_-th)/2,style_.textColor,style_.textScale);
    }
private:
    const char* text_="";uint8_t padX_=5,padY_=3;
};

class ImageButton:public Button {
public:
    ImageButton()=default;
    explicit ImageButton(const TextureRegion& region):region_(region){}
    void setRegion(const TextureRegion& region){region_=region;}
    void setImagePadding(uint8_t p){padding_=p;}
    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        Button::draw(batch,parentAlpha);
        if(!region_.texture())return;
        int p=padding_,w=(int)width_-p*2,h=(int)height_-p*2;if(w<=0||h<=0)return;
        uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
        batch.draw(region_,(int)getStageX()+p,(int)getStageY()+p,w,h,0xFFFFu,a,VXPE_BLEND_ALPHA,false,false,1);
    }
private:
    TextureRegion region_{};uint8_t padding_=3;
};

template <uint8_t MaxCells=16>
class Table:public Panel {
public:
    struct Cell{Actor* actor=nullptr;uint8_t col=0,row=0,colspan=1,rowspan=1;};
    void setGrid(uint8_t cols,uint8_t rows,uint8_t padding=2){
        cols_=cols?cols:1;rows_=rows?rows:1;padding_=padding;layoutDirty_=true;
    }
    bool add(Actor& actor,uint8_t col,uint8_t row,uint8_t colspan=1,uint8_t rowspan=1){
        if(cellCount_>=MaxCells||col>=cols_||row>=rows_||!Panel::addActor(actor))return false;
        cells_[cellCount_++]={&actor,col,row,(uint8_t)(colspan?colspan:1),(uint8_t)(rowspan?rowspan:1)};
        layoutDirty_=true;return true;
    }
    void layout(){
        if(!layoutDirty_||!cols_||!rows_)return;
        float cw=(width_-(cols_+1)*padding_)/cols_;
        float ch=(height_-(rows_+1)*padding_)/rows_;
        for(uint8_t i=0;i<cellCount_;++i){
            Cell& c=cells_[i];if(!c.actor)continue;
            float x=padding_+c.col*(cw+padding_),y=padding_+c.row*(ch+padding_);
            float w=cw*c.colspan+padding_*(c.colspan-1);
            float h=ch*c.rowspan+padding_*(c.rowspan-1);
            c.actor->setBounds(x,y,w,h);
        }
        layoutDirty_=false;
    }
    void act(float delta)override{layout();Panel::act(delta);}
private:
    Cell cells_[MaxCells]{};
    uint8_t cellCount_=0,cols_=1,rows_=1,padding_=2;bool layoutDirty_=true;
};


struct ScrollPaneStyle {
    uint16_t backgroundColor=0x0000u;
    uint16_t scrollbarColor=0x7BEFu;
    uint16_t scrollbarTrackColor=0x2104u;
    uint8_t backgroundAlpha=0;
    uint8_t scrollbarAlpha=180;
    uint8_t scrollbarWidth=3;
};

class ScrollPane:public Group {
public:
    ScrollPane():input_(this){
        Group::addActor(content_);
        content_.setTouchable(Touchable::ChildrenOnly);
        setInputListener(&input_);
        setTouchable(Touchable::Enabled);
    }
    ScrollPane(const ScrollPane&)=delete;
    ScrollPane& operator=(const ScrollPane&)=delete;

    void setBounds(float x,float y,float w,float h){
        Actor::setBounds(x,y,w,h);
        layoutDirty_=true;
    }
    void setSize(float w,float h){
        Actor::setSize(w,h);
        layoutDirty_=true;
    }

    bool setWidget(Widget& widget){
        if(widget_==&widget)return true;
        content_.clearChildren();
        widget_=&widget;autoWidgetSize_=true;layoutDirty_=true;
        if(!content_.addActor(widget)){widget_=nullptr;return false;}
        layoutContent();return true;
    }
    bool setActor(Actor& actor,float contentWidth,float contentHeight){
        content_.clearChildren();widget_=&actor;autoWidgetSize_=false;layoutDirty_=true;
        explicitContentW_=(int32_t)contentWidth;explicitContentH_=(int32_t)contentHeight;
        if(!content_.addActor(actor)){widget_=nullptr;return false;}
        layoutContent();return true;
    }
    Actor* getWidget()const{return widget_;}
    Group& getContentGroup(){return content_;}

    void setStyle(const ScrollPaneStyle& s){style_=s;}
    void setScroll(float x,float y){setScrollPixels((int32_t)x,(int32_t)y);}
    void setScrollX(float x){setScrollPixels((int32_t)x,scrollY_);}
    void setScrollY(float y){setScrollPixels(scrollX_,(int32_t)y);}
    void scrollBy(float dx,float dy){setScrollPixels(scrollX_+(int32_t)dx,scrollY_+(int32_t)dy);}
    void setScrollPixels(int32_t x,int32_t y){
        layoutContent();
        scrollX_=x;scrollY_=y;clampScroll();updateContentPosition();
    }
    int32_t getScrollXPixels()const{return scrollX_;}
    int32_t getScrollYPixels()const{return scrollY_;}
    int32_t getMaxScrollXPixels()const{return maxScrollX_;}
    int32_t getMaxScrollYPixels()const{return maxScrollY_;}
    float getScrollX()const{return (float)scrollX_;}
    float getScrollY()const{return (float)scrollY_;}
    float getMaxScrollX()const{return (float)maxScrollX_;}
    float getMaxScrollY()const{return (float)maxScrollY_;}
    bool isDragging()const{return dragging_;}
    void setDragThreshold(uint8_t px){dragThreshold_=px?px:1;}
    void setScrollbarsVisible(bool v){showScrollbars_=v;}

    void act(float delta)override{
        layoutContent();
        Group::act(delta);
    }

    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        if(!visible_)return;
        layoutContent();
        batch.flush();
        const int stageX=(int)getStageX(),stageY=(int)getStageY();
        const int sx=batch.toScreenX(stageX),sy=batch.toScreenY(stageY);
        const uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
        if(style_.backgroundAlpha)
            uiOverlayRect(batch,sx,sy,viewW_,viewH_,style_.backgroundColor,
                          (uint8_t)((uint16_t)a*style_.backgroundAlpha/255u),VXPE_BLEND_ALPHA);
        const bool ok=batch.pushClipRect(stageX,stageY,viewW_,viewH_);
        if(ok)Group::draw(batch,parentAlpha);
        batch.flush();
        if(ok&&showScrollbars_)drawScrollbars(batch,a,sx,sy);
        batch.popClipRect();
    }

    Actor* hit(float stageX,float stageY,bool touchable=true)override{
        if(!visible_||!contains(stageX,stageY))return nullptr;
        if(touchable&&touchable_!=Touchable::Enabled)return nullptr;
        return this;
    }

private:
    class InternalInput:public InputListener {
    public:
        explicit InternalInput(ScrollPane* owner):o_(owner){}
        bool touchDown(Actor&,float x,float y,uint8_t pointer,uint8_t button)override{
            o_->dragging_=false;o_->pointer_=pointer;
            o_->startX_=(int16_t)x;o_->startY_=(int16_t)y;
            o_->startScrollX_=o_->scrollX_;o_->startScrollY_=o_->scrollY_;
            o_->tapChild_=nullptr;
            const float sx=o_->getStageX()+x,sy=o_->getStageY()+y;
            Actor* child=o_->content_.hit(sx,sy,true);
            if(child&&child!=&o_->content_&&child->fireTouchDown(sx,sy,pointer,button))
                o_->tapChild_=child;
            return true;
        }
        void touchDragged(Actor&,float x,float y,uint8_t pointer)override{
            if(pointer!=o_->pointer_)return;
            const int32_t ix=(int32_t)x,iy=(int32_t)y;
            const int32_t dx=ix-o_->startX_,dy=iy-o_->startY_;
            const int32_t adx=dx<0?-dx:dx,ady=dy<0?-dy:dy;
            if(!o_->dragging_&&(adx>=o_->dragThreshold_||ady>=o_->dragThreshold_)){
                o_->dragging_=true;
                if(o_->tapChild_){
                    o_->tapChild_->fireTouchUp(o_->getStageX()-1000.0f,o_->getStageY()-1000.0f,pointer,0);
                    o_->tapChild_=nullptr;
                }
            }
            if(o_->dragging_){
                o_->setScrollPixels(o_->startScrollX_-dx,o_->startScrollY_-dy);
            }else if(o_->tapChild_){
                o_->tapChild_->fireTouchDragged(o_->getStageX()+x,o_->getStageY()+y,pointer);
            }
        }
        void touchUp(Actor&,float x,float y,uint8_t pointer,uint8_t button)override{
            if(pointer!=o_->pointer_)return;
            if(o_->tapChild_&&!o_->dragging_)
                o_->tapChild_->fireTouchUp(o_->getStageX()+x,o_->getStageY()+y,pointer,button);
            o_->tapChild_=nullptr;o_->dragging_=false;
        }
    private:ScrollPane* o_;
    } input_;

    void layoutContent(){
        if(!widget_)return;
        int32_t vw=(int32_t)width_,vh=(int32_t)height_;
        if(vw<0)vw=0;
        if(vh<0)vh=0;
        int32_t cw=explicitContentW_,ch=explicitContentH_;
        uint16_t revision=0;
        if(autoWidgetSize_){
            Widget* w=static_cast<Widget*>(widget_);
            revision=w->getLayoutRevision();
            cw=w->getPrefWidthPx();ch=w->getPrefHeightPx();
        }
        if(cw<vw)cw=vw;
        if(ch<vh)ch=vh;
        if(!layoutDirty_&&vw==viewW_&&vh==viewH_&&cw==contentW_&&ch==contentH_&&revision==widgetRevision_)
            return;
        viewW_=vw;viewH_=vh;contentW_=cw;contentH_=ch;widgetRevision_=revision;
        if(autoWidgetSize_)widget_->setBounds(0,0,(float)contentW_,(float)contentH_);
        content_.setSize((float)contentW_,(float)contentH_);
        maxScrollX_=contentW_>viewW_?contentW_-viewW_:0;
        maxScrollY_=contentH_>viewH_?contentH_-viewH_:0;
        clampScroll();updateContentPosition();layoutDirty_=false;
    }
    void clampScroll(){
        if(scrollX_<0)scrollX_=0;
        if(scrollY_<0)scrollY_=0;
        if(scrollX_>maxScrollX_)scrollX_=maxScrollX_;
        if(scrollY_>maxScrollY_)scrollY_=maxScrollY_;
    }
    void updateContentPosition(){
        content_.setPosition((float)-scrollX_,(float)-scrollY_);
    }
    void drawScrollbars(SpriteBatch& batch,uint8_t parentAlpha,int sx,int sy){
        const uint8_t a=(uint8_t)((uint16_t)parentAlpha*style_.scrollbarAlpha/255u);
        const int bw=style_.scrollbarWidth?style_.scrollbarWidth:2;
        if(maxScrollY_>0&&viewH_>4&&contentH_>0){
            const int trackH=viewH_;
            uiOverlayRect(batch,sx+viewW_-bw,sy,bw,trackH,style_.scrollbarTrackColor,(uint8_t)(a>>1));
            int thumbH=(viewH_*viewH_)/contentH_;
            if(thumbH<6)thumbH=6;
            if(thumbH>trackH)thumbH=trackH;
            const int range=trackH-thumbH;
            const int ty=sy+(range*scrollY_)/maxScrollY_;
            uiOverlayRect(batch,sx+viewW_-bw,ty,bw,thumbH,style_.scrollbarColor,a);
        }
        if(maxScrollX_>0&&viewW_>4&&contentW_>0){
            const int trackW=viewW_;
            uiOverlayRect(batch,sx,sy+viewH_-bw,trackW,bw,style_.scrollbarTrackColor,(uint8_t)(a>>1));
            int thumbW=(viewW_*viewW_)/contentW_;
            if(thumbW<6)thumbW=6;
            if(thumbW>trackW)thumbW=trackW;
            const int range=trackW-thumbW;
            const int tx=sx+(range*scrollX_)/maxScrollX_;
            uiOverlayRect(batch,tx,sy+viewH_-bw,thumbW,bw,style_.scrollbarColor,a);
        }
    }

    Group content_{};
    Actor* widget_=nullptr;
    Actor* tapChild_=nullptr;
    ScrollPaneStyle style_{};
    int32_t scrollX_=0,scrollY_=0,maxScrollX_=0,maxScrollY_=0;
    int32_t contentW_=0,contentH_=0,explicitContentW_=0,explicitContentH_=0;
    int32_t viewW_=0,viewH_=0,startScrollX_=0,startScrollY_=0;
    int16_t startX_=0,startY_=0;
    uint16_t widgetRevision_=0;
    uint8_t pointer_=0,dragThreshold_=3;
    bool autoWidgetSize_=false,dragging_=false,showScrollbars_=true,layoutDirty_=true;
};

struct ListStyle {
    uint16_t backgroundColor=0x0000u;
    uint16_t selectedColor=0x39E7u;
    uint16_t pressedColor=0x2104u;
    uint16_t textColor=0xFFFFu;
    uint16_t selectedTextColor=0xFFFFu;
    uint16_t separatorColor=0x18E3u;
    uint8_t backgroundAlpha=180;
    uint8_t selectedAlpha=220;
    uint8_t rowHeight=18;
    uint8_t textScale=1;
    uint8_t paddingX=4;
    uint8_t separatorPx=1;
};

template <uint8_t MaxItems=32>
class List:public Widget {
public:
    using Callback=void(*)(List& list,int index,const char* item,void* user);

    List():input_(this){setInputListener(&input_);recomputePref();}
    List(const List&)=delete;List& operator=(const List&)=delete;

    bool addItem(const char* text){
        if(!text||count_>=MaxItems)return false;
        items_[count_++]=text;
        if(selected_<0)selected_=0;
        const int tw=BitmapFont5x7::textWidth(text,style_.textScale);
        if(tw>maxTextWidth_)maxTextWidth_=tw;
        updatePrefFromCache();
        return true;
    }
    void clearItems(){
        count_=0;selected_=-1;pressed_=-1;maxTextWidth_=0;
        updatePrefFromCache();
    }
    uint8_t size()const{return count_;}
    const char* getItem(uint8_t i)const{return i<count_&&items_[i]?items_[i]:"";}
    int getSelectedIndex()const{return selected_;}
    const char* getSelected()const{return selected_>=0?getItem((uint8_t)selected_):nullptr;}
    void setSelectedIndex(int index){
        if(count_==0){selected_=-1;return;}
        if(index<0)index=0;
        if(index>=count_)index=count_-1;
        selected_=(int16_t)index;
    }
    void selectNext(){if(count_)setSelectedIndex(selected_+1);}
    void selectPrevious(){if(count_)setSelectedIndex(selected_-1);}
    void activateSelection(){if(selected_>=0&&callback_)callback_(*this,selected_,getSelected(),user_);}
    void setCallback(Callback cb,void* user=nullptr){callback_=cb;user_=user;}
    void setStyle(const ListStyle& style){style_=style;recomputePref();}
    const ListStyle& getStyle()const{return style_;}
    void setNavigationKeys(uint8_t upKey,uint8_t downKey,uint8_t acceptKey){
        upKey_=upKey;downKey_=downKey;acceptKey_=acceptKey;keysEnabled_=true;
    }
    void pack(){recomputePref();}
    float getPrefWidth()const override{return (float)prefWidthPx_;}
    float getPrefHeight()const override{return (float)prefHeightPx_;}
    int getPrefWidthPx()const override{return prefWidthPx_;}
    int getPrefHeightPx()const override{return prefHeightPx_;}
    uint8_t getLastDrawnRows()const{return lastDrawnRows_;}

    void draw(SpriteBatch& batch,uint8_t parentAlpha)override{
        if(!visible_)return;
        batch.flush();
        const int stageX=(int)getStageX(),stageY=(int)getStageY();
        const int sx=batch.toScreenX(stageX),sy=batch.toScreenY(stageY);
        const uint8_t a=(uint8_t)((uint16_t)parentAlpha*alpha_/255u);
        if(style_.backgroundAlpha)
            uiOverlayRect(batch,sx,sy,(int)width_,(int)height_,style_.backgroundColor,
                          (uint8_t)((uint16_t)a*style_.backgroundAlpha/255u));
        lastDrawnRows_=0;
        const int rowH=style_.rowHeight;
        if(count_==0||rowH<=0)return;
        const VxpeRectI clip=batch.clipRect();
        int first=0;
        if(clip.y>sy)first=(clip.y-sy)/rowH;
        int last=(clip.y+clip.h-1-sy)/rowH;
        if(first<0)first=0;
        if(last>=count_)last=count_-1;
        if(first>=count_||last<first)return;
        const int textH=7*style_.textScale;
        const int textX=sx+style_.paddingX;
        for(int i=first;i<=last;++i){
            const int ry=sy+i*rowH;
            const bool sel=i==selected_,press=i==pressed_;
            if(sel||press){
                const uint16_t c=press?style_.pressedColor:style_.selectedColor;
                uiOverlayRect(batch,sx,ry,(int)width_,rowH,c,
                              (uint8_t)((uint16_t)a*style_.selectedAlpha/255u));
            }
            const uint16_t tc=sel?style_.selectedTextColor:style_.textColor;
            BitmapFont5x7::drawScreen(batch,getItem((uint8_t)i),textX,
                                      ry+(rowH-textH)/2,tc,style_.textScale);
            if(style_.separatorPx&&i+1<count_)
                uiFillRect(batch,sx,ry+rowH-style_.separatorPx,(int)width_,
                           style_.separatorPx,style_.separatorColor);
            ++lastDrawnRows_;
        }
    }

private:
    class InternalInput:public InputListener {
    public:
        explicit InternalInput(List* owner):o_(owner){}
        bool touchDown(Actor&,float x,float y,uint8_t,uint8_t)override{
            (void)x;const int index=o_->indexAt(y);if(index<0)return false;
            o_->pressed_=(int16_t)index;o_->selected_=(int16_t)index;return true;
        }
        void touchDragged(Actor&,float,float y,uint8_t)override{
            o_->pressed_=(int16_t)o_->indexAt(y);
        }
        void touchUp(Actor&,float,float y,uint8_t,uint8_t)override{
            const int index=o_->indexAt(y);
            const bool fire=index>=0&&index==o_->pressed_;
            o_->pressed_=-1;
            if(fire){o_->selected_=(int16_t)index;o_->activateSelection();}
        }
        bool keyDown(Actor&,uint8_t key)override{
            if(!o_->keysEnabled_)return false;
            if(key==o_->upKey_){o_->selectPrevious();return true;}
            if(key==o_->downKey_){o_->selectNext();return true;}
            if(key==o_->acceptKey_){o_->activateSelection();return true;}
            return false;
        }
    private:List* o_;
    } input_;

    int indexAt(float localY)const{
        const int y=(int)localY;
        if(y<0||style_.rowHeight==0)return -1;
        const int i=y/style_.rowHeight;
        return i>=0&&i<count_?i:-1;
    }
    void recomputePref(){
        maxTextWidth_=0;
        for(uint8_t i=0;i<count_;++i){
            const int w=BitmapFont5x7::textWidth(getItem(i),style_.textScale);
            if(w>maxTextWidth_)maxTextWidth_=w;
        }
        updatePrefFromCache();
    }
    void updatePrefFromCache(){
        const int32_t newW=maxTextWidth_+style_.paddingX*2;
        const int32_t newH=(int32_t)count_*style_.rowHeight;
        if(newW!=prefWidthPx_||newH!=prefHeightPx_)markLayoutChanged();
        prefWidthPx_=newW;prefHeightPx_=newH;
        width_=(float)prefWidthPx_;height_=(float)prefHeightPx_;
        needsLayout_=false;
    }

    const char* items_[MaxItems]{};
    ListStyle style_{};
    Callback callback_=nullptr;void* user_=nullptr;
    int32_t prefWidthPx_=0,prefHeightPx_=0,maxTextWidth_=0;
    int16_t selected_=-1,pressed_=-1;
    uint8_t count_=0,upKey_=0,downKey_=0,acceptKey_=0,lastDrawnRows_=0;
    bool keysEnabled_=false;
};

}}}} // namespace vxpe::gdx::scene2d::ui
