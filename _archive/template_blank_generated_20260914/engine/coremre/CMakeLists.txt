cmake_minimum_required(VERSION 3.10)
project(coremre)

# VXPEngine core: coremre — riêng cho MRE VXP (bản này đã loại bỏ Arduino/ESP32), dựa trên PixelRoot32-Game-Engine, đã loại bỏ PixelRoot32 gốc.
# Hai core cũ (vxpstore và corevxp) từng là bản sao của nhau nên đã được gộp thành một.
add_library(coremre INTERFACE)
target_include_directories(coremre INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(coremre INTERFACE cxx_std_17)
target_compile_definitions(coremre INTERFACE COREMRE_PLATFORM_MRE=1)
