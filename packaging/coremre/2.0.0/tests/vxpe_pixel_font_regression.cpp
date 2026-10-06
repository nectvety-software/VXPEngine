#include "graphics/VxpPixelFont.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(){
    VxpeFontStyle s;vxpe_font_style_default(&s);
    assert(vxpe_font_measure("",&s)==0&&vxpe_font_measure(0,&s)==0);
    assert(vxpe_font_measure("II",&s)==7&&vxpe_font_measure("III\nW",&s)==11);
    assert(vxpe_font_height(&s)==7);s.font_id=1;assert(vxpe_font_height(&s)==9);
    s.font_id=2;assert(vxpe_font_measure("111",&s)==vxpe_font_measure("888",&s));
    s.scale=2;assert(vxpe_font_measure("123",&s)==34);
    s.font_id=255;s.scale=0;s.spacing=255;assert(vxpe_font_measure("II",&s)==10);
    vxpe_font_style_default(&s);assert(vxpe_font_measure("\xff",&s)==vxpe_font_measure("?",&s));
    char huge[700];memset(huge,'W',699);huge[699]=0;assert(vxpe_font_measure(huge,&s)==512*6-1);
    uint16_t screen[240*320+2]={};screen[0]=screen[240*320+1]=0xCAFE;
    s.effects=7;s.scale=4;s.color565=0xFFFF;s.highlight565=0xFFE9;
    vxpe_font_draw(screen+1,240,320,-10,-12,"Clipped 9\nVAELORA",&s,{3,4,30,24});
    int ink=0;for(int y=0;y<320;++y)for(int x=0;x<240;++x){uint16_t c=screen[1+y*240+x];
        if(x<3||x>=33||y<4||y>=28)assert(c==0);else if(c)++ink;}
    assert(ink>0&&screen[0]==0xCAFE&&screen[240*320+1]==0xCAFE);
    vxpe_font_draw(0,240,320,0,0,"null",0,{0,0,240,320});
    for(int i=1;i<=240*320;++i)screen[i]=0x0862;
    vxpe_font_style_default(&s);s.effects=7;s.color565=0xC59F;s.highlight565=0xFFFF;
    vxpe_font_draw(screen+1,240,320,9,11,"Vale UI: Aa Bb 0123456789",&s,{0,0,240,320});
    s.font_id=1;s.scale=2;s.color565=0xEDEB;
    vxpe_font_draw(screen+1,240,320,10,44,"VAELORA",&s,{0,0,240,320});
    s.font_id=2;s.scale=1;s.spacing=0;s.effects=1;s.color565=0x57F7;
    vxpe_font_draw(screen+1,240,320,12,91,"1100/1100  01:29",&s,{0,0,240,320});
    s.font_id=0;s.scale=3;s.spacing=2;s.effects=3;
    vxpe_font_draw(screen+1,240,320,-7,130,"Clipped\n?7",&s,{13,141,104,50});
    assert(screen[0]==0xCAFE&&screen[240*320+1]==0xCAFE);
    FILE* f=fopen("font_parity.raw","wb");assert(f);fwrite(screen+1,2,240*320,f);fclose(f);
    puts("PASS: three faces, width/height, tabular digits, multiline, limits/fallback, effect clipping and guards");
}
