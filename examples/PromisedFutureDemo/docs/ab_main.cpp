#include "scene.h"
#include <stdio.h>
#include <string.h>
int main(){
    static PromisedFuture g; g.input(5);
    static uint16_t a[240*320], b[240*320];
    extern int aff_run_a(); extern int aff_run_b();
    int na=aff_run_a(), nb=aff_run_b();
    printf("A(affine=1) drew=%d  B(affine=0) drew=%d\n", na, nb);
    /* compare stored buffers */
    extern uint16_t* aff_buf_a(); extern uint16_t* aff_buf_b();
    uint16_t* pa=aff_buf_a(); uint16_t* pb=aff_buf_b();
    int diff=0, maxchan=0;
    for(int i=0;i<240*320;++i){
        if(pa[i]!=pb[i]){
            diff++;
            uint16_t x=pa[i],y=pb[i];
            int dr=((x>>11)&31)-((y>>11)&31); if(dr<0)dr=-dr;
            int dg=((x>>5)&63)-((y>>5)&63); if(dg<0)dg=-dg;
            int db=(x&31)-(y&31); if(db<0)db=-db;
            if(dr>maxchan)maxchan=dr; if(dg>maxchan)maxchan=dg; if(db>maxchan)maxchan=db;
        }
    }
    printf("pixels differing: %d / %d (%.2f%%)\n", diff, 240*320, 100.0*diff/(240*320));
    printf("max channel delta (0..63/31): %d\n", maxchan);
    return 0;
}
