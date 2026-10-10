/* Minimal timing/log compatibility for the S30+ MRE runtime. */
#pragma once

#include <cstdint>

extern "C" {
#include <vmsys.h>
}

inline uint32_t millis() {
    return static_cast<uint32_t>(vm_get_tick_count());
}

inline uint32_t micros() {
    return millis() * 1000U;
}

inline void delay(uint32_t) {
    /* MRE is event driven: blocking the VM callback would reduce responsiveness. */
}

inline void yield() {}
