set(TARGET_NAME "main")
set(SOURCES
    "${CMAKE_SOURCE_DIR}/src/main.cpp"
    "${CMAKE_SOURCE_DIR}/src/scene.cpp"
    "${CMAKE_SOURCE_DIR}/src/skill_effects.cpp"
    "${CMAKE_SOURCE_DIR}/src/lane_warfare.cpp"
)
add_exec_vxp(${TARGET_NAME}
    SRCS ${SOURCES}
    RESOURCES resources
    APP_NAME "${APP_NAME}"
    APPID "${APPID}"
    CERT "${CERT}"
    CERTID "${CERTID}"
    IMSI "${IMSI}"
    BACKGROUND ${BACKGROUND}
    API "${API}"
    RAM "${RAM}"
)
target_include_directories(${TARGET_NAME} PRIVATE "${CMAKE_SOURCE_DIR}/src")
target_include_directories(${TARGET_NAME} PRIVATE "${CMAKE_SOURCE_DIR}/engine/coremre/include")
target_link_libraries(${TARGET_NAME} mreapi coremre)
if(${CMAKE_SYSTEM_NAME} STREQUAL Generic)
    target_link_libraries(${TARGET_NAME} -lm)
endif()

# Refresh editable hero definitions for both IDE and script builds.
add_custom_command(OUTPUT "${CMAKE_SOURCE_DIR}/src/hero_roster_generated.h"
    COMMAND "${CMAKE_COMMAND}" -DDATA=heroes -P "${CMAKE_SOURCE_DIR}/tools/generate_gameplay.cmake"
    DEPENDS "${CMAKE_SOURCE_DIR}/assets/gameplay/heroes.json"
            "${CMAKE_SOURCE_DIR}/tools/generate_gameplay.cmake"
    VERBATIM)
add_custom_target(vaelora_roster DEPENDS "${CMAKE_SOURCE_DIR}/src/hero_roster_generated.h")
add_dependencies(${TARGET_NAME} vaelora_roster)

# Editable world placement drives runtime collision and environment rendering.
add_custom_command(OUTPUT "${CMAKE_SOURCE_DIR}/src/world_generated.h"
    COMMAND "${CMAKE_COMMAND}" -DDATA=world -P "${CMAKE_SOURCE_DIR}/tools/generate_gameplay.cmake"
    DEPENDS "${CMAKE_SOURCE_DIR}/assets/gameplay/world.json" "${CMAKE_SOURCE_DIR}/tools/generate_gameplay.cmake"
    VERBATIM)
add_custom_target(vaelora_world DEPENDS "${CMAKE_SOURCE_DIR}/src/world_generated.h")
add_dependencies(${TARGET_NAME} vaelora_world)

