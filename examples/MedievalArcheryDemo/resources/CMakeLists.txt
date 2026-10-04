set(TARGET_NAME "resources")
set(PACK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/pack")
set(GAME_RESOURCES battlefield.raw player_archer.raw enemy_archer.raw arrow.raw logo.raw bow.wav hit.wav victory.wav)
set(RESOURCE_DEPS "")
foreach(name ${GAME_RESOURCES})
    list(APPEND RESOURCE_DEPS "${CMAKE_CURRENT_SOURCE_DIR}/gen/${name}")
endforeach()
add_custom_command(
    OUTPUT null.cpp
    COMMAND ${CMAKE_COMMAND} -E make_directory "${PACK_DIR}"
    COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_CURRENT_SOURCE_DIR}/gen" "${PACK_DIR}"
    COMMAND ${CMAKE_COMMAND} -E touch null.cpp
    DEPENDS ${RESOURCE_DEPS}
)
add_library(${TARGET_NAME} STATIC "null.cpp")
set_target_properties(${TARGET_NAME} PROPERTIES SUFFIX ".res" PREFIX "")
add_custom_command(TARGET ${TARGET_NAME} POST_BUILD
    WORKING_DIRECTORY "${PACK_DIR}"
    COMMAND "${VXPE_PYTHON}" "${VXPE_SDK_TOOLS}/vxp_resource.py" -o "$<TARGET_FILE:${TARGET_NAME}>" -f ${GAME_RESOURCES} --empty-logo
)
