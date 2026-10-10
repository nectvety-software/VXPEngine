/* Fixed-point Super Scaler style road renderer for low-memory MRE games. */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VxpeSuperScalerConfig {
    int16_t horizon_y;
    int16_t center_x;
    uint16_t far_half_width;
    uint16_t near_half_width;
    int16_t curve_q8;       /* total screen-space curve offset, Q8 pixels */
    uint16_t road_phase;    /* advances with speed; road/curb strip phase */
    uint8_t curb_period;    /* scanlines per stripe group, normally 10..20 */
    uint16_t sky565, ground565, road_a565, road_b565;
    uint16_t curb_a565, curb_b565, lane565;
    /* Optional sparse tile overlays. Dimensions must be power-of-two <= 16;
     * zero texels preserve the base road/terrain color. Caller owns the tiles. */
    const uint16_t* road_texture;
    const uint16_t* ground_texture;
    uint8_t road_texture_w, road_texture_h;
    uint8_t ground_texture_w, ground_texture_h;
} VxpeSuperScalerConfig;

/* Draw sky, distant horizon band, scrolling ground, textured road, alternating
 * curbs and perspective lane markers. Textured pixels use nearest sampling;
 * no allocation, float, or per-pixel division. */
int vxpe_superscaler_draw(uint16_t* pixels, uint16_t width, uint16_t height,
                         uint16_t stride, const VxpeSuperScalerConfig* config);

#ifdef __cplusplus
}
#endif
