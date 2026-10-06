cmake_minimum_required(VERSION 3.16)
project(vxpgdx_regressions LANGUAGES C CXX)

enable_testing()

set(CORE_DIR "${CMAKE_CURRENT_LIST_DIR}/..")
if(EXISTS "${CORE_DIR}/tools/vxpgdx_pack_tiled.py")
    set(VXPGDX_PACK_TILED "${CORE_DIR}/tools/vxpgdx_pack_tiled.py")
else()
    set(VXPGDX_PACK_TILED "${CORE_DIR}/../../tools/vxpgdx_pack_tiled.py")
endif()

add_library(vxpgdx_test_runtime STATIC
    "${CORE_DIR}/src/graphics/VxpColorGrade.cpp"
    "${CORE_DIR}/src/graphics/VxpRender2D.cpp"
    "${CORE_DIR}/src/graphics/VxpSpriteFx.cpp"
    "${CORE_DIR}/src/graphics/VxpActorSprite2D.cpp"
    "${CORE_DIR}/src/graphics/VxpStory2D.cpp"
    "${CORE_DIR}/src/graphics/VxpPixelFont.cpp"
    "${CORE_DIR}/src/graphics/VxpStage2D.cpp"
    "${CORE_DIR}/src/graphics/VxpScene25D.cpp"
    "${CORE_DIR}/src/graphics/VxpArtStyle.cpp"
    "${CORE_DIR}/src/graphics/VxpToon3D.cpp"
    "${CORE_DIR}/src/graphics/VxpDungeonFx.cpp"
)
target_include_directories(vxpgdx_test_runtime PUBLIC "${CORE_DIR}/include")
target_compile_features(vxpgdx_test_runtime PUBLIC cxx_std_17)
add_executable(vxpe_story2d_regression vxpe_story2d_regression.cpp)
target_link_libraries(vxpe_story2d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_story2d_runtime COMMAND vxpe_story2d_regression)
add_executable(vxpe_story2d_c_api vxpe_story2d_c_api.c)
set_target_properties(vxpe_story2d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_story2d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_story2d_c_api COMMAND vxpe_story2d_c_api)
add_executable(vxpe_sprite_fast_regression vxpe_sprite_fast_regression.cpp)
target_link_libraries(vxpe_sprite_fast_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_sprite_fast_runtime COMMAND vxpe_sprite_fast_regression)
add_executable(vxpe_toon3d_regression vxpe_toon3d_regression.cpp)
target_link_libraries(vxpe_toon3d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_toon3d_runtime COMMAND vxpe_toon3d_regression)
add_executable(vxpe_toon3d_c_api vxpe_toon3d_c_api.c)
set_target_properties(vxpe_toon3d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_toon3d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_toon3d_c_api COMMAND vxpe_toon3d_c_api)
add_executable(vxpe_actor_sprite_regression vxpe_actor_sprite_regression.cpp)
target_link_libraries(vxpe_actor_sprite_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_actor_sprite_runtime COMMAND vxpe_actor_sprite_regression)
add_executable(vxpe_color_grade_regression vxpe_color_grade_regression.cpp)
target_link_libraries(vxpe_color_grade_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_color_grade_runtime COMMAND vxpe_color_grade_regression)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vxpgdx_test_runtime PRIVATE -Wall -Wextra)
endif()

add_executable(vxpgdx_vxtm3_regression
    vxpgdx_vxtm3_regression.cpp
)
target_link_libraries(vxpgdx_vxtm3_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpgdx_vxtm3_runtime COMMAND vxpgdx_vxtm3_regression)

add_executable(vxpgdx_ui_arm_regression
    vxpgdx_ui_arm_regression.cpp
)
target_link_libraries(vxpgdx_ui_arm_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpgdx_ui_runtime COMMAND vxpgdx_ui_arm_regression)

add_executable(vxpe_scene25d_regression
    vxpe_scene25d_regression.cpp
)
target_link_libraries(vxpe_scene25d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_scene25d_runtime COMMAND vxpe_scene25d_regression)

add_executable(vxpe_stage2d_regression
    vxpe_stage2d_regression.cpp
)
target_link_libraries(vxpe_stage2d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_stage2d_runtime COMMAND vxpe_stage2d_regression)

add_executable(vxpe_artstyle_regression
    vxpe_artstyle_regression.cpp
)
target_link_libraries(vxpe_artstyle_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_artstyle_runtime COMMAND vxpe_artstyle_regression)

add_executable(vxpgdx_strategy_rpg_regression
    vxpgdx_strategy_rpg_regression.cpp
)
target_link_libraries(vxpgdx_strategy_rpg_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpgdx_strategy_rpg_runtime COMMAND vxpgdx_strategy_rpg_regression)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vxpgdx_vxtm3_regression PRIVATE -Wall -Wextra)
    target_compile_options(vxpgdx_ui_arm_regression PRIVATE -Wall -Wextra)
    target_compile_options(vxpe_scene25d_regression PRIVATE -Wall -Wextra)
    target_compile_options(vxpe_stage2d_regression PRIVATE -Wall -Wextra)
    target_compile_options(vxpe_artstyle_regression PRIVATE -Wall -Wextra)
    target_compile_options(vxpgdx_strategy_rpg_regression PRIVATE -Wall -Wextra)
endif()

find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_test(
    NAME vxpgdx_vxtm3_packer
    COMMAND
        "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_LIST_DIR}/test_vxtm3_packer.py"
        "${VXPGDX_PACK_TILED}"
)

add_executable(vxpe_dungeonfx_regression vxpe_dungeonfx_regression.cpp)
target_link_libraries(vxpe_dungeonfx_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_dungeonfx_runtime COMMAND vxpe_dungeonfx_regression)

add_executable(vxpe_pixel_font_regression vxpe_pixel_font_regression.cpp)
target_link_libraries(vxpe_pixel_font_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_pixel_font_runtime COMMAND vxpe_pixel_font_regression)
