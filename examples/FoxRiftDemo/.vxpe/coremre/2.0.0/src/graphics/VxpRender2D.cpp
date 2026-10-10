#include "graphics/VxpRender2D.h"

#include <stddef.h>

namespace {

inline int clamp_i(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

inline int positive_mod(int value, int mod) {
    if (mod <= 0) return 0;
    int r = value % mod;
    return r < 0 ? r + mod : r;
}

inline uint8_t mask_visible(const VxpeSprite565* s, int x, int y) {
    if (s->opaque || s->mask == nullptr) return 1;
    const uint32_t bit = static_cast<uint32_t>(y) * s->width + static_cast<uint32_t>(x);
    return (s->mask[bit >> 3] & static_cast<uint8_t>(0x80u >> (bit & 7u))) != 0;
}

inline uint16_t tint565(uint16_t src, uint16_t tint) {
    if (tint == 0xFFFFu) return src;

    const uint32_t sr = (src >> 11) & 31u;
    const uint32_t sg = (src >> 5) & 63u;
    const uint32_t sb = src & 31u;

    const uint32_t tr = (tint >> 11) & 31u;
    const uint32_t tg = (tint >> 5) & 63u;
    const uint32_t tb = tint & 31u;

    const uint32_t r = (sr * tr + 15u) / 31u;
    const uint32_t g = (sg * tg + 31u) / 63u;
    const uint32_t b = (sb * tb + 15u) / 31u;
    return static_cast<uint16_t>((r << 11) | (g << 5) | b);
}

inline uint16_t alpha565(uint16_t dst, uint16_t src, uint8_t alpha) {
    if (alpha == 0) return dst;
    if (alpha == 255) return src;

    const uint32_t inv = 255u - alpha;
    const uint32_t dr = (dst >> 11) & 31u;
    const uint32_t dg = (dst >> 5) & 63u;
    const uint32_t db = dst & 31u;
    const uint32_t sr = (src >> 11) & 31u;
    const uint32_t sg = (src >> 5) & 63u;
    const uint32_t sb = src & 31u;

    const uint32_t r = (sr * alpha + dr * inv + 127u) / 255u;
    const uint32_t g = (sg * alpha + dg * inv + 127u) / 255u;
    const uint32_t b = (sb * alpha + db * inv + 127u) / 255u;
    return static_cast<uint16_t>((r << 11) | (g << 5) | b);
}

inline uint16_t add565(uint16_t dst, uint16_t src, uint8_t alpha) {
    if (alpha == 0) return dst;

    uint32_t dr = (dst >> 11) & 31u;
    uint32_t dg = (dst >> 5) & 63u;
    uint32_t db = dst & 31u;
    const uint32_t sr = ((src >> 11) & 31u) * alpha / 255u;
    const uint32_t sg = ((src >> 5) & 63u) * alpha / 255u;
    const uint32_t sb = (src & 31u) * alpha / 255u;

    dr += sr; if (dr > 31u) dr = 31u;
    dg += sg; if (dg > 63u) dg = 63u;
    db += sb; if (db > 31u) db = 31u;
    return static_cast<uint16_t>((dr << 11) | (dg << 5) | db);
}

inline uint16_t multiply565(uint16_t dst, uint16_t src, uint8_t alpha) {
    if (alpha == 0) return dst;

    const uint32_t dr = (dst >> 11) & 31u;
    const uint32_t dg = (dst >> 5) & 63u;
    const uint32_t db = dst & 31u;
    const uint32_t sr = (src >> 11) & 31u;
    const uint32_t sg = (src >> 5) & 63u;
    const uint32_t sb = src & 31u;

    const uint32_t mr = (dr * sr + 15u) / 31u;
    const uint32_t mg = (dg * sg + 31u) / 63u;
    const uint32_t mb = (db * sb + 15u) / 31u;
    const uint16_t multiplied = static_cast<uint16_t>((mr << 11) | (mg << 5) | mb);
    return alpha565(dst, multiplied, alpha);
}

inline uint16_t blend565(uint16_t dst, uint16_t src, uint8_t alpha, uint8_t mode) {
    switch (mode) {
        case VXPE_BLEND_ADD:
            return add565(dst, src, alpha);
        case VXPE_BLEND_MULTIPLY:
            return multiply565(dst, src, alpha);
        case VXPE_BLEND_ALPHA:
        case VXPE_BLEND_COPY:
        default:
            return alpha565(dst, src, alpha);
    }
}

inline uint16_t lerp565(uint16_t a, uint16_t b, uint16_t t256) {
    if (t256 >= 256u) return b;
    const uint32_t inv = 256u - t256;
    const uint32_t ar = (a >> 11) & 31u;
    const uint32_t ag = (a >> 5) & 63u;
    const uint32_t ab = a & 31u;
    const uint32_t br = (b >> 11) & 31u;
    const uint32_t bg = (b >> 5) & 63u;
    const uint32_t bb = b & 31u;
    const uint32_t r = (ar * inv + br * t256 + 128u) >> 8;
    const uint32_t g = (ag * inv + bg * t256 + 128u) >> 8;
    const uint32_t bl = (ab * inv + bb * t256 + 128u) >> 8;
    return static_cast<uint16_t>((r << 11) | (g << 5) | bl);
}

inline VxpeRectI full_rect(const VxpeSprite565* s) {
    VxpeRectI r;
    r.x = 0;
    r.y = 0;
    r.w = static_cast<int16_t>(s ? s->width : 0);
    r.h = static_cast<int16_t>(s ? s->height : 0);
    return r;
}

inline uint16_t frame_duration(const VxpeAnimClip* clip, uint16_t frame) {
    if (clip == nullptr || clip->frame_count == 0) return 1;
    uint16_t d = clip->durations_ms ? clip->durations_ms[frame] : clip->frame_ms;
    return d == 0 ? 1 : d;
}

} // namespace

extern "C" {

uint16_t vxpe2d_rgb565(uint8_t r, uint8_t g, uint8_t b) {
    return static_cast<uint16_t>(((r & 0xF8u) << 8) | ((g & 0xFCu) << 3) | (b >> 3));
}

uint16_t vxpe2d_tint565(uint16_t color, uint16_t tint) {
    return tint565(color, tint);
}

int vxpe2d_sprite_from_raw(const void* data, uint32_t size, VxpeSprite565* out) {
    if (data == nullptr || out == nullptr || size < 8u) return 0;

    const uint8_t* bytes = static_cast<const uint8_t*>(data);
    const uint16_t w = static_cast<uint16_t>(bytes[0] | (static_cast<uint16_t>(bytes[1]) << 8));
    const uint16_t h = static_cast<uint16_t>(bytes[2] | (static_cast<uint16_t>(bytes[3]) << 8));
    if (w == 0 || h == 0) return 0;

    const uint64_t count = static_cast<uint64_t>(w) * static_cast<uint64_t>(h);
    const uint64_t pixel_bytes = count * 2u;
    const uint8_t opaque = bytes[4] ? 1u : 0u;
    const uint64_t mask_bytes = opaque ? 0u : ((count + 7u) >> 3);
    const uint64_t needed = 8u + pixel_bytes + mask_bytes;
    if (needed > size) return 0;

    out->pixels = reinterpret_cast<const uint16_t*>(bytes + 8);
    out->mask = opaque ? nullptr : (bytes + 8u + static_cast<uint32_t>(pixel_bytes));
    out->width = w;
    out->height = h;
    out->stride = w;
    out->opaque = opaque;
    return 1;
}

void vxpe2d_fill_rect(uint16_t* fb, int fb_w, int fb_h,
                      int x, int y, int w, int h, uint16_t color) {
    if (fb == nullptr || fb_w <= 0 || fb_h <= 0 || w <= 0 || h <= 0) return;

    const int x0 = clamp_i(x, 0, fb_w);
    const int y0 = clamp_i(y, 0, fb_h);
    const int x1 = clamp_i(x + w, 0, fb_w);
    const int y1 = clamp_i(y + h, 0, fb_h);
    if (x1 <= x0 || y1 <= y0) return;

    for (int py = y0; py < y1; ++py) {
        uint16_t* row = fb + py * fb_w;
        for (int px = x0; px < x1; ++px) row[px] = color;
    }
}

void vxpe2d_gradient_vertical(uint16_t* fb, int fb_w, int fb_h,
                              int x, int y, int w, int h,
                              uint16_t top_color, uint16_t bottom_color) {
    if (fb == nullptr || fb_w <= 0 || fb_h <= 0 || w <= 0 || h <= 0) return;

    const int x0 = clamp_i(x, 0, fb_w);
    const int x1 = clamp_i(x + w, 0, fb_w);
    const int y0 = clamp_i(y, 0, fb_h);
    const int y1 = clamp_i(y + h, 0, fb_h);
    if (x1 <= x0 || y1 <= y0) return;

    const int denom = h > 1 ? h - 1 : 1;
    for (int py = y0; py < y1; ++py) {
        int local_y = py - y;
        if (local_y < 0) local_y = 0;
        if (local_y > denom) local_y = denom;
        const uint16_t t = static_cast<uint16_t>((local_y * 256) / denom);
        const uint16_t c = lerp565(top_color, bottom_color, t);
        uint16_t* row = fb + py * fb_w;
        for (int px = x0; px < x1; ++px) row[px] = c;
    }
}

void vxpe2d_overlay_rect(uint16_t* fb, int fb_w, int fb_h,
                         int x, int y, int w, int h,
                         uint16_t color, uint8_t alpha, uint8_t blend_mode) {
    if (fb == nullptr || fb_w <= 0 || fb_h <= 0 || w <= 0 || h <= 0 || alpha == 0) return;

    const int x0 = clamp_i(x, 0, fb_w);
    const int y0 = clamp_i(y, 0, fb_h);
    const int x1 = clamp_i(x + w, 0, fb_w);
    const int y1 = clamp_i(y + h, 0, fb_h);
    for (int py = y0; py < y1; ++py) {
        uint16_t* row = fb + py * fb_w;
        for (int px = x0; px < x1; ++px) {
            row[px] = blend565(row[px], color, alpha, blend_mode);
        }
    }
}

void vxpe2d_blit(uint16_t* fb, int fb_w, int fb_h,
                 const VxpeSprite565* sprite, const VxpeBlit565* op) {
    if (fb == nullptr || sprite == nullptr || op == nullptr ||
        sprite->pixels == nullptr || sprite->width == 0 || sprite->height == 0 ||
        fb_w <= 0 || fb_h <= 0 || op->alpha == 0) {
        return;
    }

    int sx0 = op->src.x;
    int sy0 = op->src.y;
    int sw = op->src.w;
    int sh = op->src.h;
    if (sw <= 0 || sh <= 0) {
        sx0 = 0;
        sy0 = 0;
        sw = sprite->width;
        sh = sprite->height;
    }

    if (sx0 < 0) { sw += sx0; sx0 = 0; }
    if (sy0 < 0) { sh += sy0; sy0 = 0; }
    if (sx0 >= sprite->width || sy0 >= sprite->height) return;
    if (sx0 + sw > sprite->width) sw = sprite->width - sx0;
    if (sy0 + sh > sprite->height) sh = sprite->height - sy0;
    if (sw <= 0 || sh <= 0) return;

    const int dw = op->dst_w ? op->dst_w : sw;
    const int dh = op->dst_h ? op->dst_h : sh;
    if (dw <= 0 || dh <= 0) return;

    int clip_x0=0,clip_y0=0,clip_x1=fb_w,clip_y1=fb_h;
    if(op->clip_w&&op->clip_h){
        clip_x0=clamp_i(op->clip_x,0,fb_w);
        clip_y0=clamp_i(op->clip_y,0,fb_h);
        clip_x1=clamp_i(op->clip_x+op->clip_w,0,fb_w);
        clip_y1=clamp_i(op->clip_y+op->clip_h,0,fb_h);
    }
    const int dx0 = clamp_i(op->dst_x, clip_x0, clip_x1);
    const int dy0 = clamp_i(op->dst_y, clip_y0, clip_y1);
    const int dx1 = clamp_i(op->dst_x + dw, clip_x0, clip_x1);
    const int dy1 = clamp_i(op->dst_y + dh, clip_y0, clip_y1);
    if (dx1 <= dx0 || dy1 <= dy0) return;

    const int stride = sprite->stride ? sprite->stride : sprite->width;
    const uint16_t tint = op->tint565;

    for (int dy = dy0; dy < dy1; ++dy) {
        const int local_y = dy - op->dst_y;
        uint16_t* dst_row = fb + dy * fb_w;
        for (int dx = dx0; dx < dx1; ++dx) {
            const int local_x = dx - op->dst_x;
            int ux=local_x,uy=local_y,uw=dw,uh=dh;
            if(op->flip_y) uy=uh-1-uy;
            if(op->flip_x) ux=uw-1-ux;
            int sx_rel,sy_rel;
            if(op->flip_d){
                sx_rel=(uy*sw)/uh;
                sy_rel=(ux*sh)/uw;
            }else{
                sx_rel=(ux*sw)/uw;
                sy_rel=(uy*sh)/uh;
            }
            if(sx_rel>=sw)sx_rel=sw-1;
            if(sy_rel>=sh)sy_rel=sh-1;
            const int sx=sx0+sx_rel;
            const int sy=sy0+sy_rel;

            if (!mask_visible(sprite, sx, sy)) continue;
            uint16_t src_px = sprite->pixels[sy * stride + sx];
            src_px = tint565(src_px, tint);
            dst_row[dx] = blend565(dst_row[dx], src_px, op->alpha, op->blend);
        }
    }
}

void vxpe2d_blit_simple(uint16_t* fb, int fb_w, int fb_h,
                        const VxpeSprite565* sprite, int x, int y) {
    if (sprite == nullptr) return;
    VxpeBlit565 op = {};
    op.src = full_rect(sprite);
    op.dst_x = static_cast<int16_t>(x);
    op.dst_y = static_cast<int16_t>(y);
    op.dst_w = sprite->width;
    op.dst_h = sprite->height;
    op.tint565 = 0xFFFFu;
    op.alpha = 255u;
    op.blend = VXPE_BLEND_COPY;
    vxpe2d_blit(fb, fb_w, fb_h, sprite, &op);
}

void vxpe2d_blit_parallax_x(uint16_t* fb, int fb_w, int fb_h,
                            const VxpeSprite565* sprite,
                            int32_t camera_x_q8, uint16_t parallax_q8,
                            int world_y, int repeat_width, int max_tiles) {
    if (sprite == nullptr || sprite->pixels == nullptr || sprite->width == 0 || fb_w <= 0) return;
    if (repeat_width <= 0) repeat_width = sprite->width;
    if (max_tiles <= 0) max_tiles = 32;

    const int32_t shifted_q8 = static_cast<int32_t>(
        (static_cast<int64_t>(camera_x_q8) * parallax_q8) >> 8);
    const int shifted = static_cast<int>(shifted_q8 >> 8);
    int start = -positive_mod(shifted, repeat_width);
    if (start > 0) start -= repeat_width;

    int drawn = 0;
    for (int x = start; x < fb_w && drawn < max_tiles; x += repeat_width, ++drawn) {
        vxpe2d_blit_simple(fb, fb_w, fb_h, sprite, x, world_y);
    }
}

void vxpe2d_radial_light(uint16_t* fb, int fb_w, int fb_h,
                         int center_x, int center_y, int radius,
                         uint16_t light_color, uint8_t intensity) {
    if (fb == nullptr || fb_w <= 0 || fb_h <= 0 || radius <= 0 || intensity == 0) return;

    const int x0 = clamp_i(center_x - radius, 0, fb_w);
    const int x1 = clamp_i(center_x + radius + 1, 0, fb_w);
    const int y0 = clamp_i(center_y - radius, 0, fb_h);
    const int y1 = clamp_i(center_y + radius + 1, 0, fb_h);
    const int64_t r2 = static_cast<int64_t>(radius) * radius;
    /* One divide per light instead of one divide per covered pixel. */
    const uint32_t inv_r2_q24 = static_cast<uint32_t>(
        ((static_cast<uint64_t>(1u) << 24) + static_cast<uint64_t>(r2 / 2)) /
        static_cast<uint64_t>(r2));

    for (int y = y0; y < y1; ++y) {
        uint16_t* row = fb + y * fb_w;
        const int dy = y - center_y;
        for (int x = x0; x < x1; ++x) {
            const int dx = x - center_x;
            const int64_t d2 = static_cast<int64_t>(dx) * dx + static_cast<int64_t>(dy) * dy;
            if (d2 >= r2) continue;
            const uint64_t energy = static_cast<uint64_t>(r2 - d2) * intensity;
            const uint32_t falloff = static_cast<uint32_t>((energy * inv_r2_q24) >> 24);
            row[x] = add565(row[x], light_color, static_cast<uint8_t>(falloff));
        }
    }
}

void vxpe2d_radial_light_fast(uint16_t* fb, int fb_w, int fb_h,
                              int center_x, int center_y, int radius,
                              uint16_t light_color, uint8_t intensity) {
    if (fb == nullptr || fb_w <= 0 || fb_h <= 0 || radius <= 0 || intensity == 0) return;

    const int y0 = clamp_i(center_y - radius, 0, fb_h);
    const int y1 = clamp_i(center_y + radius + 1, 0, fb_h);
    const uint32_t inv_radius_q16 = static_cast<uint32_t>(
        ((1u << 16) + static_cast<uint32_t>(radius / 2)) /
        static_cast<uint32_t>(radius));

    for (int y = y0; y < y1; ++y) {
        const int ay = y >= center_y ? y - center_y : center_y - y;
        const int half = radius - ay;
        if (half <= 0) continue;

        const int x0 = clamp_i(center_x - half, 0, fb_w);
        const int x1 = clamp_i(center_x + half + 1, 0, fb_w);
        uint16_t* row = fb + y * fb_w;

        for (int x = x0; x < x1; ++x) {
            const int ax = x >= center_x ? x - center_x : center_x - x;
            const int distance = ax + ay;
            if (distance >= radius) continue;
            const uint32_t falloff =
                (static_cast<uint32_t>(radius - distance) * intensity * inv_radius_q16) >> 16;
            row[x] = add565(row[x], light_color, static_cast<uint8_t>(falloff));
        }
    }
}

void vxpe2d_perspective_floor(uint16_t* fb, int fb_w, int fb_h,
                              const VxpeSprite565* texture,
                              int center_x, int horizon_y, int bottom_y,
                              int far_width, int near_width,
                              int scroll_x, int scroll_y, int16_t bend_q8) {
    if (fb == nullptr || texture == nullptr || texture->pixels == nullptr ||
        texture->width == 0 || texture->height == 0 || fb_w <= 0 || fb_h <= 0 ||
        bottom_y <= horizon_y || far_width <= 0 || near_width <= 0) {
        return;
    }

    const int y0 = clamp_i(horizon_y, 0, fb_h);
    const int y1 = clamp_i(bottom_y, 0, fb_h);
    const int span = bottom_y - horizon_y;
    const int stride = texture->stride ? texture->stride : texture->width;
    const int64_t span2 = static_cast<int64_t>(span) * span;

    for (int y = y0; y < y1; ++y) {
        const int dy = y - horizon_y;
        const int depth_q8 = static_cast<int>(
            (static_cast<int64_t>(dy) * dy * 256) / span2);
        const int width = far_width + ((near_width - far_width) * depth_q8 >> 8);
        if (width <= 0) continue;

        const int center_shift = static_cast<int>(
            (static_cast<int64_t>(bend_q8) * dy * depth_q8) >> 16);
        const int cx = center_x + center_shift;
        const int left = cx - width / 2;
        const int right = left + width;
        const int draw_x0 = clamp_i(left, 0, fb_w);
        const int draw_x1 = clamp_i(right, 0, fb_w);
        if (draw_x1 <= draw_x0) continue;

        const int tex_y = positive_mod(
            scroll_y + static_cast<int>((static_cast<int64_t>(dy) * dy * texture->height) / span2),
            texture->height);
        uint16_t* dst_row = fb + y * fb_w;

        for (int x = draw_x0; x < draw_x1; ++x) {
            const int local_x = x - left;
            const int tex_x = positive_mod(
                scroll_x + static_cast<int>((static_cast<int64_t>(local_x) * texture->width) / width),
                texture->width);
            if (!mask_visible(texture, tex_x, tex_y)) continue;
            dst_row[x] = texture->pixels[tex_y * stride + tex_x];
        }
    }
}

void vxpe2d_anim_reset(VxpeAnimState* state) {
    if (state == nullptr) return;
    state->frame = 0;
    state->elapsed_ms = 0;
    state->direction = 1;
    state->finished = 0;
}

void vxpe2d_anim_update(VxpeAnimState* state, const VxpeAnimClip* clip, uint16_t delta_ms) {
    if (state == nullptr || clip == nullptr || clip->frames == nullptr ||
        clip->frame_count == 0 || state->finished) {
        return;
    }

    if (state->frame >= clip->frame_count) state->frame = 0;
    if (state->direction == 0) state->direction = 1;

    uint32_t elapsed = static_cast<uint32_t>(state->elapsed_ms) + delta_ms;
    uint32_t guard = static_cast<uint32_t>(clip->frame_count) * 4u + 4u;

    while (guard-- > 0u) {
        const uint16_t dur = frame_duration(clip, state->frame);
        if (elapsed < dur) break;
        elapsed -= dur;

        if (clip->ping_pong && clip->frame_count > 1) {
            if (state->direction > 0) {
                if (state->frame + 1u < clip->frame_count) {
                    ++state->frame;
                } else if (clip->loop) {
                    state->direction = -1;
                    --state->frame;
                } else {
                    state->finished = 1;
                    elapsed = 0;
                    break;
                }
            } else {
                if (state->frame > 0) {
                    --state->frame;
                } else if (clip->loop) {
                    state->direction = 1;
                    ++state->frame;
                } else {
                    state->finished = 1;
                    elapsed = 0;
                    break;
                }
            }
        } else {
            if (state->frame + 1u < clip->frame_count) {
                ++state->frame;
            } else if (clip->loop) {
                state->frame = 0;
            } else {
                state->finished = 1;
                elapsed = 0;
                break;
            }
        }
    }

    state->elapsed_ms = static_cast<uint16_t>(elapsed > 65535u ? 65535u : elapsed);
}

VxpeRectI vxpe2d_anim_frame_rect(const VxpeAnimState* state, const VxpeAnimClip* clip) {
    VxpeRectI empty = {0, 0, 0, 0};
    if (state == nullptr || clip == nullptr || clip->frames == nullptr || clip->frame_count == 0) {
        return empty;
    }
    const uint16_t frame = state->frame < clip->frame_count ? state->frame : 0;
    return clip->frames[frame];
}

VxpeBlit565 vxpe2d_anim_blit(const VxpeAnimState* state, const VxpeAnimClip* clip,
                             int x, int y, uint16_t dst_w, uint16_t dst_h) {
    VxpeBlit565 op = {};
    op.src = vxpe2d_anim_frame_rect(state, clip);
    op.dst_x = static_cast<int16_t>(x);
    op.dst_y = static_cast<int16_t>(y);
    op.dst_w = dst_w;
    op.dst_h = dst_h;
    op.tint565 = 0xFFFFu;
    op.alpha = 255u;
    op.blend = VXPE_BLEND_COPY;
    return op;
}

} // extern "C"

extern "C" int vxpe2d_upscale2x565(uint16_t* dst,int dw,int dh,const uint16_t* src,int sw,int sh){
    if(!dst||!src||dst==src||sw<1||sh<1||sw>1024||sh>1024||dw!=sw*2||dh!=sh*2)return 0;
    for(int y=0;y<sh;++y){uint16_t* a=dst+(y*2)*dw;uint16_t* b=a+dw;const uint16_t* row=src+y*sw;
        for(int x=0;x<sw;++x){uint16_t c=row[x];a[x*2]=a[x*2+1]=b[x*2]=b[x*2+1]=c;}}
    return 1;
}

extern "C" int vxpe2d_scale2x565(uint16_t* dst,int dw,int dh,const uint16_t* src,int sw,int sh){
    if(!dst||!src||dst==src||sw<1||sh<1||sw>1024||sh>1024||dw!=sw*2||dh!=sh*2)return 0;
    for(int y=0;y<sh;++y){uint16_t* out=dst+y*2*dw;const uint16_t* row=src+y*sw;
        const uint16_t* above=src+(y?y-1:y)*sw;const uint16_t* below=src+(y+1<sh?y+1:y)*sw;
        for(int x=0;x<sw;++x){uint16_t e=row[x],b=above[x],h=below[x],d=row[x?x-1:x],f=row[x+1<sw?x+1:x];
            uint16_t p=e,q=e,r=e,s=e;
            if(b!=h&&d!=f){if(d==b)p=d;if(b==f)q=f;if(d==h)r=d;if(h==f)s=f;}
            out[x*2]=p;out[x*2+1]=q;out[dw+x*2]=r;out[dw+x*2+1]=s;
        }
    }return 1;
}
