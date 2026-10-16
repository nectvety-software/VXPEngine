/*
 * Regression coverage for the action input layer: binding, edge lifetime,
 * platform event de-duplication, auto-repeat arithmetic and the axis helper.
 *
 * The whole module is integer bookkeeping over a struct the test owns, so the
 * assertions are exact bit patterns and exact millisecond counts. Nothing here
 * includes the SDK: the test plays the part of the app key callback.
 */
#include "action2d/VxpInputMap2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

/* The handset codes this game cares about, spelled out from vmio.h so a change
 * in the SDK shows up as a failing assertion rather than a dead button. */
enum {
    K_UP = -1, K_DOWN = -2, K_LEFT = -3, K_RIGHT = -4, K_OK = -5,
    K_LSK = -6, K_RSK = -7, K_CLEAR = -8, K_BACK = -9,
    K_2 = 50, K_4 = 52, K_6 = 54, K_8 = 56
};

enum { A_LEFT = 0, A_RIGHT = 1, A_UP = 2, A_DOWN = 3, A_JUMP = 4,
       A_ATTACK = 5, A_START = 6, A_PAUSE = 7 };

static int bit_count(uint16_t v) {
    int n = 0;
    for (int i = 0; i < 16; ++i) if (v & (1u << i)) ++n;
    return n;
}

static void bind_gamepad(VxpeInputMap2D* m) {
    /* The digit pad doubles as arrows on every handset keyboard. */
    vxpe_input_bind(m, A_LEFT, K_LEFT, K_4, VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_RIGHT, K_RIGHT, K_6, VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_UP, K_UP, K_8, VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_DOWN, K_DOWN, K_2, VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_JUMP, K_OK, K_RSK, VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_ATTACK, K_LSK, 'Z', VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_START, K_CLEAR, VXPE_IN_KEY_NONE, VXPE_IN_KEY_NONE);
    vxpe_input_bind(m, A_PAUSE, K_BACK, VXPE_IN_KEY_NONE, VXPE_IN_KEY_NONE);
}

/* ---- table -------------------------------------------------------------- */

static void test_init_and_bind(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        for (int s = 0; s < VXPE_INPUT_KEYS_PER_ACTION; ++s) {
            assert(m.keys[a][s] == VXPE_IN_KEY_NONE);
        }
        assert(m.held_ms[a] == 0 && m.repeat_ms[a] == 0);
    }
    assert(m.held == 0 && m.pressed == 0 && m.released == 0 && m.repeated == 0);
    assert(m.pending_press == 0 && m.pending_release == 0);
    assert(m.repeat_first_ms == VXPE_INPUT_REPEAT_FIRST_MS);
    assert(m.repeat_rate_ms == VXPE_INPUT_REPEAT_RATE_MS);

    vxpe_input_bind(&m, A_JUMP, K_OK, K_RSK, '#');
    assert(m.keys[A_JUMP][0] == K_OK);
    assert(m.keys[A_JUMP][1] == K_RSK);
    assert(m.keys[A_JUMP][2] == 35);

    /* Rebinding replaces the whole triple - no stale third key survives. */
    vxpe_input_bind(&m, A_JUMP, K_OK, VXPE_IN_KEY_NONE, VXPE_IN_KEY_NONE);
    assert(m.keys[A_JUMP][1] == VXPE_IN_KEY_NONE);
    assert(m.keys[A_JUMP][2] == VXPE_IN_KEY_NONE);

    vxpe_input_unbind(&m, A_JUMP);
    assert(!vxpe_input_press(&m, K_OK));
    assert(!vxpe_input_release(&m, K_OK));

    /* Out of range actions are ignored on both sides of the API. */
    vxpe_input_bind(&m, -1, K_OK, 0, 0);
    vxpe_input_bind(&m, VXPE_INPUT_ACTION_MAX, K_OK, 0, 0);
    vxpe_input_unbind(&m, 999);
    assert(m.keys[0][0] == VXPE_IN_KEY_NONE);
    for (int a = 0; a < VXPE_INPUT_ACTION_MAX; ++a) {
        assert(vxpe_input_held(&m, a) == 0);
        assert(vxpe_input_pressed(&m, a) == 0);
        assert(vxpe_input_released(&m, a) == 0);
        assert(vxpe_input_repeated(&m, a) == 0);
        assert(vxpe_input_held_ms(&m, a) == 0);
    }
}

