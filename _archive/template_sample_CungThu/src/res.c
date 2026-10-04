/* res.c - sprite loading, storage folder, sfx extraction, save file */
#include "vmres.h"
#include "vmio.h"
#include "vmchset.h"
#include "vmstdlib.h"
#include "vmmm.h"
#include <stdio.h>
#include <string.h>

#include "res.h"

static sprite_t S[SPR_COUNT];

/* order must match enum in res.h */
const char* spr_names[SPR_COUNT] = {
    "ground1", "ground2", "ground3", "ground4",
    "gh1", "gh2", "gh3",
    "wall1", "wall2", "wall3", "wall4", "wall5", "wall6",
    "block", "spikes", "ladder", "window", "chain1", "chain2",
    "shopdoor", "archway", "crate", "barrel", "banner",
    "pillar", "rubble", "collapsed",
    "arch_a", "arch_b", "arch_c", "arch_d", "arch_shoot", "arch_hit",
    "ogre_a", "ogre_b", "ogre_c", "ogre_hit", "boss_ogre",
    "dragon_a", "dragon_b", "dragon_c",
    "torch1", "torch2", "torch3", "torch4",
    "coin", "gem", "spark_s", "spark_b",
    "arrow1", "arrow2", "arrow3",
    "ic_gold", "ic_silver", "ic_gem", "ic_hpotion", "ic_mpotion",
    "ic_quiver", "portrait",
    "badge_dash", "badge_power", "badge_multi",
    "btn_dash", "btn_power", "btn_multi",
    "bg_far", "bg_mid", "bg_near",
    "tex_brick", "tex_wood", "tex_fog",
    "splash"
};

#define DATA_FOLDER "@CungThuBongDen"
char g_data_dir[64] = "E:\\@CungThuBongDen";

static const char* sfx_names[4] = { "sfx_shoot.mp3", "sfx_hit.mp3", "sfx_pickup.mp3", "sfx_explode.mp3" };
static const char* sfx_res[4] = { "sfx_shoot.mp3", "sfx_hit.mp3", "sfx_pickup.mp3", "sfx_explode.mp3" };

sprite_t* spr(int id) { return &S[id]; }

int res_init(void) {
    int i;
    memset(S, 0, sizeof(S));
    for (i = 0; i < SPR_COUNT; i++) {
        char name[48];
        VMINT size = 0;
        VMUINT8* p;
        sprintf(name, "%s.raw", spr_names[i]);
        p = vm_load_resource(name, &size);
        if (!p) return -1;
        S[i].data = p;
        S[i].w = p[0] | (p[1] << 8);
        S[i].h = p[2] | (p[3] << 8);
        S[i].opaque = p[4];
    }
    return 0;
}

void res_free(void) {
    int i;
    for (i = 0; i < SPR_COUNT; i++) {
        if (S[i].data) vm_free(S[i].data);
        S[i].data = 0;
    }
}

static int file_exists(const char* path) {
    VMCHAR w[128];
    VMFILE f;
    vm_ascii_to_ucs2((VMWSTR)w, sizeof(w), (VMSTR)path);
    f = vm_file_open((VMWSTR)w, MODE_READ, 1);
    if (f < 0) return 0;
    vm_file_close(f);
    return 1;
}

/* extract an mp3 packed in the .vxp resources to the data folder (once) */
static void extract_sfx(int id) {
    char path[96];
    VMCHAR wpath[192];
    VMINT size = 0;
    VMUINT written = 0;
    VMFILE f;
    VMUINT8* res;

    sprintf(path, "%s\\%s", g_data_dir, sfx_names[id]);
    if (file_exists(path)) return;

    res = vm_load_resource((char*)sfx_res[id], &size);
    if (!res || size <= 0) { if (res) vm_free(res); return; }

    vm_ascii_to_ucs2((VMWSTR)wpath, sizeof(wpath), (VMSTR)path);
    f = vm_file_open((VMWSTR)wpath, MODE_CREATE_ALWAYS_WRITE, 1);
    if (f >= 0) {
        vm_file_write(f, res, (VMUINT)size, &written);
        vm_file_close(f);
    }
    vm_free(res);
}

int res_prepare_storage(void) {
    VMCHAR wdrv[8], wdir[64];
    int drv, i, cand[2], n = 0;

    i = vm_get_removable_driver();
    if (i >= 0) cand[n++] = i;
    i = vm_get_system_driver();
    if (i >= 0 && (n == 0 || i != cand[0])) cand[n++] = i;
    if (n == 0) cand[n++] = 'E';
    drv = cand[0];

    sprintf(g_data_dir, "%c:\\%s", drv, DATA_FOLDER);
    vm_ascii_to_ucs2((VMWSTR)wdir, sizeof(wdir), (VMSTR)g_data_dir);
    vm_file_mkdir((VMWSTR)wdir); /* ok if exists */

    for (i = 0; i < 4; i++) extract_sfx(i);
    return 0;
}

void sfx_play(int id) {
    char path[96];
    VMCHAR wpath[192];
    if (id < 0 || id > 3) return;
    sprintf(path, "%s\\%s", g_data_dir, sfx_names[id]);
    if (!file_exists(path)) return;
    vm_ascii_to_ucs2((VMWSTR)wpath, sizeof(wpath), (VMSTR)path);
    vm_audio_stop_all();
    vm_audio_play_file((VMWSTR)wpath, 0);
}

static char* save_path(char* out) { sprintf(out, "%s\\save.dat", g_data_dir); return out; }

void save_write(int hi_score) {
    char path[96], text[64];
    VMCHAR wpath[192];
    VMFILE f;
    VMUINT written = 0;
    sprintf(text, "hi=%d", hi_score);
    vm_ascii_to_ucs2((VMWSTR)wpath, sizeof(wpath), (VMSTR)save_path(path));
    f = vm_file_open((VMWSTR)wpath, MODE_CREATE_ALWAYS_WRITE, 1);
    if (f < 0) return;
    vm_file_write(f, text, strlen(text), &written);
    vm_file_close(f);
}

int save_read(void) {
    char path[96], text[64];
    VMCHAR wpath[192];
    VMFILE f;
    VMUINT nread = 0;
    int hi = 0;
    text[0] = 0;
    vm_ascii_to_ucs2((VMWSTR)wpath, sizeof(wpath), (VMSTR)save_path(path));
    f = vm_file_open((VMWSTR)wpath, MODE_READ, 1);
    if (f < 0) return 0;
    vm_file_read(f, text, sizeof(text) - 1, &nread);
    vm_file_close(f);
    text[nread > 0 ? nread : 0] = 0;
    if (strncmp(text, "hi=", 3) == 0) hi = atoi(text + 3);
    if (hi < 0) hi = 0;
    return hi;
}
