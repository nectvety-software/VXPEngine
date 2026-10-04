#include <stdio.h>
#include "vmsys.h"
#include "vmchset.h"
#include "vmlog.h"
#include "vmio.h"

VMUINT _saved_sp;
VMUINT _init_param;

#ifdef __cplusplus
extern "C" {
#endif 
typedef VMINT (*vm_get_sym_entry_t)(char* symbol);
vm_get_sym_entry_t vm_get_sym_entry;

extern VMUINT _get_mre_sym_entry(void);
extern VMUINT _get_saved_sp(void);
extern VMUINT _get_init_param(void);
extern void _quit(VMUINT saved_sp);

#ifdef __cplusplus
}
#endif 


int main(void) {
	vm_get_sym_entry = (vm_get_sym_entry_t)_get_mre_sym_entry();
	_saved_sp = _get_saved_sp();
	_init_param = _get_init_param();
	
	vm_main();
	_quit(_saved_sp);
	
	return 0;
}
