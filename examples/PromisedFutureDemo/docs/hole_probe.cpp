/* Measure interior "sky" holes in the world buffer after one in-game frame.
 *
 * The sky is a pure vertical gradient, so we regenerate the identical gradient
 * into a reference buffer and treat exact matches as uncovered background.
 * A background pixel that has non-background pixels on both sides in the same
 * row, inside the near-left tower's screen column, is a hole: nothing was drawn
 * there while the object on either side was.
 *
 * Build twice: against ../src/scene.cpp (current, culled) and against
 * scene_ab.cpp (pre-fix, all rings submitted) to see what the culling changed.
 */
#include "scene.h"
#include "graphics/VxpRender2D.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static uint16_t skyRef[120 * 160];
static uint16_t fb[240 * 320];

static uint16_t rgb565(int r, int g, int b) { return vxpe2d_rgb565((uint8_t)r, (uint8_t)g, (uint8_t)b); }

/* Tower at world x=-175, z=385, radius<=73 projects into screen x < 40 of the
 * 120-wide world buffer; the next object on that side is far below the horizon. */
#define TOWER_XMAX 40
#define SIDE_WINDOW 70

static int holeCount(const uint16_t* px, int* minY, int* maxY, int* holeX, int* holeY, int maxHoles, int* xsum) {
    int holes = 0, sx = 0;
    *minY = 1000; *maxY = -1;
    for (int y = 0; y < 160; ++y) {
        for (int x = 1; x < TOWER_XMAX; ++x) {
            if (px[y * 120 + x] != skyRef[y * 120 + x]) continue;
            bool left = false, right = false;
            for (int k = 1; k <= SIDE_WINDOW; ++k) {
                if (x - k < 0) break;
                if (px[y * 120 + x - k] != skyRef[y * 120 + x - k]) { left = true; break; }
            }
            for (int k = 1; k <= SIDE_WINDOW; ++k) {
                if (x + k >= TOWER_XMAX) break;
                if (px[y * 120 + x + k] != skyRef[y * 120 + x + k]) { right = true; break; }
            }
            if (!(left && right)) continue;
            ++holes; sx += x;
            if (y < *minY) *minY = y;
            if (y > *maxY) *maxY = y;
            if (holes <= maxHoles) { holeX[holes - 1] = x; holeY[holes - 1] = y; }
        }
    }
    *xsum = holes ? sx / holes : 0;
    return holes;
}

static int coveredCount(const uint16_t* px) {
    int c = 0;
    for (int i = 0; i < 120 * 160; ++i) if (px[i] != skyRef[i]) ++c;
    return c;
}

int main(int argc, char** argv) {
    const char* label = argc > 1 ? argv[1] : "variant";
    const char* out = argc > 2 ? argv[2] : 0;

    vxpe2d_gradient_vertical(skyRef, 120, 160, 0, 0, 120, 160, rgb565(5, 53, 180), rgb565(137, 218, 222));

    static PromisedFuture game;
    game.input(5);                /* enter the city */
    game.update();
    game.draw(fb);

    int minY = 0, maxY = 0, xsum = 0;
    int hx[512], hy[512];
    int holes = holeCount(game.worldPixels, &minY, &maxY, hx, hy, 512, &xsum);

    printf("[%s] covered=%d  interior-sky-holes=%d  rows=%d..%d  mean-x=%d\n",
           label, coveredCount(game.worldPixels), holes, minY, maxY, xsum);
    for (int i = 0; i < holes && i < 24; ++i) printf("   hole %2d: (%d,%d)\n", i, hx[i], hy[i]);

    /* Exact per-pixel map of the tower column so the shape can be inspected
     * without an image viewer: '#' drawn, '.' background, 'H' hole. */
    printf("map (world rows 40..92, x 0..59):\n     %s\n", "012345678901234567890123456789012345678901234567890123456789");
    for (int y = 40; y <= 92; ++y) {
        char row[64];
        for (int x = 0; x < 60; ++x) {
            bool sky = game.worldPixels[y * 120 + x] == skyRef[y * 120 + x];
            row[x] = sky ? '.' : '#';
        }
        row[60] = 0;
        for (int i = 0; i < holes && i < 512; ++i) if (hy[i] == y && hx[i] < 60) row[hx[i]] = 'H';
        printf("%3d  %s\n", y, row);
    }

    if (out) {
        FILE* f = fopen(out, "wb");
        if (!f) { fprintf(stderr, "cannot open %s\n", out); return 2; }
        fprintf(f, "P6\n240 320\n255\n");
        for (int i = 0; i < 240 * 320; ++i) {
            uint16_t c = fb[i];
            unsigned char p[3] = {(unsigned char)(((c >> 11) & 31) * 255 / 31),
                                  (unsigned char)(((c >> 5) & 63) * 255 / 63),
                                  (unsigned char)((c & 31) * 255 / 31)};
            fwrite(p, 1, 3, f);
        }
        fclose(f);
    }
    return 0;
}
