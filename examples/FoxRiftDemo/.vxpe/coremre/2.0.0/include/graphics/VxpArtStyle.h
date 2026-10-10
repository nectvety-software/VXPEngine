/* VxpArtStyle - fixed-memory visual style profiles for MRE/VXP. */
#pragma once
#include <stdint.h>
#include "graphics/VxpScene25D.h"
#include "graphics/VxpSpriteFx.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef enum VxpeArtStyleId {
    VXPE_ARTSTYLE_NEUTRAL=0,VXPE_ARTSTYLE_PIXEL_CLASSIC,VXPE_ARTSTYLE_PIXEL_MODERN,
    VXPE_ARTSTYLE_COZY_FARM,VXPE_ARTSTYLE_DARK_FANTASY,VXPE_ARTSTYLE_NEON_ACTION,
    VXPE_ARTSTYLE_PASTEL_PLATFORMER,VXPE_ARTSTYLE_RETRO_HANDHELD,VXPE_ARTSTYLE_CEL_SHADED,
    VXPE_ARTSTYLE_SATURATED_ADVENTURE,VXPE_ARTSTYLE_STRATEGY_RPG,VXPE_ARTSTYLE_PAINTERLY,
    VXPE_ARTSTYLE_LOW_POLY_25D,VXPE_ARTSTYLE_URBAN_TOON,VXPE_ARTSTYLE_DUNGEON_SYNTH,VXPE_ARTSTYLE_COUNT
} VxpeArtStyleId;
typedef enum VxpeArtStyleRole {
    VXPE_ARTSTYLE_ROLE_ASSET=0,VXPE_ARTSTYLE_ROLE_SPRITE,VXPE_ARTSTYLE_ROLE_ENVIRONMENT,
    VXPE_ARTSTYLE_ROLE_UI,VXPE_ARTSTYLE_ROLE_VFX
} VxpeArtStyleRole;
typedef struct VxpeArtStyleProfile {
    uint8_t id,role,posterize_levels,saturation_q7,contrast_q7,postprocess,dither_strength,vignette_alpha;
    uint16_t tint565; uint8_t tint_alpha;
    uint16_t fog_color565; uint8_t fog_strength;
    VxpeSpriteFxStyle sprite_fx;
    uint16_t trail_color565; uint8_t trail_alpha,trail_width;
    uint16_t light_color565; uint8_t light_alpha;
} VxpeArtStyleProfile;
void vxpe_artstyle_init(VxpeArtStyleProfile* profile,VxpeArtStyleId id);
const char* vxpe_artstyle_name(VxpeArtStyleId id);
void vxpe_artstyle_apply_scene25d(const VxpeArtStyleProfile*,VxpeCamera25D*,VxpeGrade25D*);
void vxpe_artstyle_apply_sprite_fx(const VxpeArtStyleProfile*,VxpeSpriteFxStyle*);
void vxpe_artstyle_postprocess565(uint16_t* fb,int fb_w,int fb_h,const VxpeArtStyleProfile*);
#ifdef __cplusplus
}
#endif
