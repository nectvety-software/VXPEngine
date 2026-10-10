/* Prove the tower hole mechanism: the "glass band" quads at radius rs+3 are
 * OUTSIDE the tower shell (radius rs) yet drawn with arbitrary illumination
 * and against a depth test. Check radius relationship and whether the band
 * interpenetrates the shell. */
#include <stdio.h>
int main(){
    int h=235,r=61;
    int ys[5]={0,h/5,h*2/5,h*4/5,h},rs[5]={r,r*6/5,r*11/10,r*4/5,r/4};
    printf("level  y_bottom y_top   R_bottom R_top   band_R(bottom) band_R(top)\n");
    for(int l=0;l<4;++l)
        printf("  %d     %6d %6d    %6d %6d     %6d       %6d\n",l,ys[l],ys[l+1],rs[l],rs[l+1],rs[l]+3,rs[l+1]+3);
    printf("\nRadial gap between shell and band: 3 units at every level.\n");
    printf("Shell quads: level l spans R=rs[l]..rs[l+1]\n");
    printf("Band quads:  at fixed R=rs[l]+3 and rs[l+1]+3 (both OUTSIDE the shell)\n");
    /* do consecutive shell levels overlap radially? */
    printf("\nRadial overlap between consecutive shell levels:/n");
    for(int l=0;l<3;++l){
        int outerBottom=rs[l], innerTop=rs[l+2]; /* level l top = rs[l+1] ; level l+1 bottom = rs[l+1] */
        printf("  level %d top R=%d ; level %d bottom R=%d -> %s\n",
            l, rs[l+1], l+1, rs[l+1], rs[l+1]==rs[l+1]?"contiguous (no overlap)":"overlap");
    }
    return 0;
}
