/*
 * Copyright (c) 2026 PixelRoot32
 * Licensed under the MIT License
 */
#pragma once

#include "core/Log.h"

#if defined(COREMRE_PLATFORM_MRE)
    extern "C" {
    #include <vmlog.h>
    }
#elif defined(ESP32)
    #include <Arduino.h>
#else
    #include <cstdio>
#endif

/**
 * @namespace pixelroot32::core::logging
 * @brief Platform-specific logging utilities.
 * This namespace provides logging functions that work across different platforms,
 * including ESP32 and native environments.
 */
namespace pixelroot32::core::logging
{
    /**
     * @brief Converts a log level to its string representation.
     * @param level The log level to convert.
     * @return A string representation of the log level.
     */
    inline const char* levelToString(LogLevel level)
    {
        switch(level)
        {
            case LogLevel::Info:    return "[INFO] ";
            case LogLevel::Warning: return "[WARN] ";
            case LogLevel::Error:   return "[ERROR] ";
        }
        return "";
    }

    /**
     * @brief Prints text to the platform-specific output.
     * @param text The text to print.
     */
    inline void platformPrint(const char* text)
    {
    #if defined(COREMRE_PLATFORM_MRE)
        vm_log_info("%s", text);
    #elif defined(ESP32)
        Serial.print(text);
    #else
        printf("%s", text);
        fflush(stdout); // flush to avoid buffering when running native
    #endif
    }
} // namespace pixelroot32::core::logging
