/* Allocation-free RGB565 colour grading for QVGA game scenes. */
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef enum VxpeGradeStyle {
    VXPE_GRADE_NEUTRAL = 0,
    VXPE_GRADE_COZY_FARM,
    VXPE_GRADE_DARK_FANTASY,
    VXPE_GRADE_NEON_ACTION,
    VXPE_GRADE_PASTEL,
    VXPE_GRADE_RETRO_HANDHELD
} VxpeGradeStyle;

/* Independent channel LUTs occupy 256 bytes. Build once, reuse each frame. */
typedef struct VxpeColorGrade565 {
    uint16_t red[32];
    uint16_t green[64];
    uint16_t blue[32];
} VxpeColorGrade565;

void vxpe_grade_init(VxpeColorGrade565* grade, VxpeGradeStyle style);
uint16_t vxpe_grade_color(const VxpeColorGrade565* grade, uint16_t color);
/* In-place clipped rectangle; stride is in pixels and must be >= width.
 * Apply to the gameplay area before drawing HUD. No heap or floating point.
 */
void vxpe_grade_rect(const VxpeColorGrade565* grade, uint16_t* pixels,
    int width, int height, int stride, int x, int y, int w, int h);
#ifdef __cplusplus
}
#endif
