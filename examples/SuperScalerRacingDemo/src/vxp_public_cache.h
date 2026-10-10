/* Public-storage cache scaffold for generated VXP projects. Store compact game state, not bundled art. */
#ifndef VXPE_PUBLIC_CACHE_H
#define VXPE_PUBLIC_CACHE_H
#include "vmsys.h"
#include "vmio.h"
#include "vmchset.h"
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#ifndef VXPE_APP_ID
#define VXPE_APP_ID 1
#endif
typedef struct { uint32_t magic, version, payload_bytes; } VxpeCacheHeader;
static VMCHAR vxpe_cache_dir[96], vxpe_cache_file[128], vxpe_cache_tmp[144];
static int vxpe_cache_ready;
static void vxpe_cache_init(void) {
    VMINT drive = vm_get_removable_driver(); char path[112], tmp[128];
    if (drive < 0) drive = vm_get_system_driver();
    if (drive < 0) return;
    snprintf(path, sizeof(path), "%c:\\@vxp_%08lx", (char)drive, (unsigned long)VXPE_APP_ID);
    if (vm_ascii_to_ucs2((VMWSTR)vxpe_cache_dir, sizeof(vxpe_cache_dir), path) < 0) return;
    snprintf(path, sizeof(path), "%c:\\@vxp_%08lx\\save.bin", (char)drive, (unsigned long)VXPE_APP_ID);
    snprintf(tmp, sizeof(tmp), "%s.tmp", path);
    if (vm_ascii_to_ucs2((VMWSTR)vxpe_cache_file, sizeof(vxpe_cache_file), path) < 0 ||
        vm_ascii_to_ucs2((VMWSTR)vxpe_cache_tmp, sizeof(vxpe_cache_tmp), tmp) < 0) return;
    vm_file_mkdir((VMWSTR)vxpe_cache_dir); vxpe_cache_ready = 1;
}
static int vxpe_cache_read_path(const VMWSTR path, void *payload, uint32_t bytes) {
    VxpeCacheHeader h; VMUINT n=0; VMFILE f=vm_file_open(path,MODE_READ,1); VMINT rc;
    if(f<0)return 0; rc=vm_file_read(f,&h,sizeof(h),&n);
    if(rc<=0||n!=sizeof(h)||h.magic!=0x56585043u||h.version!=1u||h.payload_bytes!=bytes){vm_file_close(f);return 0;}
    n=0;rc=vm_file_read(f,payload,bytes,&n);vm_file_close(f);return rc>0&&n==bytes;
}
static int vxpe_cache_load(void *payload,uint32_t bytes) {
    if(!vxpe_cache_ready||!payload||!bytes)return 0;
    if(vxpe_cache_read_path((VMWSTR)vxpe_cache_file,payload,bytes))return 1;
    if(vxpe_cache_read_path((VMWSTR)vxpe_cache_tmp,payload,bytes)){vm_file_delete((VMWSTR)vxpe_cache_file);vm_file_rename((VMWSTR)vxpe_cache_tmp,(VMWSTR)vxpe_cache_file);return 1;}
    return 0;
}
static int vxpe_cache_save(const void *payload,uint32_t bytes) {
    VxpeCacheHeader h={0x56585043u,1u,bytes};VMUINT n=0;VMFILE f;VMINT rc;int ok=0;
    if(!vxpe_cache_ready||!payload||!bytes||bytes>65536u)return 0;
    f=vm_file_open((VMWSTR)vxpe_cache_tmp,MODE_CREATE_ALWAYS_WRITE,1);if(f<0)return 0;
    rc=vm_file_write(f,&h,sizeof(h),&n);
    if(rc>0&&n==sizeof(h)){n=0;rc=vm_file_write(f,(void*)payload,bytes,&n);if(rc>0&&n==bytes&&vm_file_commit(f)==0)ok=1;}
    vm_file_close(f);if(ok){vm_file_delete((VMWSTR)vxpe_cache_file);ok=vm_file_rename((VMWSTR)vxpe_cache_tmp,(VMWSTR)vxpe_cache_file)==0;}return ok;
}
#endif
