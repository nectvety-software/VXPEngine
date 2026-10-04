cmake_minimum_required(VERSION 3.10)
project(coremre)

# VXPEngine core: coremre — core duy nhất cho MRE VXP (đã gộp, không Arduino).
# Mặc định là INTERFACE library (header + src trong repo) để IDE build trực tiếp.
add_library(coremre INTERFACE)
target_include_directories(coremre INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_features(coremre INTERFACE cxx_std_17)
if(${CMAKE_SYSTEM_NAME} STREQUAL Generic)
    target_compile_options(coremre INTERFACE -std=c++17 -fno-exceptions -fno-rtti)
endif()

# ---------------------------------------------------------------------------
# COREMRE_STATIC_LIB=ON: biên phần độc lập nền tảng của core thành static
# library (tools/pack_core.py dùng để đóng gói + ký cho nhiều app dùng chung).
# Phần phụ thuộc nền tảng (SDL2/Arduino/ESP32/mock) không nằm trong thư tĩnh.
# ---------------------------------------------------------------------------
option(COREMRE_STATIC_LIB "Build coremre static library for the signed shared package" OFF)
if(COREMRE_STATIC_LIB)
    file(GLOB_RECURSE _coremre_src
        ${CMAKE_CURRENT_SOURCE_DIR}/src/core/*.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/graphics/*.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/gameplay/*.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/physics/*.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/input/*.cpp
    )
    list(FILTER _coremre_src EXCLUDE REGEX ".*(SDL2|ESP32|Arduino|Mock|DisplayConfig|Renderer|TileAnimation|TransitionEffect|InputManager|XPT2046|GT911).*")
    list(APPEND _coremre_src
        ${CMAKE_CURRENT_SOURCE_DIR}/src/platforms/mock/MockArduino.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/platforms/mock/MockTiming.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/platforms/mock/MockSPI.cpp
    )
    add_library(coremre_static STATIC ${_coremre_src})
    set_target_properties(coremre_static PROPERTIES OUTPUT_NAME coremre)
    target_include_directories(coremre_static PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
    target_compile_features(coremre_static PUBLIC cxx_std_17)
    target_compile_definitions(coremre_static PUBLIC PLATFORM_NATIVE)
    if(${CMAKE_SYSTEM_NAME} STREQUAL Generic)
        target_compile_options(coremre_static PUBLIC -std=c++17 -fno-exceptions -fno-rtti)
    endif()
endif()
