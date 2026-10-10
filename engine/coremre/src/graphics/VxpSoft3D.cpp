/* VxpSoft3D implementation — original clean-room code, see header note. */
#include "graphics/VxpSoft3D.h"
#include <string.h>

namespace {

inline int32_t clamp_i32(int32_t v, int32_t lo, int32_t hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

/* Integer square root (binary restoring), for normal normalization. */
uint32_t isqrt_u64(uint64_t x) {
    uint64_t r = 0, bit = (uint64_t)1 << 62;
    while (bit > x) bit >>= 2;
    while (bit) {
        if (x >= r + bit) { x -= r + bit; r = (r >> 1) + bit; }
        else r >>= 1;
        bit >>= 2;
    }
    return (uint32_t)r;
}

inline uint16_t mix565(uint16_t a, uint16_t b, uint8_t t) {
    /* t: 0 = a, 255 = b. Channel-wise to avoid hue rotation. */
    uint32_t ar = (a >> 11) & 31, ag = (a >> 5) & 63, ab = a & 31;
    uint32_t br = (b >> 11) & 31, bg = (b >> 5) & 63, bb = b & 31;
    uint32_t r = (ar * (255 - t) + br * t + 127) / 255;
    uint32_t g = (ag * (255 - t) + bg * t + 127) / 255;
    uint32_t bl = (ab * (255 - t) + bb * t + 127) / 255;
    return (uint16_t)((r << 11) | (g << 5) | bl);
}

inline uint16_t shade565(uint16_t c, uint8_t illum) {
    uint32_t r = ((c >> 11) & 31) * illum / 255;
    uint32_t g = ((c >> 5) & 63) * illum / 255;
    uint32_t b = (c & 31) * illum / 255;
    return (uint16_t)((r << 11) | (g << 5) | b);
}

uint8_t face_illum(VxpeSoft3DVec a, VxpeSoft3DVec b, VxpeSoft3DVec c,
                   const VxpeSoft3DLight* light) {
    int64_t ux = (int64_t)b.x - a.x, uy = (int64_t)b.y - a.y, uz = (int64_t)b.z - a.z;
    int64_t vx = (int64_t)c.x - a.x, vy = (int64_t)c.y - a.y, vz = (int64_t)c.z - a.z;
    int64_t nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
    uint64_t len2 = (uint64_t)(nx * nx) + (uint64_t)(ny * ny) + (uint64_t)(nz * nz);
    if (!len2) return light->ambient;
    uint32_t len = isqrt_u64(len2);
    int64_t dot = nx * light->x_q14 + ny * light->y_q14 + nz * light->z_q14;
    if (dot < 0) dot = -dot; /* two-sided */
    /* dot is in units of len*16384; NdotL_q8 = dot*256/(len*16384) */
    int64_t ndl = dot * 256 / ((int64_t)len * 16384);
    if (ndl < 0) ndl = 0;
    if (ndl > 256) ndl = 256;
    int64_t ill = (int64_t)light->ambient +
                  (int64_t)light->diffuse * ndl / 256;
    if (ill > 255) ill = 255;
    return (uint8_t)ill;
}

uint16_t apply_fog(uint16_t c, uint16_t z, const VxpeSoft3DMaterial* m) {
    if (m->fog_far_z <= m->fog_near_z) return c;
    if (z <= m->fog_near_z) return c;
    if (z >= m->fog_far_z) return m->fog565;
    uint32_t t = ((uint32_t)(z - m->fog_near_z) * 255) /
                 (m->fog_far_z - m->fog_near_z);
    return mix565(c, m->fog565, (uint8_t)t);
}

struct Proj { int32_t x, y; uint16_t z; uint8_t ok; };

Proj project_pt(const VxpeSoft3DCamera* cam, VxpeSoft3DVec p) {
    Proj r = {0, 0, 0, 0};
    int64_t dx = (int64_t)p.x - cam->position.x;
    int64_t dy = (int64_t)p.y - cam->position.y;
    int64_t dz = (int64_t)p.z - cam->position.z;
    /* yaw-only rotation into camera space */
    int64_t cx = (dx * cam->cos_yaw_q14 + dz * cam->sin_yaw_q14) >> 14;
    int64_t cz = (-dx * cam->sin_yaw_q14 + dz * cam->cos_yaw_q14) >> 14;
    if (cz < (int64_t)cam->near_z || cz > (int64_t)cam->far_z) return r;
    r.x = cam->center_x + (int32_t)((cx * cam->focal_px) / cz);
    r.y = cam->horizon_y - (int32_t)((dy * cam->focal_px) / cz);
    r.z = cz > 65535 ? 65535 : (uint16_t)cz;
    r.ok = 1;
    return r;
}

} // namespace

extern "C" {

void vxpe_soft3d_camera_init(VxpeSoft3DCamera* c, int w, int h) {
    memset(c, 0, sizeof(*c));
    c->center_x = (int16_t)(w / 2);
    c->horizon_y = (int16_t)(h / 2);
    c->focal_px = (uint16_t)(w > 0 ? w : 240);
    c->cos_yaw_q14 = 16384;
    c->near_z = 8;
    c->far_z = 60000;
}

void vxpe_soft3d_material_init(VxpeSoft3DMaterial* m, uint16_t albedo) {
    memset(m, 0, sizeof(*m));
    m->albedo565 = albedo;
    m->fog565 = albedo;
}

void vxpe_soft3d_light_init(VxpeSoft3DLight* l) {
    memset(l, 0, sizeof(*l));
    l->z_q14 = 16384;
    l->ambient = 70;
    l->diffuse = 185;
}

void vxpe_soft3d_clear(VxpeSoft3DTarget* t, uint16_t bg) {
    uint32_t n = (uint32_t)t->width * t->height;
    for (uint32_t i = 0; i < n; ++i) { t->pixels[i] = bg; t->depth[i] = 65535; }
}

void vxpe_soft3d_clear_depth(VxpeSoft3DTarget* t) {
    uint32_t n = (uint32_t)t->width * t->height;
    for (uint32_t i = 0; i < n; ++i) t->depth[i] = 65535;
}

int vxpe_soft3d_project(const VxpeSoft3DCamera* c, VxpeSoft3DVec p, VxpeSoft3DPoint* out) {
    Proj r = project_pt(c, p);
    out->x = r.x; out->y = r.y; out->z = r.z; out->visible = r.ok;
    return r.ok;
}

/* Shared edge-function raster core. Caller supplies per-pixel fill via
 * callback-style inline code paths below (flat vs textured). */
static int raster(const VxpeSoft3DTarget* t, const Proj p[3],
                  int (*shade)(void* ctx, int x, int y, int64_t w0, int64_t w1,
                               int64_t w2, int64_t area, uint16_t z),
                  void* ctx) {
    int64_t area = (int64_t)(p[1].x - p[0].x) * (p[2].y - p[0].y) -
                   (int64_t)(p[2].x - p[0].x) * (p[1].y - p[0].y);
    if (area == 0) return 0;
    int32_t x0 = p[0].x, x1 = p[1].x, x2 = p[2].x;
    int32_t y0 = p[0].y, y1 = p[1].y, y2 = p[2].y;
    int32_t minx = x0 < x1 ? (x0 < x2 ? x0 : x2) : (x1 < x2 ? x1 : x2);
    int32_t maxx = x0 > x1 ? (x0 > x2 ? x0 : x2) : (x1 > x2 ? x1 : x2);
    int32_t miny = y0 < y1 ? (y0 < y2 ? y0 : y2) : (y1 < y2 ? y1 : y2);
    int32_t maxy = y0 > y1 ? (y0 > y2 ? y0 : y2) : (y1 > y2 ? y1 : y2);
    if (minx < 0) minx = 0;
    if (miny < 0) miny = 0;
    if (maxx >= t->width) maxx = t->width - 1;
    if (maxy >= t->height) maxy = t->height - 1;
    if (minx > maxx || miny > maxy) return 0;
    int neg = area < 0 ? 1 : 0;
    int64_t aa = neg ? -area : area;
    int drawn = 0;
    /* Depth plane from screen-space z (affine; exact path uses 1/z below). */
    for (int32_t y = miny; y <= maxy; ++y) {
        for (int32_t x = minx; x <= maxx; ++x) {
            int64_t e0 = (int64_t)(x1 - x0) * (y - y0) - (int64_t)(y1 - y0) * (x - x0);
            int64_t e1 = (int64_t)(x2 - x1) * (y - y1) - (int64_t)(y2 - y1) * (x - x1);
            int64_t e2 = (int64_t)(x0 - x2) * (y - y2) - (int64_t)(y0 - y2) * (x - x2);
            int64_t w0 = neg ? -e1 : e1;
            int64_t w1 = neg ? -e2 : e2;
            int64_t w2 = neg ? -e0 : e0;
            if (w0 < 0 || w1 < 0 || w2 < 0) continue;
            uint32_t z = (uint32_t)(((uint64_t)w0 * p[0].z + (uint64_t)w1 * p[1].z +
                                     (uint64_t)w2 * p[2].z) / (uint64_t)aa);
            if (z > 65535) z = 65535;
            uint32_t idx = (uint32_t)y * t->width + (uint32_t)x;
            if ((uint16_t)z >= t->depth[idx]) continue;
            if (shade(ctx, x, y, w0, w1, w2, aa, (uint16_t)z)) {
                t->depth[idx] = (uint16_t)z;
                ++drawn;
            }
        }
    }
    return drawn;
}

struct FlatCtx {
    VxpeSoft3DTarget* t;
    const VxpeSoft3DMaterial* m;
    uint8_t illum;
};

static int flat_shade(void* vctx, int x, int y, int64_t, int64_t, int64_t,
                      int64_t, uint16_t z) {
    FlatCtx* c = (FlatCtx*)vctx;
    uint16_t col = shade565(c->m->albedo565, c->illum);
    col = apply_fog(col, z, c->m);
    c->t->pixels[(uint32_t)y * c->t->width + (uint32_t)x] = col;
    return 1;
}

int vxpe_soft3d_triangle(VxpeSoft3DTarget* t, const VxpeSoft3DCamera* cam,
    VxpeSoft3DVec a, VxpeSoft3DVec b, VxpeSoft3DVec c,
    const VxpeSoft3DMaterial* m, const VxpeSoft3DLight* light, uint8_t illum) {
    if (!t || !t->pixels || !t->depth || !cam || !m) return 0;
    Proj p[3] = {project_pt(cam, a), project_pt(cam, b), project_pt(cam, c)};
    if (!p[0].ok || !p[1].ok || !p[2].ok) return 0;
    if (m->dither_cutout == 255) return 0;
    FlatCtx ctx = {t, m, light ? face_illum(a, b, c, light) : illum};
    return raster(t, p, flat_shade, &ctx);
}

struct TexCtx {
    VxpeSoft3DTarget* t;
    const VxpeSpriteA8* tex;
    const VxpeSoft3DMaterial* m;
    uint8_t illum;
    /* 1/z fixed point: iz = SCALE/z, iu = u*256/z ... u_q8 already Q8 */
    int64_t iz[3], iu[3], iv[3];
};

static int tex_shade(void* vctx, int x, int y, int64_t w0, int64_t w1,
                     int64_t w2, int64_t area, uint16_t z) {
    TexCtx* c = (TexCtx*)vctx;
    int64_t iz = (w0 * c->iz[0] + w1 * c->iz[1] + w2 * c->iz[2]) / area;
    if (iz <= 0) return 0;
    int64_t iu = (w0 * c->iu[0] + w1 * c->iu[1] + w2 * c->iu[2]) / area;
    int64_t iv = (w0 * c->iv[0] + w1 * c->iv[1] + w2 * c->iv[2]) / area;
    /* Perspective-correct pixel coords: with iu = u_q8*S/z and
     * iz = 256*S/z, iu/iz = u directly (S cancels). No extra shift:
     * an additional S/256 factor here collapsed UVs 16x (flat faces). */
    int32_t tu = (int32_t)(iu / iz);
    int32_t tv = (int32_t)(iv / iz);
    if (tu < 0) tu = 0;
    if (tv < 0) tv = 0;
    if (tu >= c->tex->width) tu = c->tex->width - 1;
    if (tv >= c->tex->height) tv = c->tex->height - 1;
    uint32_t ti = (uint32_t)tv * c->tex->stride + (uint32_t)tu;
    uint8_t alpha = c->tex->alpha ? c->tex->alpha[ti] : 255;
    if (alpha < 128) return 0; /* transparent: keep color AND depth */
    uint16_t texel = c->tex->pixels[ti];
    uint16_t col = shade565(texel, c->illum);
    col = apply_fog(col, z, c->m);
    c->t->pixels[(uint32_t)y * c->t->width + (uint32_t)x] = col;
    return 1;
}

static void fill_texctx(TexCtx* c, const VxpeSoft3DVertex v[3],
                        const VxpeSoft3DCamera* cam, const Proj p[3]) {
    (void)cam;
    const int64_t S = (int64_t)1 << 20;
    for (int i = 0; i < 3; ++i) {
        /* z from projection; vertices share camera so recompute cheaply */
        uint32_t z = p[i].z ? p[i].z : 1;
        c->iz[i] = S * 256 / z;
        c->iu[i] = v[i].u_q8 * S / (int64_t)z;
        c->iv[i] = v[i].v_q8 * S / (int64_t)z;
    }
}

int vxpe_soft3d_triangle_textured(VxpeSoft3DTarget* t, const VxpeSoft3DCamera* cam,
    const VxpeSoft3DVertex v[3], const VxpeSpriteA8* tex,
    const VxpeSoft3DMaterial* m, const VxpeSoft3DLight* light, uint8_t illum) {
    if (!t || !t->pixels || !t->depth || !cam || !m || !tex) return 0;
    Proj p[3] = {project_pt(cam, v[0].position), project_pt(cam, v[1].position),
                 project_pt(cam, v[2].position)};
    if (!p[0].ok || !p[1].ok || !p[2].ok) return 0;
    if (m->dither_cutout == 255) return 0;
    TexCtx ctx;
    ctx.t = t;
    ctx.tex = tex;
    ctx.m = m;
    ctx.illum = light ? face_illum(v[0].position, v[1].position, v[2].position, light)
                      : illum;
    fill_texctx(&ctx, v, cam, p);
    return raster(t, p, tex_shade, &ctx);
}

static int mesh_common(VxpeSoft3DTarget* t, const VxpeSoft3DCamera* cam,
    const VxpeSoft3DVertex* verts, const uint32_t* idx, uint32_t faces,
    const uint8_t* illum, const VxpeSpriteA8* tex,
    const VxpeSoft3DMaterial* m, const VxpeSoft3DLight* light) {
    int total = 0;
    for (uint32_t f = 0; f < faces; ++f) {
        uint8_t il = illum ? illum[f] : 255;
        if (tex) {
            VxpeSoft3DVertex v[3] = {verts[idx[f * 3]], verts[idx[f * 3 + 1]],
                                     verts[idx[f * 3 + 2]]};
            total += vxpe_soft3d_triangle_textured(t, cam, v, tex, m, light, il);
        } else {
            total += vxpe_soft3d_triangle(t, cam, verts[idx[f * 3]].position,
                                          verts[idx[f * 3 + 1]].position,
                                          verts[idx[f * 3 + 2]].position, m,
                                          light, il);
        }
    }
    return total;
}

int vxpe_soft3d_mesh16(VxpeSoft3DTarget* t, const VxpeSoft3DCamera* cam,
    const VxpeSoft3DMesh16* mesh, const VxpeSpriteA8* tex,
    const VxpeSoft3DMaterial* m, const VxpeSoft3DLight* light) {
    if (!mesh || !mesh->vertices || !mesh->indices) return 0;
    /* widen indices once into a scratch-free streaming loop (no heap) */
    int total = 0;
    for (uint32_t f = 0; f < mesh->face_count; ++f) {
        uint32_t idx[3] = {mesh->indices[f * 3], mesh->indices[f * 3 + 1],
                           mesh->indices[f * 3 + 2]};
        if (idx[0] >= mesh->vertex_count || idx[1] >= mesh->vertex_count ||
            idx[2] >= mesh->vertex_count)
            continue;
        uint8_t il = (mesh->illumination) ? mesh->illumination[f] : 255;
        if (tex) {
            VxpeSoft3DVertex v[3] = {mesh->vertices[idx[0]],
                                     mesh->vertices[idx[1]],
                                     mesh->vertices[idx[2]]};
            total += vxpe_soft3d_triangle_textured(t, cam, v, tex, m, light, il);
        } else {
            total += vxpe_soft3d_triangle(t, cam, mesh->vertices[idx[0]].position,
                                          mesh->vertices[idx[1]].position,
                                          mesh->vertices[idx[2]].position, m,
                                          light, il);
        }
    }
    return total;
}

int vxpe_soft3d_mesh32(VxpeSoft3DTarget* t, const VxpeSoft3DCamera* cam,
    const VxpeSoft3DMesh32* mesh, const VxpeSpriteA8* tex,
    const VxpeSoft3DMaterial* m, const VxpeSoft3DLight* light) {
    if (!mesh || !mesh->vertices || !mesh->indices) return 0;
    return mesh_common(t, cam, mesh->vertices, mesh->indices, mesh->face_count,
                       mesh->illumination, tex, m, light);
}

/* Moller-Trumbore with Q14 direction. Host-side bake use. */
int vxpe_soft3d_ray_triangle(int32_t orig[3], int32_t dir_q14[3],
    VxpeSoft3DVec a, VxpeSoft3DVec b, VxpeSoft3DVec c, int32_t* t_q8) {
    /* Convert to double-free float math on host for robustness; device never
     * calls this (bake tool only). Float is fine for offline baking. */
    float o[3] = {(float)orig[0], (float)orig[1], (float)orig[2]};
    float d[3] = {(float)dir_q14[0] / 16384.0f, (float)dir_q14[1] / 16384.0f,
                  (float)dir_q14[2] / 16384.0f};
    float e1[3] = {(float)(b.x - a.x), (float)(b.y - a.y), (float)(b.z - a.z)};
    float e2[3] = {(float)(c.x - a.x), (float)(c.y - a.y), (float)(c.z - a.z)};
    float p[3] = {d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2],
                  d[0] * e2[1] - d[1] * e2[0]};
    float det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2];
    if (det > -1e-6f && det < 1e-6f) return 0;
    float inv = 1.0f / det;
    float tv[3] = {o[0] - (float)a.x, o[1] - (float)a.y, o[2] - (float)a.z};
    float u = (tv[0] * p[0] + tv[1] * p[1] + tv[2] * p[2]) * inv;
    if (u < 0.0f || u > 1.0f) return 0;
    float q[3] = {tv[1] * e1[2] - tv[2] * e1[1], tv[2] * e1[0] - tv[0] * e1[2],
                  tv[0] * e1[1] - tv[1] * e1[0]};
    float w = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) * inv;
    if (w < 0.0f || u + w > 1.0f) return 0;
    float dist = (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) * inv;
    if (dist <= 0.0f) return 0;
    if (t_q8) *t_q8 = (int32_t)(dist * 256.0f);
    return 1;
}

