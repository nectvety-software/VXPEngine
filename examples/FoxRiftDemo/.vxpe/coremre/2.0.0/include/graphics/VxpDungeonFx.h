/* Fixed-memory dungeon lighting and animated mana sky. C API. */
#pragma once
#include "graphics/VxpToon3D.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct VxpeDungeonLight3D { VxpeVec3D position; uint16_t color565,radius; uint8_t intensity; } VxpeDungeonLight3D;
/* Bounded to 16 lights; squared radial attenuation, ambient 0..255. */
uint16_t vxpe_dungeon_light565(VxpeVec3D point,uint16_t albedo,uint8_t ambient,const VxpeDungeonLight3D* lights,unsigned count);
/* Caller-owned RGB565 viewport; deterministic frame animation, no allocation. */
void vxpe_dungeon_mana_sky(uint16_t* pixels,int width,int height,unsigned frame);
#ifdef __cplusplus
}
#endif
