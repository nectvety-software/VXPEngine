#include "scene.h"

namespace {
int absn(int n){return n<0?-n:n;}
int maxn(int a,int b){return a>b?a:b;}
const int cx[16]={256,237,181,98,0,-98,-181,-237,-256,-237,-181,-98,0,98,181,237};
const int cy[16]={0,98,181,237,256,237,181,98,0,-98,-181,-237,-256,-237,-181,-98};
const int durations[3][4]={{420,650,500,1050},{450,1400,600,950},{380,650,600,1250}};
unsigned short color(int hero,int skin){
    const unsigned short base[3]={0xC59F,0xFCE8,0x57F7},alt[3]={0x87FF,0xC5BF,0xFD30};
    return skin?alt[hero]:base[hero];
}
// Every effect pixel is clipped to the world viewport, including glow and trails.
struct Ink {
    unsigned short* fb; int alpha;
    void pixel(int x,int y,unsigned short c){
        if(x<0||x>=240||y<41||y>=250)return;
        unsigned short& d=fb[y*240+x];
        int a=alpha;
        int r=(((c>>11)&31)*a+((d>>11)&31)*(255-a))/255;
        int g=(((c>>5)&63)*a+((d>>5)&63)*(255-a))/255;
        int b=((c&31)*a+(d&31)*(255-a))/255;
        d=(unsigned short)((r<<11)|(g<<5)|b);
    }
    void line(int x,int y,int x2,int y2,unsigned short c,int width=1){
        int dx=absn(x2-x),sx=x<x2?1:-1,dy=-absn(y2-y),sy=y<y2?1:-1,err=dx+dy;
        for(;;){for(int xx=0;xx<width;++xx)for(int yy=0;yy<width;++yy)pixel(x+xx-width/2,y+yy-width/2,c);
            if(x==x2&&y==y2)break;
            int e=err*2;if(e>=dy){err+=dy;x+=sx;}if(e<=dx){err+=dx;y+=sy;}
        }
    }
    void ring(int x,int y,int rx,int ry,unsigned short c,int from=0,int segments=16){
        for(int i=from;i<from+segments;++i){int a=i&15,b=(i+1)&15;
            line(x+cx[a]*rx/256,y+cy[a]*ry/256,x+cx[b]*rx/256,y+cy[b]*ry/256,c,rx>10?2:1);
        }
    }
    void diamond(int x,int y,int r,unsigned short c){
        for(int yy=-r;yy<=r;++yy){int half=r-absn(yy);for(int xx=-half;xx<=half;++xx)pixel(x+xx,y+yy,c);}
        line(x,y-r,x+r,y,0xFFFF);line(x-r,y,x,y-r,0xFFE9);
        line(x,y-r+2,x,y+r-2,0xFFFF);
    }
    void arrow(int x,int y,int dx,int dy,unsigned short c,int length=14){
        int n=maxn(absn(dx),absn(dy));if(!n){dx=1;n=1;}
        int ux=dx*length/n,uy=dy*length/n;
        line(x-ux,y-uy,x,y,c,2);
        line(x,y,x-ux/3-uy/3,y-uy/3+ux/3,0xFFFF);
        line(x,y,x-ux/3+uy/3,y-uy/3-ux/3,0xFFFF);
    }
};
}

void FoxScene::spawn_effect(int owner,int hero,int skill,int x,int y,int x2,int y2,int impact){
    int slot=0;
    for(int i=0;i<24;++i){if(!effects[i].life){slot=i;break;}if(effects[i].life<effects[slot].life)slot=i;}
    int duration=impact?(skill==2?850:400):durations[hero][skill];
    effects[slot]={x,y,duration,hero,skill,owner,x2,y2,duration,impact};
}

