/* res.h - packed resource access (sprites baked by AssetTool into resources.res) */
#ifndef CTBD_RES_H
#define CTBD_RES_H

#include "vmsys.h"

/* sprite ids - order must match spr_names[] in sprite_ids.c */
enum {
    SPR_GROUND1, SPR_GROUND2, SPR_GROUND3, SPR_GROUND4,
    SPR_GH1, SPR_GH2, SPR_GH3,
    SPR_WALL1, SPR_WALL2, SPR_WALL3, SPR_WALL4, SPR_WALL5, SPR_WALL6,
    SPR_BLOCK, SPR_SPIKES, SPR_LADDER, SPR_WINDOW, SPR_CHAIN1, SPR_CHAIN2,
    SPR_SHOPDOOR, SPR_ARCHWAY, SPR_CRATE, SPR_BARREL, SPR_BANNER,
    SPR_PILLAR, SPR_RUBBLE, SPR_COLLAPSED,
    SPR_ARCH_A, SPR_ARCH_B, SPR_ARCH_C, SPR_ARCH_D, SPR_ARCH_SHOOT, SPR_ARCH_HIT,
    SPR_OGRE_A, SPR_OGRE_B, SPR_OGRE_C, SPR_OGRE_HIT, SPR_BOSS_OGRE,
    SPR_DRAGON_A, SPR_DRAGON_B, SPR_DRAGON_C,
    SPR_TORCH1, SPR_TORCH2, SPR_TORCH3, SPR_TORCH4,
    SPR_COIN, SPR_GEM, SPR_SPARK_S, SPR_SPARK_B,
    SPR_ARROW1, SPR_ARROW2, SPR_ARROW3,
    SPR_IC_GOLD, SPR_IC_SILVER, SPR_IC_GEM, SPR_IC_HPOTION, SPR_IC_MPOTION,
    SPR_IC_QUIVER, SPR_PORTRAIT,
    SPR_BADGE_DASH, SPR_BADGE_POWER, SPR_BADGE_MULTI,
    SPR_BTN_DASH, SPR_BTN_POWER, SPR_BTN_MULTI,
    SPR_BG_FAR, SPR_BG_MID, SPR_BG_NEAR,
    SPR_TEX_BRICK, SPR_TEX_WOOD, SPR_TEX_FOG,
    SPR_SPLASH,
    SPR_COUNT
};

typedef struct {
    VMUINT8* data;   /* header 8B + rgb565 + mask */
    int w, h, opaque;
} sprite_t;

int       res_init(void);   /* 0 = ok */
void      res_free(void);
sprite_t* spr(int id);

/* data folder ("X:\@CungThuBongDen") + sfx extraction + save helpers */
extern char g_data_dir[64];
int  res_prepare_storage(void);            /* 0 = ok */
void sfx_play(int id);                     /* 0 shoot 1 hit 2 pickup 3 explode */
void save_write(int hi_score);
int  save_read(void);                      /* returns hi score */

#endif
