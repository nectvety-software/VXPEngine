set(TARGET_NAME "resources")

# Dự án trống: chỉ đóng gói sprite placeholder để .vxp luôn có resources.res hợp lệ.
# Thêm file vào gen/ (hoặc import từ Thư viện VXPEngine) rồi build lại để đóng gói.
set(PROJECT_RESOURCES_DIR "${CMAKE_SOURCE_DIR}/resources")
file(GLOB SPRITE_RAW "${PROJECT_RESOURCES_DIR}/gen/*.raw")

set(PACK_DIR   "${PROJECT_RESOURCES_DIR}/pack")
set(RESOURCES_FILES "")
foreach(f ${SPRITE_RAW})
    get_filename_component(n "${f}" NAME)
    list(APPEND RESOURCES_FILES "${n}")
endforeach()

add_custom_command(
   OUTPUT null.cpp
   COMMAND ${CMAKE_COMMAND} -E make_directory "${PACK_DIR}"
   COMMAND ${CMAKE_COMMAND} -E copy_directory "${PROJECT_RESOURCES_DIR}/gen" "${PACK_DIR}"
   COMMAND ${CMAKE_COMMAND} -E touch null.cpp
   DEPENDS ${SPRITE_RAW}
)

add_library(${TARGET_NAME} STATIC "null.cpp")

set_target_properties(${TARGET_NAME} PROPERTIES SUFFIX ".res")
set_target_properties(${TARGET_NAME} PROPERTIES PREFIX "")

add_custom_command(TARGET ${TARGET_NAME} POST_BUILD
   WORKING_DIRECTORY "${PACK_DIR}"
   COMMAND "${VXPE_PYTHON}" "${VXPE_SDK_TOOLS}/vxp_resource.py"
               -o "$<TARGET_FILE:${TARGET_NAME}>"
               -f ${RESOURCES_FILES}
               --empty-logo
)
