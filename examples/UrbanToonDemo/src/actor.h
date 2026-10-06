#pragma once
#include "graphics/VxpToon3D.h"
struct UrbanActorPose { int tick,jump,grind,lean; int16_t sin_yaw_q14,cos_yaw_q14; };
void urban_actor_draw(VxpeToonTarget3D*,const VxpeToonCamera3D*,VxpeVec3D position,const UrbanActorPose*,bool shadow,bool render_body=true);
int urban_actor_vertex_count();
int urban_actor_face_count();
