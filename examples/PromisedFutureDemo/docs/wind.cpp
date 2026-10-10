/* The demo draws each tower ring with ring16(x,...,s) and ring16(x,...,s+1).
   ring16 index k=(i&15)*2 steps 2 entries in the 32-entry table = 22.5 degrees.
   So s covers 0,1,..15 with 22.5 deg steps -> wraps at s=16 (15*22.5=337.5).
   That is correct. BUT the ring radius sequence for level 1 is 73->67 (SHRINKING)
   while level 0 is 61->73 (GROWING). Check whether the shell is actually a
   proper surface or whether alternating levels flip the facing. */
#include <stdio.h>
int main(){
    int h=235,r=61;
    int ys[5]={0,h/5,h*2/5,h*4/5,h},rs[5]={r,r*6/5,r*11/10,r*4/5,r/4};
    printf("radius profile: ");
    for(int i=0;i<5;++i) printf("%d ",rs[i]);
    printf("\ndelta per level:");
    for(int i=0;i<4;++i) printf("  L%d:%+d",i,rs[i+1]-rs[i]);
    printf("\n\nObserve: level0 grows (+12), level1 shrinks (-6), level2 shrinks (-19), level3 shrinks (-33).\n");
    printf("The silhouette bulges at y=%d then tapers. That is intentional.\n", ys[1]);
    printf("\nThe real issue: for a CONVEX ring, the 16 quads per level are each\n");
    printf("planar. A viewer at the axis sees ~8 front-facing and ~8 back-facing.\n");
    printf("Back-facing quads are correctly hidden by the depth test.\n");
    printf("Holes appear only if a FRONT quad loses the depth test to a BACK quad.\n");
    printf("That needs the two to overlap in screen space with the back one nearer.\n");
    printf("\nWith bend=level*level*2, level 0 has bend=0 (no shear);\n");
    printf("level 1 bend=2, level 2 bend=8, level 3 bend=18.\n");
    printf("The shear moves upper rings sideways, so a sheared ring can project\n");
    printf("onto the same screen area as an unsheared one from another level.\n");
    return 0;
}