void vxpe_soft3d_bake_vertex_light(const VxpeSoft3DVec* pos,
    const VxpeSoft3DVec* nrm, const uint8_t* shadow,
    uint8_t* out, uint32_t count, const VxpeSoft3DLight* light) {
    if (!pos || !nrm || !out || !light) return;
    for (uint32_t i = 0; i < count; ++i) {
        int64_t nx = nrm[i].x, ny = nrm[i].y, nz = nrm[i].z;
        uint64_t len2 = (uint64_t)(nx * nx) + (uint64_t)(ny * ny) +
                        (uint64_t)(nz * nz);
        int64_t ndl = 0;
        if (len2) {
            uint32_t len = isqrt_u64(len2);
            int64_t dot = nx * light->x_q14 + ny * light->y_q14 +
                          nz * light->z_q14;
            if (dot < 0) dot = -dot;
            ndl = dot * 256 / ((int64_t)len * 16384);
            if (ndl < 0) ndl = 0;
            if (ndl > 256) ndl = 256;
        }
        int64_t ill = (int64_t)light->ambient + (int64_t)light->diffuse * ndl / 256;
        if (shadow) ill = ill * (255 - shadow[i]) / 255;
        if (ill > 255) ill = 255;
        out[i] = (uint8_t)ill;
    }
}

} // extern "C"
