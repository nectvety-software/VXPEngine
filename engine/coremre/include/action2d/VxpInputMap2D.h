/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 *
 * VxpInputMap2D - raw handset key codes in, named action edges out.
 *
 * The platform delivers one flat integer per key event (VM_KEY_*, so -9..122
 * depending on the handset) and a game otherwise spends its life comparing
 * magic numbers in a switch statement. This module turns that stream into
 * named actions with held / pressed / released edges and menu-style
 * auto-repeat, and it never includes the SDK: the app forwardes codes from its
 * key callback, so the same mapping runs unchanged in the host harness.
 *
 * Handsets have a small keyboard and several actions share a physical key (2,
 * 4, 6, 8 double as arrows), so an action owns up to three codes and one code
 * can feed several actions. Nothing allocates: the map is a plain struct the
 * game owns, and every state field is a bit in a uint16_t so the whole input
 * state fits in a cache line.
 */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define VXPE_INPUT_ACTION_MAX 12
#define VXPE_INPUT_KEYS_PER_ACTION 3

/* Slot sentinel. No handset key code is ever 0x7FFF, so an empty slot is
 * distinguishable from VM_KEY_NUM0 (48) and from 0 itself. */
#define VXPE_IN_KEY_NONE ((int16_t)0x7FFF)

/* Default auto-repeat: the first step comes after 350 ms of holding, then one
 * every 120 ms, which is what the handset's own list widgets feel like. */
#define VXPE_INPUT_REPEAT_FIRST_MS 350
#define VXPE_INPUT_REPEAT_RATE_MS 120

typedef struct VxpeInputMap2D {
    int16_t keys[VXPE_INPUT_ACTION_MAX][VXPE_INPUT_KEYS_PER_ACTION];

    /* Bit per action, filled by the app's key callback and consumed by the
     * frame loop. Only the low VXPE_INPUT_ACTION_MAX bits are ever used. */
    uint16_t held;     /* down right now */
    uint16_t pressed;  /* went down during the last vxpe_input_update */
    uint16_t released; /* went up during the last vxpe_input_update */
    uint16_t repeated; /* auto-repeat edge, see vxpe_input_set_repeat */
    uint16_t pending_press;   /* edge seen between updates, incl. a same-frame tap */
    uint16_t pending_release;

    uint16_t held_ms[VXPE_INPUT_ACTION_MAX];    /* saturates at 60 000 */
    uint16_t repeat_ms[VXPE_INPUT_ACTION_MAX];  /* countdown to the next edge */

    uint16_t repeat_first_ms;
    uint16_t repeat_rate_ms;
} VxpeInputMap2D;

/* Clear every bit, fill the key table with VXPE_IN_KEY_NONE and install the
 * default repeat timings. Call once before binding. */
void vxpe_input_init(VxpeInputMap2D* map);

/* Bind up to three codes to one action; pass VXPE_IN_KEY_NONE to leave a slot
 * empty. Rebinding replaces the whole triple, so unbind by calling this with
 * three sentinels or with vxpe_input_unbind. `action` out of range is ignored. */
void vxpe_input_bind(VxpeInputMap2D* map, int action,
                     int16_t k0, int16_t k1, int16_t k2);
void vxpe_input_unbind(VxpeInputMap2D* map, int action);

/* 1 when `action` is currently down. */
int vxpe_input_held(const VxpeInputMap2D* map, int action);
/* 1 only on the frame the action went down (or was tapped between updates). */
int vxpe_input_pressed(const VxpeInputMap2D* map, int action);
int vxpe_input_released(const VxpeInputMap2D* map, int action);
/* 1 on an auto-repeat edge: the held frame itself does not repeat. */
int vxpe_input_repeated(const VxpeInputMap2D* map, int action);
/* Milliseconds the action has been down, saturating at 60 000. */
uint16_t vxpe_input_held_ms(const VxpeInputMap2D* map, int action);

/* Drop the press and repeat edges after the frame that consumed them, so a menu
 * opened by vxpe_input_pressed cannot re-fire if the game reads the flag twice.
 * Only the edges clear; the held bit and its timer are untouched. */
void vxpe_input_consume(VxpeInputMap2D* map, int action);

/* App key callback hooks. Both return 1 when the code maps to at least one
 * action, so the caller can tell "handled" from "unknown key". A press while
 * already held is ignored - the platform sends DOWN, LONG_PRESS and REPEAT for
 * one physical hold and only the first should look like an edge. */
int vxpe_input_press(VxpeInputMap2D* map, int16_t code);
int vxpe_input_release(VxpeInputMap2D* map, int16_t code);

/* Advance timers and recompute pressed / released / repeated. Call exactly
 * once per frame, after dispatching that frame's key events and before the
 * simulation reads the edges. */
void vxpe_input_update(VxpeInputMap2D* map, uint16_t dt_ms);

/* -1 / 0 / +1 from two opposing actions - the form VxpeBodyIntent2D wants.
 * Held on both sides gives 0, which is the safe reading for a stuck key: a
 * player leaning on left and right should stop, not walk into a wall. */
int8_t vxpe_input_axis(const VxpeInputMap2D* map, int neg_action, int pos_action);

/* Delay before the first repeat edge and the interval after it. 0 for either
 * disables auto-repeat entirely. Turning it back on re-arms a key that was
 * already held while it was off, so enabling cannot fire a stray edge; a key
 * that is already counting down keeps its countdown. */
void vxpe_input_set_repeat(VxpeInputMap2D* map,
                           uint16_t first_ms, uint16_t rate_ms);

/* Short label for one code, for help and key-legend screens: "UP", "OK",
 * "CLR", "2", "A", "#". Returns NULL for an unknown or unbound code, and the
 * static buffer is only valid until the next call. */
const char* vxpe_input_key_name(int16_t code);

#ifdef __cplusplus
} /* extern "C" */
#endif
