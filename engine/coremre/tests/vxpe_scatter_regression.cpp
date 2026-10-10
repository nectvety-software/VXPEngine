#include "graphics/VxpScatter2D.h"
#include <cassert>
int main() {
using coremre::VxpScatter2D;
assert(VxpScatter2D::hash(0,0,42)==4237770831u);
assert(VxpScatter2D::hash(3,7,42)==3819037551u);
assert(VxpScatter2D::hash(-1,5,42)==2724760519u);
int cells[300];for(int &v:cells)v=-1;
auto occupied=[&](int x,int y){return x>=0&&x<15&&y>=0&&y<20&&cells[y*15+x]>=0;};
auto emit=[&](int x,int y,unsigned v){cells[y*15+x]=int(v);};
assert(VxpScatter2D::paint(0,0,14,19,4,0,2,42,occupied,emit)==0);
unsigned n=VxpScatter2D::paint(0,0,14,19,4,100,2,42,occupied,emit);assert(n>0);
for(int y=0;y<20;++y)for(int x=0;x<15;++x)if(occupied(x,y))
for(int b=y-1;b<=y+1;++b)for(int a=x-1;a<=x+1;++a)if(a!=x||b!=y)assert(!occupied(a,b));
assert(VxpScatter2D::paint(0,0,14,19,4,100,2,42,occupied,emit)==0);
}
