/* Fixed-memory RGB565 raycaster for low-power MRE devices. */
#pragma once
#include <stdint.h>
#include "graphics/VxpSpriteFx.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeRaycastTexture {
    const uint16_t* pixels;
    uint8_t width,height,stride;
} VxpeRaycastTexture;

typedef struct VxpeRaycastMap {
    const uint8_t* walls; /* 0=open, 1..wall_count = wall texture index + 1 */
    uint8_t width,height,stride;
} VxpeRaycastMap;

typedef struct VxpeRaycastCamera {
    int32_t x_q8,z_q8;             /* world position; one map cell is 256 */
    int16_t dir_x_q14,dir_z_q14;  /* normalized forward direction */
    int16_t plane_x_q14,plane_z_q14; /* perpendicular camera plane; controls FOV */
    int16_t horizon_y;
    uint16_t focal_px,eye_height_q8,max_distance_q8;
} VxpeRaycastCamera;

typedef struct VxpeRaycastScene {
    VxpeRaycastMap map;
    const VxpeRaycastTexture* wall_textures;
    uint8_t wall_count;
    VxpeRaycastTexture floor_texture,ceiling_texture;
    uint16_t sky565,fog565;
    uint16_t fog_near_q8,fog_far_q8;
    uint8_t fog_strength,dither_strength;
} VxpeRaycastScene;

typedef struct VxpeRaycastTarget {
    uint16_t* pixels;
    uint16_t width,height,stride;
    uint16_t* wall_depth_q8; /* caller-owned width entries; may be null */
} VxpeRaycastTarget;

typedef struct VxpeRaycastBillboard {
    int32_t x_q8,z_q8,bottom_y_q8;
    uint16_t width_q8,height_q8;
    uint16_t tint565;
    uint8_t alpha;
} VxpeRaycastBillboard;

void vxpe_raycast3d_camera_init(VxpeRaycastCamera*,int width,int height,int horizon_y,int focal_px);
int vxpe_raycast3d_render(VxpeRaycastTarget*,const VxpeRaycastCamera*,const VxpeRaycastScene*);
int vxpe_raycast3d_billboard(VxpeRaycastTarget*,const VxpeRaycastCamera*,const VxpeSpriteA8*,const VxpeRaycastBillboard*);

#ifdef __cplusplus
}
#endif