void FoxScene::draw_skill_effects(unsigned short* fb){
    for(const auto& e:effects)if(e.life){
        int elapsed=e.duration-e.life,t=elapsed*256/e.duration;
        int fade=e.life<220?e.life*255/220:255;
        Ink ink={fb,fade};unsigned short c=color(e.hero,fighters[e.owner].skin),gold=0xFFE9;
        int x=e.x,y=e.y-camera_y-20,ground=e.y-camera_y;
        int dx=e.x2-e.x,dy=e.y2-e.y,n=maxn(absn(dx),absn(dy));if(!n){dx=1;n=1;}
        int ux=dx*256/n,uy=dy*256/n;
        if(e.impact){
            // Binding effects live on the hit position; their caster sparks never imply a hit.
            if(e.skill==2){
                if(e.hero==0){
                    for(int i=0;i<3;++i)ink.ring(x,y-10+i*11,16+t/32,6,gold);
                    ink.line(x-14,y-17,x-14,y+16,c,2);ink.line(x+14,y-17,x+14,y+16,c,2);
                }else{
                    ink.ring(x,y+17,21,7,c);
                    for(int i=0;i<4;++i){int xx=x-15+i*10;ink.line(xx,y+20,xx,y-15-(i&1)*8,c,2);}
                    ink.arrow(x,y,ux,uy,0xFFFF,12);
                }
            }else{
                for(int i=0;i<(e.hero==0?6:4);++i){int a=(i*3+t/24)&15,r=5+t/9;
                    if(e.hero==0)ink.diamond(x+cx[a]*r/256,y+cy[a]*r/256,3,c);
                    else ink.line(x+cx[a]*r/256,y+cy[a]*r/256,x+cx[a]*(r+7)/256,y+cy[a]*(r+7)/256,c);
                }
            }
            continue;
        }
        if(e.hero==0){
            if(e.skill==0){ // Prism Bolt: small rotating launch sigil; the projectile carries the prism.
                ink.diamond(x,y,7+t/24,gold);
                ink.line(x,y,x+ux*(10+t/16)/256,y+uy*(10+t/16)/256,c,2);
            }else if(e.skill==1){ // Light Burst: radial shards explode outward and fade.
                int r=9+t/4;ink.ring(x,y,r,r/2,c);
                for(int i=0;i<8;++i){int a=i*2;int xx=x+cx[a]*r/256,yy=y+cy[a]*r/256;
                    ink.line(xx,yy,x+cx[a]*(r+13)/256,y+cy[a]*(r+13)/256,gold,2);
                    ink.diamond(xx,yy,3,c);
                }
            }else if(e.skill==2){ // Anchor Ray: two gate rings and a narrowing beam at launch.
                int reach=12+t/6;
                ink.line(x,y,x+ux*reach/256,y+uy*reach/256,c,2);
                ink.ring(x+ux*10/256,y+uy*10/256,7,11,gold);
                ink.ring(x+ux*reach/256,y+uy*reach/256,5,8,gold);
            }else{ // Prism Nova: a rune wheel, expanding ground rings, rising crystalline crown.
                int r=18+t/3;ink.ring(x,ground-4,r,r/3,c);ink.ring(x,ground-4,r*2/3,r/5,gold);
                for(int i=0;i<6;++i){int a=(i*3+elapsed/100)&15;
                    int xx=x+cx[a]*r/256,yy=ground-8+cy[a]*r/768;
                    ink.diamond(xx,yy-12-(256-t)/16,5+(i&1),c);
                    ink.line(xx,yy-8,xx,yy+4,gold);
                }
                if(t<100){ink.line(x-10,y,x+10,y,gold,2);ink.line(x,y-14,x,y+14,0xFFFF,2);}
            }
        }else if(e.hero==1){
            if(e.skill==0){ // Hammer Arc: directional crescent and the square hammer head.
                int angle=0,best=-100000;for(int i=0;i<16;++i){int dot=cx[i]*ux+cy[i]*uy;if(dot>best){best=dot;angle=i;}}
                int a=angle-4+t/32;ink.ring(x,y,35,26,c,a-3,4);ink.ring(x,y,31,23,gold,a-3,4);
                int xx=x+cx[a&15]*35/256,yy=y+cy[a&15]*26/256;
                ink.line(x,y,xx,yy,gold,2);
                ink.line(xx-5,yy-5,xx+5,yy-5,c,3);ink.line(xx+5,yy-5,xx+5,yy+5,c,3);
                ink.line(xx+5,yy+5,xx-5,yy+5,c,3);ink.line(xx-5,yy+5,xx-5,yy-5,c,3);
            }else if(e.skill==1){ // Iron Guard: shield follows the armored hero, with a pulsing rivet frame.
                if(fighters[e.owner].hp<=0||!fighters[e.owner].shield)continue;
                x=fighters[e.owner].x;y=fighters[e.owner].y-camera_y-27;
                int w=18+((elapsed/100)&1);
                ink.line(x-w,y-17,x+w,y-17,c,2);ink.line(x-w,y-17,x-w,y+7,c,2);
                ink.line(x+w,y-17,x+w,y+7,c,2);ink.line(x-w,y+7,x,y+22,c,2);ink.line(x+w,y+7,x,y+22,c,2);
                ink.line(x-8,y,x+8,y,gold,2);ink.line(x,y-10,x,y+11,gold,2);
                for(int i=0;i<4;++i)ink.diamond(x+(i&1?w:-w),y+(i<2?-14:5),2,0xFFFF);
            }else if(e.skill==2){ // Charge: thick speed rails and dust along the actual swept dash.
                for(int j=-1;j<=1;++j){int off=j*6;
                    ink.line(x-uy*off/256,y+ux*off/256,e.x2-uy*off/256,e.y2-camera_y-20+ux*off/256,c,j?1:3);
                }
                for(int i=0;i<6;++i){int a=i*43;int xx=e.x+dx*a/256,yy=e.y+dy*a/256-camera_y;
                    ink.ring(xx-ux*t/4096,yy,3+t/24,2+t/48,gold);
                }
                ink.ring(e.x2,e.y2-camera_y,12+t/14,4+t/42,c);
            }else{ // Earthbreak: a ground shockwave and branching jagged cracks, no aerial shards.
                int r=8+t/3;ink.ring(x,ground,r,r/2,c);ink.ring(x,ground,r/2,r/4,gold);
                for(int i=0;i<7;++i){int a=i*2;int xx=x+cx[a]*r/256,yy=ground+cy[a]*r/512;
                    int mx=x+cx[a]*r/512+cy[a]*4/256,my=ground+cy[a]*r/1024-cx[a]*4/256;
                    ink.line(x,ground,mx,my,0xA344,3);ink.line(mx,my,xx,yy,c,2);
                    ink.line(mx,my,mx+cy[a]*12/256,my-cx[a]*6/256,gold);
                }
            }
        }else{
            if(e.skill==0){ // Wind Bolt: curling air at the bow, silver-arrow flight is drawn below.
                ink.ring(x,y,8+t/20,5+t/32,c,elapsed/50,10);
                ink.line(x-ux*10/256,y-uy*10/256,x+ux*15/256,y+uy*15/256,0xFFFF);
            }else if(e.skill==1){ // Gust Step: fading afterimage silhouettes and wind ribbons at actual dash endpoints.
                for(int i=0;i<3;++i){int xx=e.x+dx*i/3,yy=e.y+dy*i/3-camera_y-18;
                    ink.ring(xx,yy-17,4,5,c);ink.line(xx,yy-12,xx,yy+4,c,2);
                    ink.line(xx,yy+4,xx-6,yy+14,c);ink.line(xx,yy+4,xx+7,yy+12,c);
                }
                for(int i=0;i<2;++i)ink.line(x,y+6+i*8,e.x2,e.y2-camera_y-12+i*6,c,2);
                ink.ring(e.x2,e.y2-camera_y,14+t/18,5+t/54,c,elapsed/60,12);
            }else if(e.skill==2){ // Pinning Shot: bow crosshair; successful hit shows a vertical wind cage.
                ink.ring(x+ux*20/256,y+uy*20/256,12,12,c);
                int xx=x+ux*20/256,yy=y+uy*20/256;
                ink.line(xx-17,yy,xx+17,yy,0xFFFF);ink.line(xx,yy-17,xx,yy+17,c);
            }else{ // Arrowstorm: an ellipse on the target area with staggered falling arrow volleys.
                int range=absn(dx)+absn(dy);int tx=range<180?e.x2:e.x,ty=(range<180?e.y2:e.y)-camera_y;
                ink.ring(tx,ty-8,39,18,c);
                for(int i=0;i<9;++i){int age=(elapsed+i*71)%430;
                    if(age>340)continue;
                    int xx=tx-32+(i*17)%65,yy=ty-68+age/5;
                    ink.arrow(xx,yy,1,4,(i&1)?c:0xFFFF,13);
                    if(age>290)ink.ring(xx,ty-5+(i%3-1)*7,4+(age-290)/8,2,c);
                }
            }
        }
    }
    for(const auto& p:projectiles)if(p.active){
        int y=p.y-camera_y;if(y<25||y>270)continue;
        unsigned short c=color(p.hero,fighters[p.owner].skin);Ink ink={fb,235};
        int n=maxn(absn(p.vx),absn(p.vy));if(!n)n=1;int ux=p.vx*256/n,uy=p.vy*256/n;
        if(p.hero==0&&p.skill==0){
            for(int i=1;i<4;++i)ink.diamond(p.x-p.vx*i,y-p.vy*i,5-i,c);
            ink.diamond(p.x,y,6,0xFFE9);ink.diamond(p.x,y,4,c);
        }else if(p.hero==0){
            ink.line(p.x-p.vx*4,y-p.vy*4,p.x,y,c,2);
            ink.ring(p.x,y,6,9,0xFFE9);ink.ring(p.x-p.vx*2,y-p.vy*2,4,6,c);
        }else if(p.skill==0){
            ink.arrow(p.x,y,ux,uy,0xFFFF,15);
            ink.ring(p.x-ux*9/256,y-uy*9/256,10,6,c,p.life/65,10);
        }else{
            ink.arrow(p.x,y,ux,uy,c,18);
            for(int i=0;i<3;++i)ink.diamond(p.x-p.vx*i*2,y-p.vy*i*2,2,0xFFFF);
        }
    }
}
