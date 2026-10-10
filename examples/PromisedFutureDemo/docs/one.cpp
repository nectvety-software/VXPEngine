#include "scene.h"
#include <stdio.h>
#include <string.h>
int main(int argc,char**argv){
    static PromisedFuture g; g.input(5);
    static uint16_t buf[240*320];
    g.draw(buf);
    FILE* f=fopen(argv[1],"wb"); fprintf(f,"P6\n240 320\n255\n");
    for(int i=0;i<240*320;++i){uint16_t c=buf[i];unsigned char rgb[3]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31)};fwrite(rgb,1,3,f);} fclose(f);
    return 0;
}
