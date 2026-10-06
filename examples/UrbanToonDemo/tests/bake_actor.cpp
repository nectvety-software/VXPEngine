#include "actor.h"
#include <stdio.h>
#include <assert.h>
int main(int argc,char** argv){
    assert(argc==2);FILE* output=fopen(argv[1],"wb");assert(output);
    static uint16_t color[96*144],depth[96*144];VxpeToonTarget3D target={color,depth,96,144};
    VxpeToonCamera3D camera;vxpe_toon3d_camera_init(&camera,96,144);
    camera.position={-65,85,-180};camera.sin_yaw_q14=5568;camera.cos_yaw_q14=15408;
    camera.sin_pitch_q14=2933;camera.cos_pitch_q14=16119;camera.focal_px=148;camera.horizon_y=78;
    for(int frame=0;frame<6;++frame){vxpe_toon3d_clear(&target,0);UrbanActorPose pose={frame*4,0,0,0,0,16384};
        urban_actor_draw(&target,&camera,{0,0,0},&pose,false);
        assert(urban_actor_vertex_count()==384&&urban_actor_face_count()==640);
        int coverage=0;for(int i=0;i<96*144;++i){uint16_t c=color[i];unsigned char rgba[4]={(unsigned char)(((c>>11)&31)*255/31),(unsigned char)(((c>>5)&63)*255/63),(unsigned char)((c&31)*255/31),(unsigned char)(depth[i]==65535?0:255)};
            if(rgba[3])++coverage;fwrite(rgba,1,4,output);}assert(coverage>500&&coverage<96*144/2);
    }
    fclose(output);puts("PASS: six mesh animation frames, transparent coverage and fixed geometry budget");
}
