# Dùng core coremre đã đóng gói: include(<gói>/cmake/UseCoremre.cmake)
# sau đó target_link_libraries(<app> PRIVATE coremre) và (tùy chọn) biên dịch
# ${COREMRE_SOURCES} vào app nếu app dùng phần C++ của core.
if(NOT TARGET coremre)
  get_filename_component(_COREMRE_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
  add_library(coremre INTERFACE)
  target_include_directories(coremre INTERFACE ${_COREMRE_ROOT}/include)
  target_compile_features(coremre INTERFACE cxx_std_17)
  target_compile_definitions(coremre INTERFACE PLATFORM_NATIVE)
  include("${CMAKE_CURRENT_LIST_DIR}/CoremreSources.cmake")
endif()
