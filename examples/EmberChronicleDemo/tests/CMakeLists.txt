cmake_minimum_required(VERSION 3.16)
project(ember_preview LANGUAGES CXX)
set(CORE "${CMAKE_CURRENT_LIST_DIR}/../../../engine/coremre")
add_executable(ember_preview preview.cpp ../src/scene.cpp
    "${CORE}/src/graphics/VxpRender2D.cpp"
    "${CORE}/src/graphics/VxpSpriteFx.cpp"
    "${CORE}/src/graphics/VxpStory2D.cpp"
    "${CORE}/src/graphics/particles/VxpParticlePool.cpp")
target_include_directories(ember_preview PRIVATE ../src "${CORE}/include")
target_compile_features(ember_preview PRIVATE cxx_std_17)
target_compile_options(ember_preview PRIVATE -Wall -Wextra)
enable_testing()
add_test(NAME ember_preview_runtime COMMAND ember_preview)
