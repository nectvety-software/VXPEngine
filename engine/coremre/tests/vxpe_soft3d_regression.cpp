// Clean-room soft-3D regression: flat, textured, mesh16/32, ray, bake.
#include "graphics/VxpSoft3D.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

static int count_nonzero(const uint16_t* px, int n, uint16_t bg) {
    int c = 0;
    for (int i = 0; i < n; ++i) if (px[i] != bg) ++c;
    return c;
}

int main() {
    const int W = 64, H = 64;
    static uint16_t pixels[64 * 64], depth[64 * 64];
    VxpeSoft3DTarget tgt = {pixels, depth, W, H};
    VxpeSoft3DCamera cam;
    VxpeSoft3DMaterial mat;
    VxpeSoft3DLight light;
    vxpe_soft3d_camera_init(&cam, W, H);
    vxpe_soft3d_material_init(&mat, 0xF800); // red
    vxpe_soft3d_light_init(&light);

    // 1. flat quad (two tris) covers center
    vxpe_soft3d_clear(&tgt, 0x0000);
    VxpeSoft3DVec q[4] = {{-10, 10, 40}, {10, 10, 40}, {10, -10, 40}, {-10, -10, 40}};
    int n0 = vxpe_soft3d_triangle(&tgt, &cam, q[0], q[1], q[2], &mat, &light, 255);
    int n1 = vxpe_soft3d_triangle(&tgt, &cam, q[0], q[2], q[3], &mat, &light, 255);
    assert(n0 > 0 && n1 > 0);
    assert(count_nonzero(pixels, W * H, 0x0000) > 100);
    // depth nearer wins: far quad behind must not overwrite (depth smaller = nearer)
    uint16_t center_before = pixels[(H / 2) * W + (W / 2)];
    VxpeSoft3DVec far[3] = {{-10, 10, 80}, {10, 10, 80}, {0, -10, 80}};
    vxpe_soft3d_triangle(&tgt, &cam, far[0], far[1], far[2], &mat, nullptr, 255);
    assert(pixels[(H / 2) * W + (W / 2)] == center_before);

    // 2. textured perspective-correct: white 2x2 texture, check center lit
    static uint16_t texpx[4] = {0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF};
    static uint8_t texa[4] = {255, 255, 255, 255};
    VxpeSpriteA8 tex = {texpx, texa, 2, 2, 2, 2, 0};
    vxpe_soft3d_clear(&tgt, 0x0000);
    VxpeSoft3DVertex tv[3] = {{{-10, 10, 40}, 0, 0},
                              {{10, 10, 40}, 1 * 256, 0},
                              {{0, -10, 40}, 0, 1 * 256}};
    int nt = vxpe_soft3d_triangle_textured(&tgt, &cam, tv, &tex, &mat, nullptr, 255);
    assert(nt > 0);
    // UV correctness: 2x1 red|blue texture must show BOTH colors
    // (catches scaling bugs that collapse UVs to one texel).
    static uint16_t texpx2[2] = {0xF800, 0x001F};
    static uint8_t texa2[2] = {255, 255};
    VxpeSpriteA8 tex2 = {texpx2, texa2, 2, 1, 2, 2, 0};
    vxpe_soft3d_clear(&tgt, 0x0000);
    VxpeSoft3DVertex tv2[3] = {{{-10, 10, 40}, 0, 0},
                               {{10, 10, 40}, 1 * 256, 0},
                               {{0, -10, 40}, 0, 0}};
    assert(vxpe_soft3d_triangle_textured(&tgt, &cam, tv2, &tex2, &mat, nullptr, 255) > 0);
    {
        int reds = 0, blues = 0;
        for (int i = 0; i < W * H; ++i) {
            uint16_t shaded_r = (uint16_t)(((0xF800u >> 11) * 255 / 255) << 11);
            if (pixels[i] == shaded_r) ++reds;
            if (pixels[i] == 0x001F) ++blues;
        }
        assert(reds > 0 && blues > 0);
    }
    // transparent texel path: alpha 0 quad of texture must leave bg
    static uint8_t texa0[4] = {0, 0, 0, 0};
    VxpeSpriteA8 tex0 = {texpx, texa0, 2, 2, 2, 2, 0};
    vxpe_soft3d_clear(&tgt, 0x1234);
    int nt0 = vxpe_soft3d_triangle_textured(&tgt, &cam, tv, &tex0, &mat, nullptr, 255);
    assert(nt0 == 0);
    assert(count_nonzero(pixels, W * H, 0x1234) == 0);

    // 3. mesh16 + mesh32 (16/32-bit index switch)
    VxpeSoft3DVertex mv[4] = {{{-10, 10, 40}, 0, 0}, {{10, 10, 40}, 0, 0},
                              {{10, -10, 40}, 0, 0}, {{-10, -10, 40}, 0, 0}};
    static const uint16_t idx16[6] = {0, 1, 2, 0, 2, 3};
    VxpeSoft3DMesh16 m16 = {mv, idx16, nullptr, 4, 2};
    vxpe_soft3d_clear(&tgt, 0x0000);
    int m16n = vxpe_soft3d_mesh16(&tgt, &cam, &m16, nullptr, &mat, nullptr);
    assert(m16n > 0);
    static const uint32_t idx32[6] = {0, 1, 2, 0, 2, 3};
    VxpeSoft3DMesh32 m32 = {mv, idx32, nullptr, 4, 2};
    vxpe_soft3d_clear(&tgt, 0x0000);
    int m32n = vxpe_soft3d_mesh32(&tgt, &cam, &m32, nullptr, &mat, nullptr);
    assert(m32n == m16n);

    // 4. ray/triangle: straight-on ray hits, parallel misses
    {
        int32_t o[3] = {0, 0, 0};
        int32_t d[3] = {0, 0, 16384};
        VxpeSoft3DVec a = {-10, -10, 40}, b = {10, -10, 40}, c = {0, 10, 40};
        int32_t tq = 0;
        assert(vxpe_soft3d_ray_triangle(o, d, a, b, c, &tq) == 1);
        assert(tq > 0);
        int32_t d2[3] = {16384, 0, 0};
        assert(vxpe_soft3d_ray_triangle(o, d2, a, b, c, nullptr) == 0);
    }

    // 5. bake: up normal + overhead light => full, shadow halves
    {
        VxpeSoft3DVec pos[1] = {{0, 0, 0}};
        VxpeSoft3DVec nrm[1] = {{0, 0, 16384}};
        uint8_t out[1] = {0};
        VxpeSoft3DLight bl;
        vxpe_soft3d_light_init(&bl); // ambient 70, diffuse 185, +Z
        vxpe_soft3d_bake_vertex_light(pos, nrm, nullptr, out, 1, &bl);
        assert(out[0] == 255);
        uint8_t sh[1] = {128};
        vxpe_soft3d_bake_vertex_light(pos, nrm, sh, out, 1, &bl);
        assert(out[0] < 255 && out[0] > 0);
    }

    std::printf("soft3d regression OK\n");
    return 0;
}
