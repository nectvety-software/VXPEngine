set(TARGET_NAME "main")
set(SOURCES
    "${CMAKE_SOURCE_DIR}/src/main.cpp"
    "${CMAKE_SOURCE_DIR}/src/scene.cpp"
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
    COMMAND "${VXPE_PYTHON}" "${CMAKE_SOURCE_DIR}/tools/generate_roster.py"
    DEPENDS "${CMAKE_SOURCE_DIR}/assets/gameplay/heroes.json"
            "${CMAKE_SOURCE_DIR}/tools/generate_roster.py"
    VERBATIM)
add_custom_target(vaelora_roster DEPENDS "${CMAKE_SOURCE_DIR}/src/hero_roster_generated.h")
add_dependencies(${TARGET_NAME} vaelora_roster)
