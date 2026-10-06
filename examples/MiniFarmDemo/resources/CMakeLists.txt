set(TARGET_NAME "resources")
file(GLOB GENERATED_FILES "${CMAKE_CURRENT_SOURCE_DIR}/gen/*.vxa8" "${CMAKE_CURRENT_SOURCE_DIR}/gen/*.vxat" "${CMAKE_CURRENT_SOURCE_DIR}/gen/*.vxtm")
set(PACK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/pack")
set(RESOURCES_FILES "")
foreach(f ${GENERATED_FILES})
    get_filename_component(n "${f}" NAME)
    list(APPEND RESOURCES_FILES "${n}")
endforeach()
add_custom_command(
   OUTPUT null.cpp
   COMMAND ${CMAKE_COMMAND} -E make_directory "${PACK_DIR}"
   COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_CURRENT_SOURCE_DIR}/gen" "${PACK_DIR}"
   COMMAND ${CMAKE_COMMAND} -E touch null.cpp
   DEPENDS ${GENERATED_FILES}
)
add_library(${TARGET_NAME} STATIC "null.cpp")
set_target_properties(${TARGET_NAME} PROPERTIES SUFFIX ".res" PREFIX "")
add_custom_command(TARGET ${TARGET_NAME} POST_BUILD
   WORKING_DIRECTORY "${PACK_DIR}"
   COMMAND "${VXPE_PYTHON}" "${VXPE_SDK_TOOLS}/vxp_resource.py"
               -o "$<TARGET_FILE:${TARGET_NAME}>"
               -f ${RESOURCES_FILES}
               --empty-logo
)