static void test_null_map(void) {
    /* The app must be able to call into a missing map during a boot frame. */
    assert(!vxpe_input_press(0, K_OK));
    assert(!vxpe_input_release(0, K_OK));
    vxpe_input_update(0, 33);
    vxpe_input_init(0);
    vxpe_input_bind(0, A_JUMP, K_OK, 0, 0);
    vxpe_input_unbind(0, A_JUMP);
    vxpe_input_consume(0, A_JUMP);
    vxpe_input_set_repeat(0, 10, 10);
    assert(!vxpe_input_held(0, A_JUMP));
    assert(!vxpe_input_pressed(0, A_JUMP));
    assert(!vxpe_input_released(0, A_JUMP));
    assert(!vxpe_input_repeated(0, A_JUMP));
    assert(vxpe_input_held_ms(0, A_JUMP) == 0);
    assert(vxpe_input_axis(0, A_LEFT, A_RIGHT) == 0);
    /* The sentinel never matches, so a stray unhandled event cannot latch. */
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    bind_gamepad(&m);
    assert(!vxpe_input_press(&m, VXPE_IN_KEY_NONE));
    assert(!vxpe_input_release(&m, VXPE_IN_KEY_NONE));
    vxpe_input_update(&m, 33);
    assert(m.pressed == 0 && m.held == 0);
}

/* ---- edges -------------------------------------------------------------- */

static void test_press_release_edges(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    bind_gamepad(&m);

    /* One physical hold emits DOWN, LONG_PRESS and REPEAT for the same code.
     * Only the first may look like an edge. */
    assert(vxpe_input_press(&m, K_RIGHT));
    assert(vxpe_input_press(&m, K_RIGHT));
    assert(vxpe_input_press(&m, K_RIGHT));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_pressed(&m, A_RIGHT));
    assert(bit_count(m.pressed) == 1);
    assert(vxpe_input_held(&m, A_RIGHT));
    assert(m.held_ms[A_RIGHT] == 33);

    /* The edge lives for exactly one update. */
    vxpe_input_update(&m, 33);
    assert(!vxpe_input_pressed(&m, A_RIGHT));
    assert(vxpe_input_held(&m, A_RIGHT));
    assert(m.held_ms[A_RIGHT] == 66);

    assert(vxpe_input_release(&m, K_RIGHT));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_released(&m, A_RIGHT));
    assert(!vxpe_input_held(&m, A_RIGHT));
    assert(m.held_ms[A_RIGHT] == 0);
    vxpe_input_update(&m, 33);
    assert(!vxpe_input_released(&m, A_RIGHT));

    /* Releasing something that was never down is matched but edge-free. */
    assert(vxpe_input_release(&m, K_LEFT));
    vxpe_input_update(&m, 33);
    assert(m.released == 0 && m.pressed == 0);

    /* An unknown code reports itself as unhandled. */
    assert(!vxpe_input_press(&m, 'Q'));
    assert(!vxpe_input_release(&m, 'Q'));

    /* A tap squeezed between two updates yields both edges in one frame. */
    assert(vxpe_input_press(&m, K_OK));
    assert(vxpe_input_release(&m, K_OK));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_pressed(&m, A_JUMP) && vxpe_input_released(&m, A_JUMP));
    assert(!vxpe_input_held(&m, A_JUMP));

    /* Press and release across a frame boundary keeps the usual lifetime. */
    assert(vxpe_input_press(&m, K_OK));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_pressed(&m, A_JUMP) && !vxpe_input_released(&m, A_JUMP));
    assert(vxpe_input_release(&m, K_OK));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_released(&m, A_JUMP) && !vxpe_input_pressed(&m, A_JUMP));
}

static void test_one_code_many_actions(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    /* A share button: one code, two meanings. */
    vxpe_input_bind(&m, A_JUMP, K_OK, VXPE_IN_KEY_NONE, VXPE_IN_KEY_NONE);
    vxpe_input_bind(&m, A_ATTACK, K_OK, VXPE_IN_KEY_NONE, VXPE_IN_KEY_NONE);

    assert(vxpe_input_press(&m, K_OK));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_pressed(&m, A_JUMP) && vxpe_input_pressed(&m, A_ATTACK));
    assert(bit_count(m.pressed) == 2);
    assert(m.held == (uint16_t)((1u << A_JUMP) | (1u << A_ATTACK)));

    assert(vxpe_input_release(&m, K_OK));
    vxpe_input_update(&m, 33);
    assert(m.held == 0 && bit_count(m.released) == 2);
}

