#include "graphics/VxpColorGrade.h"
#include <assert.h>
#include <limits.h>

int main() {
    VxpeColorGrade565 grade;
    vxpe_grade_init(&grade, VXPE_GRADE_NEUTRAL);
    for (unsigned i = 0; i < 65536; ++i)
        assert(vxpe_grade_color(&grade, (uint16_t)i) == i);
    uint16_t fb[15];
    for (int i = 0; i < 15; ++i) fb[i] = 0x8410;
    vxpe_grade_init(&grade, VXPE_GRADE_NEON_ACTION);
    uint16_t changed = vxpe_grade_color(&grade, 0x8410);
    assert(changed != 0x8410);
    vxpe_grade_rect(&grade, fb, 3, 3, 5, -1, -1, 3, 3);
    for (int y = 0; y < 3; ++y)
        for (int x = 0; x < 5; ++x)
            assert(fb[y*5+x] == ((y < 2 && x < 2) ? changed : 0x8410));
    vxpe_grade_rect(&grade, fb, 3, 3, 5, INT_MAX, 0, INT_MAX, 3);
    vxpe_grade_rect(&grade, fb, 3, 3, 2, 0, 0, 3, 3);
    assert(fb[14] == 0x8410);
    assert(vxpe_grade_color(0, 0x1234) == 0x1234);
    for (int style = 0; style <= VXPE_GRADE_RETRO_HANDHELD; ++style) {
        vxpe_grade_init(&grade, (VxpeGradeStyle)style);
        for (int i = 1; i < 32; ++i) {
            assert(grade.red[i] >= grade.red[i-1]);
            assert(grade.blue[i] >= grade.blue[i-1]);
        }
    }
    return 0;
}
