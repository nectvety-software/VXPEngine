#include "graphics/VxpColorGrade.h"

static int channel(int value, int contrast, int lift) {
    int result = ((value - 128) * contrast) / 256 + 128 + lift;
    return result < 0 ? 0 : (result > 255 ? 255 : result);
}

void vxpe_grade_init(VxpeColorGrade565* grade, VxpeGradeStyle style) {
    if (!grade) return;
    int contrast = 256, r = 0, g = 0, b = 0;
    switch (style) {
    case VXPE_GRADE_COZY_FARM: contrast = 270; r = 10; g = 8; b = -8; break;
    case VXPE_GRADE_DARK_FANTASY: contrast = 300; r = -12; g = -16; b = 2; break;
    case VXPE_GRADE_NEON_ACTION: contrast = 320; r = 8; g = -8; b = 16; break;
    case VXPE_GRADE_PASTEL: contrast = 210; r = 14; g = 10; b = 16; break;
    case VXPE_GRADE_RETRO_HANDHELD: contrast = 280; r = -8; g = 12; b = -20; break;
    default: break;
    }
    for (int i = 0; i < 32; ++i) {
        const int value = (i * 255 + 15) / 31;
        grade->red[i] = (uint16_t)((channel(value, contrast, r) >> 3) << 11);
        grade->blue[i] = (uint16_t)(channel(value, contrast, b) >> 3);
    }
    for (int i = 0; i < 64; ++i)
        grade->green[i] = (uint16_t)((channel((i * 255 + 31) / 63, contrast, g) >> 2) << 5);
}

uint16_t vxpe_grade_color(const VxpeColorGrade565* grade, uint16_t color) {
    if (!grade) return color;
    return (uint16_t)(grade->red[color >> 11] |
        grade->green[(color >> 5) & 63] | grade->blue[color & 31]);
}

void vxpe_grade_rect(const VxpeColorGrade565* grade, uint16_t* pixels,
    int width, int height, int stride, int x, int y, int w, int h) {
    if (!grade || !pixels || width <= 0 || height <= 0 || stride < width || w <= 0 || h <= 0) return;
    /* Widen before addition to avoid overflow from offscreen input. */
    int64_t right = (int64_t)x + w, bottom = (int64_t)y + h;
    if (right <= 0 || bottom <= 0 || x >= width || y >= height) return;
    int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y;
    int x1 = right > width ? width : (int)right;
    int y1 = bottom > height ? height : (int)bottom;
    for (int row = y0; row < y1; ++row) {
        uint16_t* line = pixels + (int64_t)row * stride;
        for (int col = x0; col < x1; ++col) line[col] = vxpe_grade_color(grade, line[col]);
    }
}
