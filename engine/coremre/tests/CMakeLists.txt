cmake_minimum_required(VERSION 3.16)
project(vxpgdx_regressions LANGUAGES C CXX)

enable_testing()

set(CORE_DIR "${CMAKE_CURRENT_LIST_DIR}/..")
if(EXISTS "${CORE_DIR}/tools/vxpgdx_pack_tiled.py")
    set(VXPGDX_PACK_TILED "${CORE_DIR}/tools/vxpgdx_pack_tiled.py")
else()
    set(VXPGDX_PACK_TILED "${CORE_DIR}/../../tools/vxpgdx_pack_tiled.py")
endif()
if(EXISTS "${CORE_DIR}/tools/vxp_import_sprite_forge.py")
    set(VXPE_SPRITE_FORGE "${CORE_DIR}/tools/vxp_import_sprite_forge.py")
else()
    set(VXPE_SPRITE_FORGE "${CORE_DIR}/../../tools/vxp_import_sprite_forge.py")
endif()

add_library(vxpgdx_test_runtime STATIC
    "${CORE_DIR}/src/graphics/VxpColorGrade.cpp"
    "${CORE_DIR}/src/graphics/VxpRender2D.cpp"
    "${CORE_DIR}/src/graphics/VxpSpriteFx.cpp"
    "${CORE_DIR}/src/graphics/VxpSoft3D.cpp"
    "${CORE_DIR}/src/graphics/VxpActorSprite2D.cpp"
    "${CORE_DIR}/src/graphics/VxpStory2D.cpp"
    "${CORE_DIR}/src/graphics/VxpPixelFont.cpp"
    "${CORE_DIR}/src/graphics/VxpStage2D.cpp"
    "${CORE_DIR}/src/graphics/VxpScene25D.cpp"
    "${CORE_DIR}/src/graphics/VxpArtStyle.cpp"
    "${CORE_DIR}/src/graphics/VxpToon3D.cpp"
    "${CORE_DIR}/src/graphics/VxpRaycast3D.cpp"
    "${CORE_DIR}/src/graphics/VxpSuperScaler.cpp"
    "${CORE_DIR}/src/graphics/VxpDungeonFx.cpp"
    "${CORE_DIR}/src/action2d/VxpTilemap2D.cpp"
    "${CORE_DIR}/src/action2d/VxpCamera2D.cpp"
    "${CORE_DIR}/src/action2d/VxpBody2D.cpp"
    "${CORE_DIR}/src/action2d/VxpCombat2D.cpp"
    "${CORE_DIR}/src/action2d/VxpInputMap2D.cpp"
    "${CORE_DIR}/src/action2d/VxpHud2D.cpp"
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
add_executable(vxpe_raycast3d_regression vxpe_raycast3d_regression.cpp)
target_link_libraries(vxpe_raycast3d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_raycast3d_runtime COMMAND vxpe_raycast3d_regression)
add_executable(vxpe_superscaler_regression vxpe_superscaler_regression.cpp)
target_link_libraries(vxpe_superscaler_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_superscaler_runtime COMMAND vxpe_superscaler_regression)
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

add_executable(vxpe_scene25d_c_api vxpe_scene25d_c_api.c)
set_target_properties(vxpe_scene25d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_scene25d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_scene25d_c_api COMMAND vxpe_scene25d_c_api)

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

add_executable(vxpe_scatter_regression vxpe_scatter_regression.cpp)
target_include_directories(vxpe_scatter_regression PRIVATE "${CORE_DIR}/include")
add_test(NAME vxpe_scatter_runtime COMMAND vxpe_scatter_regression)

add_executable(vxpe_soft3d_regression vxpe_soft3d_regression.cpp)
target_link_libraries(vxpe_soft3d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_soft3d_runtime COMMAND vxpe_soft3d_regression)

# action2d core: tilemap + camera + platformer body, and the identity-scale blit
# fast path that makes a 16 px tile affordable on ARMv5TE.
add_executable(vxpe_action2d_regression vxpe_action2d_regression.cpp)
target_link_libraries(vxpe_action2d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_action2d_runtime COMMAND vxpe_action2d_regression)
add_executable(vxpe_action2d_c_api vxpe_action2d_c_api.c)
set_target_properties(vxpe_action2d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_action2d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_action2d_c_api COMMAND vxpe_action2d_c_api)

# Combat layer on top of the bodies: swing windows, i-frames, hit-stop, the
# per-swing hit mask and the projectile pool.
add_executable(vxpe_combat2d_regression vxpe_combat2d_regression.cpp)
target_link_libraries(vxpe_combat2d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_combat2d_runtime COMMAND vxpe_combat2d_regression)
add_executable(vxpe_combat2d_c_api vxpe_combat2d_c_api.c)
set_target_properties(vxpe_combat2d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_combat2d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_combat2d_c_api COMMAND vxpe_combat2d_c_api)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vxpe_combat2d_regression PRIVATE -Wall -Wextra)
endif()
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vxpe_action2d_regression PRIVATE -Wall -Wextra)
endif()

