/*
 * The input map is the C template's key layer, so it must compile and run from
 * plain C99 with no C++ symbol in sight: designated initialisers for the
 * bindings and a frame loop in the shape a main.c actually has. Language
 * binding gate - edge arithmetic is covered by vxpe_input2d_regression.cpp.
 */
#include "action2d/VxpInputMap2D.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

enum { A_LEFT, A_RIGHT, A_UP, A_DOWN, A_JUMP, A_ATTACK, A_START, A_PAUSE, A_COUNT };

int main(void) {
    VxpeInputMap2D input;
    /* The three-slot table a C game fills at boot: arrows first, the digit pad
     * as the fallback every handset keyboard also has. */
    static const int16_t bindings[A_COUNT][VXPE_INPUT_KEYS_PER_ACTION] = {
        { -3, 52, VXPE_IN_KEY_NONE },  /* left:  LEFT,  "4" */
        { -4, 54, VXPE_IN_KEY_NONE },  /* right: RIGHT, "6" */
        { -1, 56, VXPE_IN_KEY_NONE },  /* up:    UP,    "8" */
        { -2, 50, VXPE_IN_KEY_NONE },  /* down:  DOWN,  "2" */
        { -5, 90, VXPE_IN_KEY_NONE },  /* jump:  OK,    "Z" */
        { -6, 88, VXPE_IN_KEY_NONE },  /* attack: LSK,  "X" */
        { -8, -7, VXPE_IN_KEY_NONE },  /* start:  CLR,  RSK */
        { -9, 35, VXPE_IN_KEY_NONE }   /* pause:  BACK, "#" */
    };
    char label[16];
    int a, s, frames;

    vxpe_input_init(&input);
    for (a = 0; a < A_COUNT; ++a) {
        vxpe_input_bind(&input, a, bindings[a][0], bindings[a][1], bindings[a][2]);
    }
    for (s = 0; s < VXPE_INPUT_KEYS_PER_ACTION; ++s) {
        assert(input.keys[A_LEFT][s] == bindings[A_LEFT][s]);
    }

    /* A run of frames where the player walks right, taps jump once and holds
     * left long enough for the auto-repeat to take over. */
    vxpe_input_press(&input, -4);
    frames = 0;
    for (; frames < 10; ++frames) {
        vxpe_input_update(&input, 33);
    }
    assert(vxpe_input_held(&input, A_RIGHT) && !vxpe_input_pressed(&input, A_RIGHT));
    assert(vxpe_input_axis(&input, A_LEFT, A_RIGHT) == 1);
    vxpe_input_release(&input, -4);

    /* A tap between two frames still reports both edges. */
    vxpe_input_press(&input, -5);
    vxpe_input_release(&input, -5);
    vxpe_input_update(&input, 33);
    assert(vxpe_input_pressed(&input, A_JUMP) && vxpe_input_released(&input, A_JUMP));
    vxpe_input_consume(&input, A_JUMP);
    assert(!vxpe_input_pressed(&input, A_JUMP));

    /* Held past the first delay: the menu would step. */
    vxpe_input_press(&input, -3);
    for (frames = 0; frames < 12; ++frames) vxpe_input_update(&input, 33);
    assert(vxpe_input_held(&input, A_LEFT));
    assert(vxpe_input_axis(&input, A_LEFT, A_RIGHT) == -1);
    assert(vxpe_input_held_ms(&input, A_LEFT) == 396);
    vxpe_input_release(&input, -3);
    vxpe_input_update(&input, 33);
    assert(!vxpe_input_held(&input, A_LEFT));

    /* Unknown codes are the app's to handle (a dialler key, a hard-wired volume). */
    assert(!vxpe_input_press(&input, 'Q'));
    assert(vxpe_input_press(&input, '8'));
    assert(vxpe_input_release(&input, '8'));

    /* A key legend line built without sprintf. */
    strcpy(label, "Jump: ");
    strcat(label, vxpe_input_key_name(-5));
    assert(strcmp(label, "Jump: OK") == 0);
    assert(strcmp(vxpe_input_key_name(90), "Z") == 0);
    assert(vxpe_input_key_name(122) == 0);

    vxpe_input_set_repeat(&input, 0, 0);
    for (frames = 0; frames < 20; ++frames) {
        vxpe_input_update(&input, 33);
        assert(!vxpe_input_repeated(&input, A_LEFT));
    }

    printf("input2d C API ok\n");
    return 0;
}
