/* Four-direction atlas animation, fixed memory, C compatible. */
#pragma once
#include "graphics/VxpSpriteFx.h"
#ifdef __cplusplus
extern "C" {
#endif
enum { VXPE_ACTOR_NORTH=0, VXPE_ACTOR_EAST=1, VXPE_ACTOR_SOUTH=2, VXPE_ACTOR_WEST=3 };
enum { VXPE_ACTOR_IDLE=0, VXPE_ACTOR_WALK=1, VXPE_ACTOR_CAST=2, VXPE_ACTOR_REEL=3 };
typedef struct VxpeActorClip2D {
    uint16_t first, count, frame_ms;
    uint8_t loop;
} VxpeActorClip2D;
typedef struct VxpeActorAtlas2D {
    VxpeSpriteA8 sprite;
    uint16_t frame_w, frame_h;
    int16_t anchor_x, anchor_y; /* Foot position within a frame. */
    VxpeActorClip2D clips[4];
} VxpeActorAtlas2D;
typedef struct VxpeActorState2D {
    uint16_t elapsed_ms, frame;
    uint8_t direction, action, finished;
} VxpeActorState2D;
void vxpe_actor_init(VxpeActorState2D* state);
/* Same action/direction preserves playback; action changes restart it.
 * Direction changes preserve frame phase while changing atlas row.
 */
int vxpe_actor_set(VxpeActorState2D* state, uint8_t direction, uint8_t action);
int vxpe_actor_update(VxpeActorState2D* state, const VxpeActorAtlas2D* atlas, uint16_t dt_ms);
/* Returns 0 on invalid atlas/state. x/y specify the world-space foot anchor. */
int vxpe_actor_draw(uint16_t* fb, int w, int h, const VxpeActorAtlas2D* atlas,
    const VxpeActorState2D* state, int16_t x, int16_t y);
#ifdef __cplusplus
}
#endif
