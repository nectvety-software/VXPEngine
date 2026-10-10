#pragma once
#include <stdint.h>
// Allocation-free placement rules shared with Editor Assets. Coordinates are cells.
namespace coremre {
struct VxpScatter2D {
    static uint32_t hash(int32_t x, int32_t y, uint32_t seed = 1) {
        uint32_t v = uint32_t(x) * 0x8da6b343u ^ uint32_t(y) * 0xd8163841u ^ seed;
        v ^= v >> 16; v *= 0x7feb352du; v ^= v >> 15; return v;
    }
    // Pass a clipped rectangle. occupied(x,y) returns false outside the map.
    // emit returns void; neighbours outside the map do not block placement.
    // Traversal is row-major; occupancy must reflect each emitted placement.
    template<class Occupied, class Emit>
    static unsigned paint(int x0, int y0, int x1, int y1, unsigned variants,
                          unsigned density, unsigned spacing, uint32_t seed,
                          Occupied occupied, Emit emit) {
        if (!variants || x1 < x0 || y1 < y0) return 0;
        if (density > 100) density = 100;
        if (spacing < 1) spacing = 1;
        if (spacing > 32) spacing = 32;
        unsigned count = 0;
        for (int y = y0; y <= y1; ++y) for (int x = x0; x <= x1; ++x) {
            uint32_t h = hash(x,y,seed);
            if (occupied(x,y) || h % 100 >= density) continue;
            bool blocked = false;
            int gap = int(spacing) - 1;
            for (int dy = -gap; dy <= gap && !blocked; ++dy)
                for (int dx = -gap; dx <= gap; ++dx)
                    if (occupied(x+dx,y+dy)) { blocked = true; break; }
            if (!blocked) { emit(x,y,(h >> 8) % variants); ++count; }
        }
        return count;
    }
};
}
