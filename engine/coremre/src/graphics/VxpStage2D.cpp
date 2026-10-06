#include "graphics/VxpStage2D.h"

#include <string.h>

namespace {

static int pos_mod(int value, int modulus) {
    if (modulus <= 0) return 0;
    int r = value % modulus;
    return r < 0 ? r + modulus : r;
}

static int clamp_i(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static int wave_offset(int line, uint8_t phase, uint8_t shift, int amp) {
    static const int8_t lut[16] = {0,3,6,7,8,7,6,3,0,-3,-6,-7,-8,-7,-6,-3};
    if (!amp) return 0;
    const int index = (phase + (line >> shift)) & 15;
    return (lut[index] * amp) / 8;
}

static uint16_t mix565(uint16_t a, uint16_t b, uint8_t t) {
    const int ar=(a>>11)&31, ag=(a>>5)&63, ab=a&31;
    const int br=(b>>11)&31, bg=(b>>5)&63, bb=b&31;
    const int r=ar+((br-ar)*t+127)/255;
    const int g=ag+((bg-ag)*t+127)/255;
    const int bl=ab+((bb-ab)*t+127)/255;
    return (uint16_t)((r<<11)|(g<<5)|bl);
}

}

extern "C" {

void vxpe_stage_camera_init(VxpeStageCamera2D* camera, int viewport_w, int world_w) {
    if (!camera) return;
    memset(camera, 0, sizeof(*camera));
    if (viewport_w < 1) viewport_w = 1;
    if (world_w < viewport_w) world_w = viewport_w;
    camera->viewport_w = (int16_t)viewport_w;
    camera->min_x_q8 = 0;
    camera->max_x_q8 = (int32_t)(world_w - viewport_w) << 8;
    camera->deadzone_left = (int16_t)(viewport_w * 3 / 10);
    camera->deadzone_right = (int16_t)(viewport_w * 7 / 10);
}

void vxpe_stage_camera_follow(VxpeStageCamera2D* camera, int target_world_x, uint16_t smooth_q8) {
    if (!camera) return;
    if (smooth_q8 > 256) smooth_q8 = 256;
    int screen_x = target_world_x - (int)(camera->x_q8 >> 8);
    int desired = (int)(camera->x_q8 >> 8);
    if (screen_x < camera->deadzone_left) {
        desired = target_world_x - camera->deadzone_left;
    } else if (screen_x > camera->deadzone_right) {
        desired = target_world_x - camera->deadzone_right;
    }
    int32_t desired_q8 = (int32_t)desired << 8;
    if (desired_q8 < camera->min_x_q8) desired_q8 = camera->min_x_q8;
    if (desired_q8 > camera->max_x_q8) desired_q8 = camera->max_x_q8;
    if (smooth_q8 == 0 || smooth_q8 == 256) {
        camera->x_q8 = desired_q8;
    } else {
        camera->x_q8 += (int32_t)(((int64_t)(desired_q8 - camera->x_q8) * smooth_q8) >> 8);
    }
}

int vxpe_stage_world_to_screen_x(const VxpeStageCamera2D* camera, int world_x) {
    return camera ? world_x - (int)(camera->x_q8 >> 8) : world_x;
}

void vxpe_stage_draw_band565(
    uint16_t* fb, int fb_w, int fb_h, const VxpeSprite565* sprite,
    const VxpeStageCamera2D* camera, const VxpeStageBand2D* band) {
    if (!fb || !sprite || !sprite->pixels || !camera || !band) return;
    VxpeRectI src = band->src;
    if (src.w <= 0 || src.h <= 0) {
        src.x = 0; src.y = 0; src.w = (int16_t)sprite->width; src.h = (int16_t)sprite->height;
    }
    if (src.x < 0 || src.y < 0 || src.x + src.w > sprite->width || src.y + src.h > sprite->height) return;
    const int dst_h = band->dst_h ? band->dst_h : src.h;
    if (dst_h <= 0) return;
    const int camera_px = (int)(((int64_t)camera->x_q8 * band->parallax_q8) >> 16);
    const int base_scroll = camera_px + band->scroll_x;
    const uint16_t tint = band->tint565 ? band->tint565 : 0xFFFFu;
    const uint8_t alpha = band->alpha;
    const int clip_y0 = clamp_i(band->dst_y, 0, fb_h);
    const int clip_y1 = clamp_i(band->dst_y + dst_h, 0, fb_h);
    if (clip_y1 <= clip_y0) return;

    if (!band->raster_wave) {
        const int tile_w = src.w;
        int first_x = -pos_mod(base_scroll, tile_w);
        int tiles = band->repeat_x ? (fb_w / tile_w + 3) : 1;
        for (int i=0; i<tiles; ++i) {
            VxpeBlit565 op{};
            op.src = src;
            op.dst_x = (int16_t)(first_x + i * tile_w);
            op.dst_y = band->dst_y;
            op.dst_w = (uint16_t)tile_w;
            op.dst_h = (uint16_t)dst_h;
            op.tint565 = tint; op.alpha = alpha; op.blend = band->blend;
            op.clip_x = 0; op.clip_y = (int16_t)clip_y0;
            op.clip_w = (uint16_t)fb_w; op.clip_h = (uint16_t)(clip_y1 - clip_y0);
            vxpe2d_blit(fb, fb_w, fb_h, sprite, &op);
            if (!band->repeat_x) break;
        }
        return;
    }

    for (int y=clip_y0; y<clip_y1; ++y) {
        const int local_y = y - band->dst_y;
        const int sy = src.y + pos_mod((local_y * src.h) / dst_h + band->scroll_y, src.h);
        const int shift = wave_offset(local_y, band->wave_phase, band->wave_shift, band->wave_amplitude);
        const int tile_w = src.w;
        const int scroll = base_scroll + shift;
        int first_x = -pos_mod(scroll, tile_w);
        int tiles = band->repeat_x ? (fb_w / tile_w + 3) : 1;
        for (int i=0; i<tiles; ++i) {
            VxpeBlit565 op{};
            op.src.x = src.x; op.src.y = (int16_t)sy; op.src.w = src.w; op.src.h = 1;
            op.dst_x = (int16_t)(first_x + i * tile_w); op.dst_y = (int16_t)y;
            op.dst_w = (uint16_t)tile_w; op.dst_h = 1;
            op.tint565 = tint; op.alpha = alpha; op.blend = band->blend;
            op.clip_x = 0; op.clip_y = (int16_t)y; op.clip_w = (uint16_t)fb_w; op.clip_h = 1;
            vxpe2d_blit(fb, fb_w, fb_h, sprite, &op);
            if (!band->repeat_x) break;
        }
    }
}

uint16_t vxpe_stage_cycle565(uint16_t color_a, uint16_t color_b, uint8_t phase) {
    uint8_t p = phase & 31u;
    uint8_t t = p < 16 ? (uint8_t)(p * 17) : (uint8_t)((31 - p) * 17);
    return mix565(color_a, color_b, t);
}

}
