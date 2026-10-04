/* gfx.h - direct RGB565 blitting into the MRE layer buffer */
#ifndef CTBD_GFX_H
#define CTBD_GFX_H

#include "vmsys.h"
#include "res.h"

#define RGB(r, g, b) (VMUINT16)((((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3))

#define C_WHITE  RGB(255, 255, 255)
#define C_BLACK  RGB(0, 0, 0)
#define C_RED    RGB(230, 40, 40)
#define C_DKRED  RGB(120, 16, 16)
#define C_GREEN  RGB(60, 200, 80)
#define C_BLUE   RGB(60, 130, 230)
#define C_DKBLUE RGB(16, 30, 110)
#define C_GOLD   RGB(255, 200, 40)
#define C_PURPLE RGB(180, 90, 240)
#define C_GREY   RGB(140, 140, 150)
#define C_DKGREY RGB(50, 50, 60)
#define C_ORANGE RGB(255, 140, 30)

void gfx_set_fb(VMUINT8* buf, int w, int h);
void gfx_clear(VMUINT16 color);
void gfx_px(int x, int y, VMUINT16 c);
void gfx_fill(int x, int y, int w, int h, VMUINT16 c);
void gfx_frame(int x, int y, int w, int h, VMUINT16 c);
void gfx_blit(int id, int x, int y, int flip);          /* masked sprite */
void gfx_blit_op(int id, int x, int y);                 /* opaque sprite */
void gfx_blit_scaled(int id, int x, int y, int w, int h, int flip);
void gfx_blit_bright(int id, int x, int y, int flip, int boost); /* brightened blit */
void gfx_blit_scaled_bright(int id, int x, int y, int w, int h, int flip, int boost);
void gfx_tint(int id, int x, int y, int flip, VMUINT16 tint); /* solid-color silhouette (cooldown) */
void gfx_text(int x, int y, const char* s, VMUINT16 c);
void gfx_text_c(int cx, int y, const char* s, VMUINT16 c);
int  gfx_text_w(const char* s);
void gfx_bar(int x, int y, int w, int h, int ratio /*0..100*/, VMUINT16 fill, VMUINT16 back);

#endif
