#include "graphics/VxpSuperScaler.h"
#include <stddef.h>
#include <array>
#include <utility>

namespace {
static inline void span(uint16_t* row, int width, int x0, int x1, uint16_t c) {
    if (x0 < 0) x0 = 0;
    if (x1 > width) x1 = width;
    if (x1 < 0) x1 = 0;
    if (x0 > width) x0 = width;
    for (int x = x0; x < x1; ++x) row[x] = c;
}
/* Q8 perspective curve fraction: square of normalized depth. */
constexpr uint8_t depth_value(unsigned t) { return t >= 256u ? 255u : static_cast<uint8_t>((t * t) >> 8); }
template <size_t... I> constexpr std::array<uint8_t, sizeof...(I)> make_depth_lut(std::index_sequence<I...>) {
    return {{depth_value(static_cast<unsigned>(I))...}};
}
constexpr auto kDepthQ8 = make_depth_lut(std::make_index_sequence<257>{});
static bool valid_tile(const uint16_t* p, uint8_t w, uint8_t h) {
    return !p || (w && h && w <= 16 && h <= 16 && !(w & (w - 1)) && !(h & (h - 1)));
}
}

extern "C" int vxpe_superscaler_draw(uint16_t* pixels, uint16_t width,
                                      uint16_t height, uint16_t stride,
                                      const VxpeSuperScalerConfig* c) {
    if (!pixels || !c || !width || !height || stride < width ||
        c->horizon_y < 0 || c->horizon_y >= height || !c->far_half_width ||
        !c->near_half_width || !valid_tile(c->road_texture,c->road_texture_w,c->road_texture_h) ||
        !valid_tile(c->ground_texture,c->ground_texture_w,c->ground_texture_h)) return 0;
    const int horizon = c->horizon_y;
    int span_y = (int)height - horizon - 1;
    if (span_y <= 0) return 0;
    const uint32_t inverse_span_q16 = (65536u + (uint32_t)span_y / 2u) / (uint32_t)span_y;
    const int period = c->curb_period ? c->curb_period : 16;
    const uint32_t inverse_period_q16 = (65536u + (uint32_t)period / 2u) / (uint32_t)period;
    const uint32_t phase_q16 = (uint32_t)c->road_phase * inverse_period_q16;
    const uint32_t row_step_q16 = 3u * inverse_period_q16;
    for (int y = 0; y < horizon; ++y) span(pixels + y * stride, width, 0, width, c->sky565);
    for (int y = horizon; y < height; ++y) {
        uint16_t* row = pixels + y * stride;
        const int d = y - horizon;
        unsigned normalized_q8 = (unsigned)(((uint32_t)d * inverse_span_q16) >> 8);
        if (normalized_q8 > 256u) normalized_q8 = 256u;
        const int q = kDepthQ8[normalized_q8];
        const int half = (int)c->far_half_width +
            ((int)(c->near_half_width - c->far_half_width) * q >> 8);
        const int center = c->center_x + ((int)c->curve_q8 * q >> 16);
        const int left = center - half;
        const int right = center + half;
        const int motion = (int)((phase_q16 + (uint32_t)d * row_step_q16) >> 16);
        const uint16_t turf = c->ground565;
        span(row, width, 0, width, turf);
        if (c->ground_texture) {
            const unsigned tw=c->ground_texture_w, th=c->ground_texture_h;
            const unsigned ty=(((unsigned)d*(unsigned)d>>8)+(c->road_phase>>3))&(th-1u);
            for (int x=0;x<width;++x) {
                const unsigned tx=((unsigned)x+(c->road_phase>>2))&(tw-1u);
                const uint16_t p=c->ground_texture[ty*tw+tx]; if(p)row[x]=p;
            }
        }
        const uint16_t curb = (motion & 1) ? c->curb_a565 : c->curb_b565;
        const int curb_w = 1 + (q >> 5);
        span(row, width, left - curb_w, left, curb);
        span(row, width, right, right + curb_w, curb);
        span(row, width, left, right, ((motion + (y >> 4)) & 1) ? c->road_a565 : c->road_b565);
        if (c->road_texture && right>0 && left<(int)width) {
            const unsigned tw=c->road_texture_w, th=c->road_texture_h;
            const unsigned ty=(((unsigned)d*(unsigned)d>>7)+(c->road_phase>>4))&(th-1u);
            const int x0=left<0?0:left, x1=right>(int)width?(int)width:right;
            for(int x=x0;x<x1;++x){const unsigned tx=((unsigned)(x-left)+(c->road_phase>>3))&(tw-1u);const uint16_t p=c->road_texture[ty*tw+tx];if(p)row[x]=p;}
        }
        /* Broken center lane markers shrink toward the horizon. */
        const int marker = 1 + (q >> 6);
        if ((((uint32_t)c->road_phase + (uint32_t)d * 3u) & 16u) == 0u)
            span(row, width, center - marker / 2, center + (marker + 1) / 2, c->lane565);
    }
    return 1;
}
