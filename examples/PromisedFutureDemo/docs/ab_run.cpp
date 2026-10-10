#include "scene.h"
#include <string.h>
static uint16_t bufA[240*320], bufB[240*320];
extern "C" void probe_reset();
extern "C" int probe_count();
uint16_t* aff_buf_a(){return bufA;}
uint16_t* aff_buf_b(){return bufB;}
int aff_run_a(){ static PromisedFuture g; g.input(5); probe_reset(); g.draw(bufA); return probe_count(); }
int aff_run_b(){ static PromisedFuture g; g.input(5); probe_reset(); g.draw(bufB); return probe_count(); }
