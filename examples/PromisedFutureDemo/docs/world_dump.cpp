#include "scene.h"
#include <stdio.h>
static uint16_t fb[240*320];
int main(int argc,char**argv){
    static PromisedFuture g; g.input(5); g.update(); g.draw(fb);
    FILE* f=fopen(argv[1],"wb"); fprintf(f,"P6\n120 160\n255\n");
    for(int i=0;i<120*160;++i){uint16_t c=g.worldPixels[i];unsigned char p[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(p,1,3,f);}
    fclose(f); return 0;
}
