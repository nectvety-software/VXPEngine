/* Bench toi thieu de do chi phi fill cua bau troi tren ARM.
 *
 * Khong co OS, khong libc: chi mot vung dem 120x160 va hai ham entry, moi ham
 * chay vong lap `iters` lan roi nhay vao bench_halt de trinh mo phong dung lai.
 */
#include <stdint.h>
#include "graphics/VxpRender2D.h"

static uint16_t skybuf[120 * 160];

extern "C" void bench_halt(void) { for (;;) { } }

extern "C" uint32_t bench_sky_plain(uint32_t iters) {
    const uint16_t top = vxpe2d_rgb565(5, 53, 180);
    const uint16_t bottom = vxpe2d_rgb565(137, 218, 222);
    for (uint32_t i = 0; i < iters; ++i) {
        vxpe2d_gradient_vertical(skybuf, 120, 160, 0, 0, 120, 160, top, bottom);
    }
    bench_halt();
    return skybuf[iters % (120 * 160)];
}

extern "C" uint32_t bench_sky_dither(uint32_t iters) {
    const uint16_t top = vxpe2d_rgb565(5, 53, 180);
    const uint16_t bottom = vxpe2d_rgb565(137, 218, 222);
    for (uint32_t i = 0; i < iters; ++i) {
        vxpe2d_gradient_vertical_dithered(skybuf, 120, 160, 0, 0, 120, 160, top, bottom);
    }
    bench_halt();
    return skybuf[iters % (120 * 160)];
}
