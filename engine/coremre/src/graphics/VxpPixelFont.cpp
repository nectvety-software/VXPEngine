#include "graphics/VxpPixelFont.h"
#include "PixelFontData.inc"
struct Face { const uint8_t* rows;const uint8_t* widths;int width,height; };
static const Face faces[]={
    {font_rows_0,font_widths_0,5,7},{font_rows_1,font_widths_1,7,9},
    {font_rows_2,font_widths_2,5,7}};
static VxpeFontStyle sane(const VxpeFontStyle* value){
    VxpeFontStyle s;if(value)s=*value;else vxpe_font_style_default(&s);
    if(s.font_id>2)s.font_id=0;
    if(s.scale<1)s.scale=1;
    if(s.scale>4)s.scale=4;
    if(s.spacing>4)s.spacing=4;
    return s;
}
void vxpe_font_style_default(VxpeFontStyle* s){
    if(!s)return;
    s->font_id=0;s->scale=1;s->spacing=1;s->effects=VXPE_FONT_SHADOW;
    s->color565=0xFFB8;s->shadow565=0x0000;s->outline565=0x0862;s->highlight565=0xFFFF;
}
static int glyph_index(unsigned char c){return c>=32&&c<=126?c-32:'?'-32;}
int vxpe_font_height(const VxpeFontStyle* style){auto s=sane(style);return faces[s.font_id].height*s.scale;}
int vxpe_font_measure(const char* text,const VxpeFontStyle* style){
    if(!text)return 0;
    auto s=sane(style);const auto& face=faces[s.font_id];
    int widest=0,width=0;bool any=false;
    for(int i=0;i<VXPE_FONT_TEXT_MAX&&text[i];++i){
        if(text[i]=='\n'){if(width>widest)widest=width;width=0;any=false;continue;}
        if(any)width+=s.spacing*s.scale;
        width+=face.widths[glyph_index((unsigned char)text[i])]*s.scale;any=true;
    }
    return width>widest?width:widest;
}
static void dot(uint16_t* fb,int w,int h,int x,int y,int scale,uint16_t color,VxpeRectI clip){
    for(int yy=0;yy<scale;++yy)for(int xx=0;xx<scale;++xx){int px=x+xx,py=y+yy;
        if(px>=0&&px<w&&py>=0&&py<h&&px>=clip.x&&py>=clip.y&&
           px<(int)clip.x+clip.w&&py<(int)clip.y+clip.h)fb[py*w+px]=color;
    }
}
void vxpe_font_draw(uint16_t* fb,int w,int h,int x,int y,const char* text,
    const VxpeFontStyle* style,VxpeRectI clip){
    if(!fb||!text||w<=0||h<=0||w>32767||h>32767||clip.w<=0||clip.h<=0||x<-32768||x>32767||y<-32768||y>32767)return;
    auto s=sane(style);const auto& f=faces[s.font_id];int origin=x;
    // Paint effects for the entire run before foreground, preserving overlapping glyph ink.
    for(int pass=0;pass<3;++pass){int px=x,py=y;
        if(pass==0&&!(s.effects&VXPE_FONT_SHADOW))continue;
        if(pass==1&&!(s.effects&VXPE_FONT_OUTLINE))continue;
        for(int i=0;i<VXPE_FONT_TEXT_MAX&&text[i];++i){
            if(text[i]=='\n'){px=origin;py+=(f.height+3)*s.scale;continue;}
            int index=glyph_index((unsigned char)text[i]);
            for(int yy=0;yy<f.height;++yy)for(int xx=0;xx<f.widths[index];++xx){
                if(!(f.rows[index*f.height+yy]&(1<<(f.width-1-xx))))continue;
                int gx=px+xx*s.scale,gy=py+yy*s.scale;
                if(pass==0)dot(fb,w,h,gx+s.scale,gy+s.scale,s.scale,s.shadow565,clip);
                else if(pass==1){
                    dot(fb,w,h,gx-s.scale,gy,s.scale,s.outline565,clip);
                    dot(fb,w,h,gx+s.scale,gy,s.scale,s.outline565,clip);
                    dot(fb,w,h,gx,gy-s.scale,s.scale,s.outline565,clip);
                    dot(fb,w,h,gx,gy+s.scale,s.scale,s.outline565,clip);
                }else{
                    bool top=yy==0||!(f.rows[index*f.height+yy-1]&(1<<(f.width-1-xx)));
                    dot(fb,w,h,gx,gy,s.scale,(s.effects&VXPE_FONT_BEVEL)&&top?s.highlight565:s.color565,clip);
                }
            }
            px+=(f.widths[index]+s.spacing)*s.scale;
        }
    }
}
