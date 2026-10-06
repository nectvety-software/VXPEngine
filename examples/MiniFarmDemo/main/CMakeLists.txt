set(TARGET_NAME "main")
set(SOURCES ../src/main.cpp)
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
target_include_directories(${TARGET_NAME} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../src)
target_link_libraries(${TARGET_NAME} mreapi coremre)
if(${CMAKE_SYSTEM_NAME} STREQUAL Generic)
    target_link_libraries(${TARGET_NAME} -lm)
endif()
