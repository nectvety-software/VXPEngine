set(TARGET_NAME "resources")

# Everything vm_load_resource() fetches by bare filename gets flattened
# into resources/pack/: 73 sprite .raw files, the arena map, 4 sfx mp3s.
file(GLOB SPRITE_RAW "${CMAKE_CURRENT_SOURCE_DIR}/gen/*.raw")

set(SFX_SWING  "${CMAKE_CURRENT_SOURCE_DIR}/../assets/audio/swing-whoosh-1.mp3")
set(SFX_HIT    "${CMAKE_CURRENT_SOURCE_DIR}/../assets/audio/axe-hit-flesh.mp3")
set(SFX_PICKUP "${CMAKE_CURRENT_SOURCE_DIR}/../assets/audio/health-pickup-6860.mp3")
set(SFX_BOOM   "${CMAKE_CURRENT_SOURCE_DIR}/../assets/audio/explosion-fx.mp3")
set(ARENA_MAP  "${CMAKE_CURRENT_SOURCE_DIR}/../maps/arena1.txt")

set(PACK_DIR   "${CMAKE_CURRENT_SOURCE_DIR}/pack")
set(RESOURCES_FILES "") # packed under their plain base names
foreach(f ${SPRITE_RAW})
    get_filename_component(n "${f}" NAME)
    list(APPEND RESOURCES_FILES "${n}")
endforeach()
list(APPEND RESOURCES_FILES
    "arena1.txt"
    "sfx_shoot.mp3"
    "sfx_hit.mp3"
    "sfx_pickup.mp3"
    "sfx_explode.mp3"
)

add_custom_command( # stage flat copies, then trigger repack
   OUTPUT null.cpp
   COMMAND ${CMAKE_COMMAND} -E make_directory "${PACK_DIR}"
   COMMAND ${CMAKE_COMMAND} -E copy_directory "${CMAKE_CURRENT_SOURCE_DIR}/gen" "${PACK_DIR}"
   COMMAND ${CMAKE_COMMAND} -E remove -f "${PACK_DIR}/sprites.h" "${PACK_DIR}/sprites.txt"
   COMMAND ${CMAKE_COMMAND} -E copy "${ARENA_MAP}"  "${PACK_DIR}/arena1.txt"
   COMMAND ${CMAKE_COMMAND} -E copy "${SFX_SWING}"  "${PACK_DIR}/sfx_shoot.mp3"
   COMMAND ${CMAKE_COMMAND} -E copy "${SFX_HIT}"    "${PACK_DIR}/sfx_hit.mp3"
   COMMAND ${CMAKE_COMMAND} -E copy "${SFX_PICKUP}" "${PACK_DIR}/sfx_pickup.mp3"
   COMMAND ${CMAKE_COMMAND} -E copy "${SFX_BOOM}"   "${PACK_DIR}/sfx_explode.mp3"
   COMMAND ${CMAKE_COMMAND} -E touch null.cpp
   DEPENDS ${SPRITE_RAW} "${ARENA_MAP}" "${SFX_SWING}" "${SFX_HIT}" "${SFX_PICKUP}" "${SFX_BOOM}"
)

add_library(${TARGET_NAME} STATIC "null.cpp")

set_target_properties(${TARGET_NAME} PROPERTIES SUFFIX ".res")
set_target_properties(${TARGET_NAME} PROPERTIES PREFIX "")

add_custom_command(TARGET ${TARGET_NAME} POST_BUILD
   WORKING_DIRECTORY "${PACK_DIR}"
   COMMAND "${TinyMRESDK}/bin/PackRes"
               -o "$<TARGET_FILE:${TARGET_NAME}>"
               -f ${RESOURCES_FILES}
               --empty-logo
)
