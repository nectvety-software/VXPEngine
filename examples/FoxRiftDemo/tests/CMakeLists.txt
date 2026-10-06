cmake_minimum_required(VERSION 3.16)
project(rift_preview LANGUAGES CXX)
set(CORE "${CMAKE_CURRENT_LIST_DIR}/../../../engine/coremre")
add_executable(rift_preview preview.cpp ../src/scene.cpp
    "${CORE}/src/graphics/VxpRender2D.cpp"
    "${CORE}/src/graphics/VxpSpriteFx.cpp"
    "${CORE}/src/graphics/VxpStory2D.cpp"
    "${CORE}/src/graphics/VxpPixelFont.cpp"
    "${CORE}/src/graphics/particles/VxpParticlePool.cpp")
target_include_directories(rift_preview PRIVATE ../src "${CORE}/include")
target_compile_features(rift_preview PRIVATE cxx_std_17)
target_compile_options(rift_preview PRIVATE -Wall -Wextra)
enable_testing()
add_test(NAME rift_preview_runtime COMMAND rift_preview)
