/* Allocation-free RGB565 low-poly/cel renderer. C API; caller owns depth buffer. */
#pragma once
#include <stdint.h>
#include "graphics/VxpSpriteFx.h"
#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeVec3D { int32_t x,y,z; } VxpeVec3D;
typedef struct VxpeToonCamera3D {
    VxpeVec3D position;
    int16_t sin_yaw_q14,cos_yaw_q14; /* normalized pair, 0 / 16384 faces +Z */
    int16_t center_x,horizon_y;
    uint16_t focal_px,near_z,far_z; /* 1 <= near < far <= 65534 */
    int16_t sin_pitch_q14,cos_pitch_q14; /* positive pitch looks down; 0/0 = legacy identity */
} VxpeToonCamera3D;
typedef struct VxpeToonMaterial3D {
    uint16_t albedo565,ink565,fog565;
    uint16_t fog_near_z,fog_far_z;
    uint8_t shadow_threshold,highlight_threshold;
    uint8_t shadow_q8,midtone_q8,highlight_q8;
    uint8_t outline_px,fog_alpha;
    uint8_t texture_wrap; /* 0 clamp, 1 repeat; supports signed UV */
} VxpeToonMaterial3D;
typedef struct VxpeToonTarget3D {
    uint16_t* pixels;
    uint16_t* depth; /* width*height entries; clear to 65535 every frame */
    uint16_t width,height;
} VxpeToonTarget3D;
typedef struct VxpeToonPoint3D { int32_t x,y; uint16_t z; uint8_t visible; } VxpeToonPoint3D;
typedef struct VxpeToonVertex3D {
    VxpeVec3D position;
    int32_t u_q8,v_q8; /* texture pixel coordinates Q8; nearest sampling, clamped */
} VxpeToonVertex3D;
typedef struct VxpeToonTransform3D {
    VxpeVec3D position;
    int16_t basis_q14[9]; /* row-major 3x3 rotation */
    uint16_t scale_q8;
} VxpeToonTransform3D;
typedef struct VxpeToonLight3D {
    int16_t x_q14,y_q14,z_q14; /* normalized direction towards the light */
    uint8_t ambient,diffuse;
} VxpeToonLight3D;
typedef struct VxpeToonMeshFace3D {
    uint16_t indices[3],material;
    uint8_t edge_mask,illumination;
} VxpeToonMeshFace3D;
typedef struct VxpeToonMesh3D {
    const VxpeToonVertex3D* vertices;
    const VxpeToonMeshFace3D* faces;
    const VxpeToonMaterial3D* materials;
    const VxpeSpriteA8* const* textures; /* optional, material_count pointers */
    uint16_t vertex_count,face_count,material_count;
} VxpeToonMesh3D;
typedef enum VxpeToonCull3D { VXPE_TOON_CULL_NONE=0,VXPE_TOON_CULL_BACK=1,VXPE_TOON_CULL_FRONT=2 } VxpeToonCull3D;

void vxpe_toon3d_camera_init(VxpeToonCamera3D*,int width,int height);
void vxpe_toon3d_material_init(VxpeToonMaterial3D*,uint16_t albedo565);
void vxpe_toon3d_transform_init(VxpeToonTransform3D*);
VxpeVec3D vxpe_toon3d_transform_point(const VxpeToonTransform3D*,VxpeVec3D);
void vxpe_toon3d_light_init(VxpeToonLight3D*);
uint8_t vxpe_toon3d_face_light(VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,const VxpeToonLight3D*);
/* Indexed mesh with optional directional lighting and face culling. No allocations.
 * For silhouette ink, draw an expanded mesh with CULL_FRONT / black material,
 * then the original mesh with CULL_BACK. Shared triangle diagonals need no ink. */
int vxpe_toon3d_mesh(VxpeToonTarget3D*,const VxpeToonCamera3D*,const VxpeToonMesh3D*,
    const VxpeToonTransform3D*,const VxpeToonLight3D*,VxpeToonCull3D);
void vxpe_toon3d_clear(VxpeToonTarget3D*,uint16_t background565);
uint16_t vxpe_toon3d_shade(const VxpeToonMaterial3D*,uint8_t illumination);
int vxpe_toon3d_project(const VxpeToonCamera3D*,VxpeVec3D,VxpeToonPoint3D*);
/* illumination 0..255 chooses one of three flat bands. Winding is two-sided.
 * edge_mask: bit0=A-B, bit1=B-C, bit2=C-A. Set 0 to avoid internal mesh seams. */
int vxpe_toon3d_triangle(VxpeToonTarget3D*,const VxpeToonCamera3D*,
    VxpeVec3D a,VxpeVec3D b,VxpeVec3D c,const VxpeToonMaterial3D*,uint8_t illumination,uint8_t edge_mask);
/* Vertices ordered around a convex, planar quad; shared diagonal has no ink. */
int vxpe_toon3d_quad(VxpeToonTarget3D*,const VxpeToonCamera3D*,
    const VxpeVec3D vertices[4],const VxpeToonMaterial3D*,uint8_t illumination);
/* Perspective-correct UV, RGB565+A8, albedo tint, the same bands/ink/depth/fog.
 * Fully transparent texels leave both framebuffer and depth unchanged. */
int vxpe_toon3d_triangle_textured(VxpeToonTarget3D*,const VxpeToonCamera3D*,
    const VxpeToonVertex3D vertices[3],const VxpeSpriteA8*,const VxpeToonMaterial3D*,uint8_t illumination,uint8_t edge_mask);
int vxpe_toon3d_quad_textured(VxpeToonTarget3D*,const VxpeToonCamera3D*,
    const VxpeToonVertex3D vertices[4],const VxpeSpriteA8*,const VxpeToonMaterial3D*,uint8_t illumination);
/* Bottom-centred, camera-facing sprite. Binary A8 coverage at 128, depth tested,
 * nearest sampling, palette-preserving cel shade and external silhouette ink. */
int vxpe_toon3d_billboard(VxpeToonTarget3D*,const VxpeToonCamera3D*,
    VxpeVec3D bottom_center,uint16_t world_w,uint16_t world_h,
    const VxpeSpriteA8*,const VxpeToonMaterial3D*,uint8_t illumination);

#ifdef __cplusplus
}
#endif