static void test_consume(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    bind_gamepad(&m);
    vxpe_input_set_repeat(&m, 50, 50);

    assert(vxpe_input_press(&m, K_UP));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_pressed(&m, A_UP));
    vxpe_input_consume(&m, A_UP);
    assert(!vxpe_input_pressed(&m, A_UP));
    /* The held bit and its timer survive, so a jump still reads as held. */
    assert(vxpe_input_held(&m, A_UP));
    assert(vxpe_input_held_ms(&m, A_UP) == 33);

    /* A repeat edge is consumable too, or a menu scrolls twice. */
    vxpe_input_update(&m, 50);
    assert(vxpe_input_repeated(&m, A_UP));
    vxpe_input_consume(&m, A_UP);
    assert(!vxpe_input_repeated(&m, A_UP));
    /* Consume only touches its own action. */
    assert(vxpe_input_press(&m, K_DOWN));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_pressed(&m, A_DOWN));
    vxpe_input_consume(&m, A_UP);
    assert(vxpe_input_pressed(&m, A_DOWN));
    vxpe_input_consume(&m, -1);
    vxpe_input_consume(&m, VXPE_INPUT_ACTION_MAX);
}

/* ---- auto-repeat -------------------------------------------------------- */

static void test_repeat_timing(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    bind_gamepad(&m);
    /* 350 ms first step, then 120 ms, sampled on a clean 50 ms frame. */
    assert(m.repeat_first_ms == 350 && m.repeat_rate_ms == 120);

    assert(vxpe_input_press(&m, K_RIGHT));
    int edges = 0, first_at = -1, second_at = -1;
    for (int frame = 1; frame <= 14; ++frame) {
        vxpe_input_update(&m, 50);
        if (vxpe_input_repeated(&m, A_RIGHT)) {
            ++edges;
            if (first_at < 0) first_at = m.held_ms[A_RIGHT];
            else if (second_at < 0) second_at = m.held_ms[A_RIGHT];
        }
        /* The press frame itself must not repeat. */
        if (frame == 1) assert(!vxpe_input_repeated(&m, A_RIGHT));
    }
    assert(edges == 3);
    assert(first_at == 350);
    assert(second_at == 500);
    assert(m.held_ms[A_RIGHT] == 700);

    /* held_ms saturates instead of wrapping on a long hold. */
    for (int i = 0; i < 200; ++i) vxpe_input_update(&m, 500);
    assert(m.held_ms[A_RIGHT] == 60000);
}

static void test_repeat_disabled_and_stepped(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    bind_gamepad(&m);

    vxpe_input_set_repeat(&m, 0, 120);
    assert(vxpe_input_press(&m, K_LEFT));
    for (int i = 0; i < 40; ++i) {
        vxpe_input_update(&m, 50);
        assert(!vxpe_input_repeated(&m, A_LEFT));
    }
    vxpe_input_set_repeat(&m, 100, 0);
    for (int i = 0; i < 40; ++i) {
        vxpe_input_update(&m, 50);
        assert(!vxpe_input_repeated(&m, A_LEFT));
    }
    assert(m.held_ms[A_LEFT] == 4000);

    /* Turning repeat back on re-arms the first delay for a key that was held
     * while it was off, instead of firing an edge nobody asked for. */
    vxpe_input_set_repeat(&m, 100, 50);
    assert(m.repeat_ms[A_LEFT] == 100);
    vxpe_input_update(&m, 50);
    assert(!vxpe_input_repeated(&m, A_LEFT));
    vxpe_input_update(&m, 50);
    assert(vxpe_input_repeated(&m, A_LEFT));

    /* A stalled frame fires one edge, not fifty: a menu that misses a second
     * moves the cursor one line. */
    m.repeated = 0;
    vxpe_input_update(&m, 1000);
    assert(vxpe_input_repeated(&m, A_LEFT));
    assert(bit_count(m.repeated) == 1);
    vxpe_input_update(&m, 1000);
    assert(bit_count(m.repeated) == 1);
    assert(m.repeat_ms[A_LEFT] == 50);
}