# Action-game furniture: named key bindings with edges and auto-repeat, then the
# zero-allocation HUD (plates, gauges with a damage ghost, icon rows, boss plate,
# fog-of-war minimap) drawn straight into the game's RGB565 buffer.
add_executable(vxpe_input2d_regression vxpe_input2d_regression.cpp)
target_link_libraries(vxpe_input2d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_input2d_runtime COMMAND vxpe_input2d_regression)
add_executable(vxpe_input2d_c_api vxpe_input2d_c_api.c)
set_target_properties(vxpe_input2d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_input2d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_input2d_c_api COMMAND vxpe_input2d_c_api)
add_executable(vxpe_hud2d_regression vxpe_hud2d_regression.cpp)
target_link_libraries(vxpe_hud2d_regression PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_hud2d_runtime COMMAND vxpe_hud2d_regression)
add_executable(vxpe_hud2d_c_api vxpe_hud2d_c_api.c)
set_target_properties(vxpe_hud2d_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_link_libraries(vxpe_hud2d_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_hud2d_c_api COMMAND vxpe_hud2d_c_api)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(vxpe_input2d_regression PRIVATE -Wall -Wextra)
    target_compile_options(vxpe_hud2d_regression PRIVATE -Wall -Wextra)
endif()

# Sprite-forge bridge. The vendored skills emit transparent PNG frames;
# tools/vxp_import_sprite_forge.py bakes them into the RGB565 + 1-bit-mask
# tables the core draws. The C file reads the committed fixtures back through
# the real blit and animation paths, so an importer change that shifts a mask
# bit, pads an atlas row or drops a per-frame duration fails here rather than
# on a handset. The Python file re-bakes those fixtures byte for byte and drives
# every gate, so the shipped art can never drift from the tool that made it.
add_executable(vxpe_sprite_forge_c_api vxpe_sprite_forge_c_api.c)
set_target_properties(vxpe_sprite_forge_c_api PROPERTIES C_STANDARD 99 LINKER_LANGUAGE CXX)
target_include_directories(vxpe_sprite_forge_c_api PRIVATE "${CMAKE_CURRENT_LIST_DIR}")
target_link_libraries(vxpe_sprite_forge_c_api PRIVATE vxpgdx_test_runtime)
add_test(NAME vxpe_sprite_forge_c_api COMMAND vxpe_sprite_forge_c_api)
add_test(
    NAME vxpe_sprite_forge_importer
    COMMAND
        "${Python3_EXECUTABLE}"
        "${CMAKE_CURRENT_LIST_DIR}/test_sprite_forge_importer.py"
        "${VXPE_SPRITE_FORGE}"
        "${CMAKE_CURRENT_LIST_DIR}"
)

# Opt-in profiler for 2.5D billboard and 3D triangle paths. It intentionally
# stays out of CTest so timing noise never affects the regression suite.
add_executable(vxpe_graphics_benchmark vxpe_graphics_benchmark.cpp)
target_link_libraries(vxpe_graphics_benchmark PRIVATE vxpgdx_test_runtime)
