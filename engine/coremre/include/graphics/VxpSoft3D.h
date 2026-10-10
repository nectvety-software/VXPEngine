/* Clean-room soft 3D rasterizer for MRE VXP (RGB565, fixed-point, C API).
 *
 * NOTE ON PROVENANCE (clean-room):
 * The pipeline organization here (vertex transform -> near-clip reject ->
 * edge-function raster -> 16-bit depth test -> perspective-correct UV via 1/z
 * -> nearest RGB565 sampling -> flat/Gouraud light -> distance fog) follows
 * ideas described in the public YMGRE documentation (C99 CPU engine with
 * rasterization, depth buffering, texture sampling, lighting, and offline
 * texture baking). No YMGRE source is bundled, quoted, or translated: every
 * line below is an original implementation for the VXPEngine `vxpstore`
 * core, sized for 240x320 MRE screens and ARMv5TE without FPU.
 * YMGRE itself is distributed under a noncommercial license requiring
 * separate commercial authorization; this module does not change that.
 *
 * Conventions mirror the rest of coremre: caller owns all buffers, no heap
 * use on the render path, Q14/Q8 fixed point, C-linkage API.
 */
#pragma once
#include <stdint.h>
#include "graphics/VxpSpriteFx.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeSoft3DVec { int32_t x, y, z; } VxpeSoft3DVec;

typedef struct VxpeSoft3DTarget {
    uint16_t* pixels; /* width*height RGB565 */
    uint16_t* depth;  /* width*height entries, nearer = smaller z; clear to 65535 */
    uint16_t width, height;
} VxpeSoft3DTarget;

typedef struct VxpeSoft3DCamera {
    VxpeSoft3DVec position;
    int16_t sin_yaw_q14, cos_yaw_q14; /* normalized pair; 0/16384 faces +Z */
    int16_t center_x, horizon_y;
    uint16_t focal_px, near_z, far_z; /* 1 <= near < far <= 65534 */
} VxpeSoft3DCamera;

typedef struct VxpeSoft3DMaterial {
    uint16_t albedo565, fog565;
    uint16_t fog_near_z, fog_far_z; /* fog_far <= fog_near disables fog */
    uint8_t dither_cutout;          /* mesh coverage: 0 opaque, 255 invisible */
} VxpeSoft3DMaterial;

typedef struct VxpeSoft3DLight {
    int16_t x_q14, y_q14, z_q14; /* normalized direction TOWARDS the light */
    uint8_t ambient;             /* 0..255 floor */
    uint8_t diffuse;             /* 0..255 scale of NdotL */
} VxpeSoft3DLight;

typedef struct VxpeSoft3DPoint {
    int32_t x, y;      /* screen pixels */
    uint16_t z;        /* camera-space depth */
    uint8_t visible;   /* 0 when behind near plane / beyond far */
} VxpeSoft3DPoint;

typedef struct VxpeSoft3DVertex {
    VxpeSoft3DVec position;
    int32_t u_q8, v_q8; /* texture pixel coordinates Q8; nearest sampling */
} VxpeSoft3DVertex;

typedef struct VxpeSoft3DFace {
    uint32_t indices[3]; /* widened: mesh16 stores uint16_t, mesh32 uint32_t */
    uint8_t illumination;/* 0..255 precomputed light (flat path) */
    uint8_t edge_mask;   /* reserved, set 0 */
} VxpeSoft3DFace;

typedef struct VxpeSoft3DMesh16 {
    const VxpeSoft3DVertex* vertices;
    const uint16_t* indices;      /* face_count*3 */
    const uint8_t* illumination;  /* optional per-face 0..255, may be NULL */
    uint16_t vertex_count;
    uint16_t face_count;
} VxpeSoft3DMesh16;

typedef struct VxpeSoft3DMesh32 {
    const VxpeSoft3DVertex* vertices;
    const uint32_t* indices;      /* face_count*3; 16/32-bit index switch */
    const uint8_t* illumination;
    uint32_t vertex_count;
    uint32_t face_count;
} VxpeSoft3DMesh32;

void vxpe_soft3d_camera_init(VxpeSoft3DCamera*, int width, int height);
void vxpe_soft3d_material_init(VxpeSoft3DMaterial*, uint16_t albedo565);
void vxpe_soft3d_light_init(VxpeSoft3DLight*);
void vxpe_soft3d_clear(VxpeSoft3DTarget*, uint16_t background565);
void vxpe_soft3d_clear_depth(VxpeSoft3DTarget*);

/* World -> screen. Returns 0 when rejected by near/far planes. */
int vxpe_soft3d_project(const VxpeSoft3DCamera*, VxpeSoft3DVec, VxpeSoft3DPoint*);

/* Flat-shaded triangle (affine depth, integer Lambert when light != NULL). */
int vxpe_soft3d_triangle(VxpeSoft3DTarget*, const VxpeSoft3DCamera*,
    VxpeSoft3DVec a, VxpeSoft3DVec b, VxpeSoft3DVec c,
    const VxpeSoft3DMaterial*, const VxpeSoft3DLight*, uint8_t illumination);

/* Perspective-correct UV (1/z interpolation), RGB565+A8 nearest sampling.
 * Fully transparent texels leave framebuffer and depth unchanged. */
int vxpe_soft3d_triangle_textured(VxpeSoft3DTarget*, const VxpeSoft3DCamera*,
    const VxpeSoft3DVertex v[3], const VxpeSpriteA8*,
    const VxpeSoft3DMaterial*, const VxpeSoft3DLight*, uint8_t illumination);

/* Indexed meshes. illumination array overrides light when non-NULL. */
int vxpe_soft3d_mesh16(VxpeSoft3DTarget*, const VxpeSoft3DCamera*,
    const VxpeSoft3DMesh16*, const VxpeSpriteA8* /*may be NULL*/,
    const VxpeSoft3DMaterial*, const VxpeSoft3DLight*);
int vxpe_soft3d_mesh32(VxpeSoft3DTarget*, const VxpeSoft3DCamera*,
    const VxpeSoft3DMesh32*, const VxpeSpriteA8* /*may be NULL*/,
    const VxpeSoft3DMaterial*, const VxpeSoft3DLight*);

/* ---- Host-side bake helpers (NOT for the MRE render path) ----
 * Moller-Trumbore ray/triangle test in plain integers/floats for an offline
 * baking tool: cast shadow rays on the host, store the result as per-vertex
 * illumination or a lightmap, and ship only baked data to the device.
 * Returns 1 on hit (t_q8 > 0 set), 0 otherwise. */
int vxpe_soft3d_ray_triangle(int32_t orig[3], int32_t dir_q14[3],
    VxpeSoft3DVec a, VxpeSoft3DVec b, VxpeSoft3DVec c, int32_t* t_q8);

/* Bake per-vertex illumination: illum = ambient + diffuse*max(0,NdotL),
 * multiplied by (255-shadow)/255 when shadow != NULL. Pure integer. */
void vxpe_soft3d_bake_vertex_light(const VxpeSoft3DVec* positions,
    const VxpeSoft3DVec* normals, const uint8_t* shadow,
    uint8_t* out_illum, uint32_t count, const VxpeSoft3DLight*);

#ifdef __cplusplus
}
#endif