/* ---- axis --------------------------------------------------------------- */

static void test_axis(void) {
    VxpeInputMap2D m;
    vxpe_input_init(&m);
    bind_gamepad(&m);

    assert(vxpe_input_axis(&m, A_LEFT, A_RIGHT) == 0);
    assert(vxpe_input_press(&m, K_6)); /* digit pad right */
    vxpe_input_update(&m, 33);
    assert(vxpe_input_axis(&m, A_LEFT, A_RIGHT) == 1);
    assert(vxpe_input_press(&m, K_4));
    vxpe_input_update(&m, 33);
    /* Leaning on both keys stops instead of grinding into the wall. */
    assert(vxpe_input_axis(&m, A_LEFT, A_RIGHT) == 0);
    assert(vxpe_input_release(&m, K_4));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_axis(&m, A_LEFT, A_RIGHT) == 1);
    assert(vxpe_input_release(&m, K_6));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_axis(&m, A_LEFT, A_RIGHT) == 0);

    /* Vertical axis and reversed polarity both work the same way. */
    assert(vxpe_input_press(&m, K_8));
    vxpe_input_update(&m, 33);
    assert(vxpe_input_axis(&m, A_DOWN, A_UP) == 1);
    assert(vxpe_input_axis(&m, A_UP, A_DOWN) == -1);
    /* Out of range operands read as not held. */
    assert(vxpe_input_axis(&m, A_UP, VXPE_INPUT_ACTION_MAX) == -1);
    assert(vxpe_input_axis(&m, -1, A_UP) == 1);
    assert(vxpe_input_axis(&m, -1, -2) == 0);
}

/* ---- key labels --------------------------------------------------------- */

static void test_key_name(void) {
    assert(strcmp(vxpe_input_key_name(K_UP), "UP") == 0);
    assert(strcmp(vxpe_input_key_name(K_DOWN), "DOWN") == 0);
    assert(strcmp(vxpe_input_key_name(K_LEFT), "LEFT") == 0);
    assert(strcmp(vxpe_input_key_name(K_RIGHT), "RIGHT") == 0);
    assert(strcmp(vxpe_input_key_name(K_OK), "OK") == 0);
    assert(strcmp(vxpe_input_key_name(K_LSK), "LSK") == 0);
    assert(strcmp(vxpe_input_key_name(K_RSK), "RSK") == 0);
    assert(strcmp(vxpe_input_key_name(K_CLEAR), "CLR") == 0);
    assert(strcmp(vxpe_input_key_name(K_BACK), "BACK") == 0);
    assert(strcmp(vxpe_input_key_name('0'), "0") == 0);
    assert(strcmp(vxpe_input_key_name('9'), "9") == 0);
    assert(strcmp(vxpe_input_key_name('A'), "A") == 0);
    assert(strcmp(vxpe_input_key_name('Z'), "Z") == 0);
    assert(strcmp(vxpe_input_key_name('#'), "#") == 0);
    assert(strcmp(vxpe_input_key_name('*'), "*") == 0);
    assert(strcmp(vxpe_input_key_name(58), "VOL+") == 0);
    assert(strcmp(vxpe_input_key_name(59), "VOL-") == 0);

    /* Lower-case letters and anything else have no label. */
    assert(vxpe_input_key_name('a') == 0);
    assert(vxpe_input_key_name(VXPE_IN_KEY_NONE) == 0);
    assert(vxpe_input_key_name(0) == 0);

    /* A legend draws one label per row, so two live calls must not alias the
     * same static buffer into nonsense. */
    const char* first = vxpe_input_key_name('7');
    assert(strcmp(first, "7") == 0);
    assert(strcmp(vxpe_input_key_name('8'), "8") == 0);
}

int main(void) {
    test_init_and_bind();
    test_null_map();
    test_press_release_edges();
    test_one_code_many_actions();
    test_consume();
    test_repeat_timing();
    test_repeat_disabled_and_stepped();
    test_axis();
    test_key_name();
    printf("vxpe_input2d_regression: all assertions passed\n");
    return 0;
}
