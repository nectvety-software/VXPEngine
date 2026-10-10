/* Bench toi thieu de do chi phi fill cua thap tren ARM.
 *
 * Link voi mot trong cac bien the scene trong gen/: tower_now, tower_flat,
 * tower_prev. Moi lan goi bench_run = mot khung world (sky + clear depth +
 * nam arcology), khong HUD, khong scale2x.
 *
 * scene.h khai bao renderWorld() la private; harness nay chi goi no nen dung
 * thu thuat `#define private public` co gioi han trong dung TU do.
 */
#include <stdint.h>
#include "graphics/VxpToon3D.h"
#include "graphics/VxpRender2D.h"

#define private public
#include "scene.h"
#undef private

extern "C" void bench_halt(void) { for (;;) { } }

extern "C" uint32_t bench_run(uint32_t iters) {
    static PromisedFuture game;
    for (uint32_t i = 0; i < iters; ++i) {
        game.renderWorld();
    }
    bench_halt();
    return (uint32_t)game.worldPixels[0] + (uint32_t)game.wallDepth[3];
}
