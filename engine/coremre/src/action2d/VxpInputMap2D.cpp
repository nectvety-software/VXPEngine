/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpInputMap2D implementation. Pure integer bookkeeping over bit sets: no
 * allocation, no libc beyond NULL, and the whole state is one struct, so the
 * host harness and the handset run identical code paths.
 */
#include "action2d/VxpInputMap2D.h"

#include <stddef.h>
#include <string.h>

namespace {

/* Key-down, long-press and repeat are three platform events for one physical
 * hold; only the first may look like an edge. Held bits therefore ignore a
 * press that arrives while the bit is already set. */
const uint16_t kHeldMsCap = 60000u;

inline uint16_t add_capped_ms(uint16_t v, uint16_t dt) {
    const uint32_t sum = (uint32_t)v + dt;
    return sum > kHeldMsCap ? kHeldMsCap : (uint16_t)sum;
}

inline int bit_of(int action) { return 1 << action; }

inline int valid(const VxpeInputMap2D* map, int action) {
    return map != nullptr && action >= 0 && action < VXPE_INPUT_ACTION_MAX;
}

}  // namespace

extern "C" {

void vxpe_input_init(VxpeInputMap2D* map) {
    if (map == nullptr) return;
    memset(map, 0, sizeof(*map));
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        for (int s = 0; s < VXPE_INPUT_KEYS_PER_ACTION; ++s) {
            map->keys[a][s] = VXPE_IN_KEY_NONE;
        }
    }
    map->repeat_first_ms = VXPE_INPUT_REPEAT_FIRST_MS;
    map->repeat_rate_ms = VXPE_INPUT_REPEAT_RATE_MS;
}

void vxpe_input_bind(VxpeInputMap2D* map, int action,
                     int16_t k0, int16_t k1, int16_t k2) {
    if (!valid(map, action)) return;
    map->keys[action][0] = k0;
    map->keys[action][1] = k1;
    map->keys[action][2] = k2;
}

void vxpe_input_unbind(VxpeInputMap2D* map, int action) {
    if (!valid(map, action)) return;
    for (int s = 0; s < VXPE_INPUT_KEYS_PER_ACTION; ++s) {
        map->keys[action][s] = VXPE_IN_KEY_NONE;
    }
}

int vxpe_input_held(const VxpeInputMap2D* map, int action) {
    return valid(map, action) ? (map->held >> action) & 1 : 0;
}

int vxpe_input_pressed(const VxpeInputMap2D* map, int action) {
    return valid(map, action) ? (map->pressed >> action) & 1 : 0;
}

int vxpe_input_released(const VxpeInputMap2D* map, int action) {
    return valid(map, action) ? (map->released >> action) & 1 : 0;
}

int vxpe_input_repeated(const VxpeInputMap2D* map, int action) {
    return valid(map, action) ? (map->repeated >> action) & 1 : 0;
}

uint16_t vxpe_input_held_ms(const VxpeInputMap2D* map, int action) {
    return valid(map, action) ? map->held_ms[action] : 0;
}

void vxpe_input_consume(VxpeInputMap2D* map, int action) {
    if (!valid(map, action)) return;
    map->pressed &= (uint16_t)~bit_of(action);
    map->repeated &= (uint16_t)~bit_of(action);
}

int vxpe_input_press(VxpeInputMap2D* map, int16_t code) {
    if (map == nullptr || code == VXPE_IN_KEY_NONE) return 0;
    int matched = 0;
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        for (int s = 0; s < VXPE_INPUT_KEYS_PER_ACTION; ++s) {
            if (map->keys[a][s] != code) continue;
            matched = 1;
            const int b = bit_of(a);
            if (map->held & b) break;
            map->held |= (uint16_t)b;
            map->pending_press |= (uint16_t)b;
            map->repeat_ms[a] = map->repeat_first_ms;
            break;
        }
    }
    return matched;
}

int vxpe_input_release(VxpeInputMap2D* map, int16_t code) {
    if (map == nullptr || code == VXPE_IN_KEY_NONE) return 0;
    int matched = 0;
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        for (int s = 0; s < VXPE_INPUT_KEYS_PER_ACTION; ++s) {
            if (map->keys[a][s] != code) continue;
            matched = 1;
            const int b = bit_of(a);
            if (!(map->held & b)) break;
            map->held &= (uint16_t)~b;
            map->pending_release |= (uint16_t)b;
            map->held_ms[a] = 0;
            map->repeat_ms[a] = 0;
            break;
        }
    }
    return matched;
}

void vxpe_input_update(VxpeInputMap2D* map, uint16_t dt_ms) {
    if (map == nullptr) return;

    map->pressed = map->pending_press;
    map->released = map->pending_release;
    map->pending_press = 0;
    map->pending_release = 0;
    map->repeated = 0;

    /* A tap squeezed between two updates produces both edges in the same
     * frame, which is what a menu wants: the highlight moves even though the
     * held bit never survived to be sampled. */
    const int repeating = map->repeat_first_ms != 0 && map->repeat_rate_ms != 0;
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        const int b = bit_of(a);
        if (!(map->held & b)) continue;
        map->held_ms[a] = add_capped_ms(map->held_ms[a], dt_ms);
        if (!repeating) continue;
        if (map->repeat_ms[a] > dt_ms) {
            map->repeat_ms[a] = (uint16_t)(map->repeat_ms[a] - dt_ms);
        } else {
            /* One edge per frame whatever dt_ms says: a 30 fps loop that
             * stalls for a second should step the cursor once, not fifty
             * times, and a game that reads the flag once per frame cannot see
             * the difference anyway. */
            map->repeated |= (uint16_t)b;
            map->repeat_ms[a] = map->repeat_rate_ms;
        }
    }
}

int8_t vxpe_input_axis(const VxpeInputMap2D* map, int neg_action, int pos_action) {
    const int neg = vxpe_input_held(map, neg_action);
    const int pos = vxpe_input_held(map, pos_action);
    if (neg == pos) return 0; /* both or neither: stand still */
    return pos ? 1 : -1;
}

void vxpe_input_set_repeat(VxpeInputMap2D* map, uint16_t first_ms, uint16_t rate_ms) {
    if (map == nullptr) return;
    map->repeat_first_ms = first_ms;
    map->repeat_rate_ms = rate_ms;
    if (first_ms == 0 || rate_ms == 0) return;
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        /* A key pressed while repeat was off has no countdown armed, so it would
         * fire the instant repeat comes back on. Handing it the new first delay
         * instead keeps "enable repeat" from moving a cursor nobody asked for.
         * A countdown already running is left alone, so tightening the delay
         * never skips an edge a menu was about to fire. */
        if ((map->held & bit_of(a)) && map->repeat_ms[a] == 0) {
            map->repeat_ms[a] = first_ms;
        }
    }
}

const char* vxpe_input_key_name(int16_t code) {
    switch (code) {
    case -1: return "UP";
    case -2: return "DOWN";
    case -3: return "LEFT";
    case -4: return "RIGHT";
    case -5: return "OK";
    case -6: return "LSK";
    case -7: return "RSK";
    case -8: return "CLR";
    case -9: return "BACK";
    case 35: return "#";
    case 42: return "*";
    case 58: return "VOL+";
    case 59: return "VOL-";
    default: break;
    }
    /* The digit pad and the qwerty letters are their own ASCII characters, so
     * one static byte is enough for both ranges. */
    static char ascii[2];
    if ((code >= '0' && code <= '9') || (code >= 'A' && code <= 'Z')) {
        ascii[0] = (char)code;
        ascii[1] = 0;
        return ascii;
    }
    return nullptr;
}

} /* extern "C" */
