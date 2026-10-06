cmake_minimum_required (VERSION 3.10)

project("gnarly_dungeon")

# ---------------------------------------------------------------------------
# Dự án TRỐNG do VXPEngine sinh ra (template_blank):
#   - Không tài nguyên, không SFX; thêm từ Thư viện của VXPEngine khi cần.
#   - App ID riêng do engine cấp khi tạo dự án (set(APPID ...) được patch).
#   - Không chứa khóa ký: bản signed do VXPEngine build bằng khóa của engine.
# ---------------------------------------------------------------------------
set(APP_NAME "gnarly_dungeon")
set(DEVELOPER_NAME "VXPstore")
set(RAM "2048")
set(IMSI "91234567890" CACHE STRING "Imsi of first SIM-card (Nokia needs a leading 9)")
set(API "File Audio ProMng")
set(APPID "5814721" CACHE STRING "App id")
set(CERTID "1" CACHE STRING "Cert id")
set(CERT "none" CACHE STRING "Path to cert")
option(BACKGROUND "App can work background" OFF)

set(MRE_SDK "$ENV{MRE_SDK}" CACHE STRING "MRE SDK dir")
set(VXPE_PYTHON "$ENV{VXPE_PYTHON}" CACHE FILEPATH "Python used by VXPEngine SDK tools")
set(VXPE_SDK_TOOLS "$ENV{VXPE_SDK_TOOLS}" CACHE PATH "VXPEngine SDK tools directory")
if(NOT VXPE_PYTHON)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)
    set(VXPE_PYTHON "${Python3_EXECUTABLE}")
endif()
if(NOT EXISTS "${VXPE_SDK_TOOLS}/vxp_pack.py")
    message(FATAL_ERROR "Thieu VXPEngine SDK tools: truyen -DVXPE_SDK_TOOLS=<engine/coremre/tools>")
endif()

if(BACKGROUND)
    add_definitions(-DSUPPORT_BG)
endif()

include(.vxpe/cmake/MreUtils.cmake)

# --- VXPEngine core: coremre (core duy nhất, gộp từ vxpstore/corevxp) ---
# Core dùng chung: ưu tiên gói coremre đã ký do VXPEngine truyền qua
# -DCOREMRE_PACKAGE_DIR; project cũ còn engine/ trong cây thì dùng tại chỗ.
if(DEFINED COREMRE_PACKAGE_DIR AND EXISTS "${COREMRE_PACKAGE_DIR}/cmake/UseCoremre.cmake")
    include("${COREMRE_PACKAGE_DIR}/cmake/UseCoremre.cmake")
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/engine/coremre/CMakeLists.txt")
    add_subdirectory(engine/coremre)
else()
    message(FATAL_ERROR "Thieu core coremre: chay qua VXPEngine hoac truyen -DCOREMRE_PACKAGE_DIR=<goi core>")
endif()

add_subdirectory(.vxpe/platform/resources resources)
add_subdirectory(.vxpe/platform/mreapi mreapi)
add_subdirectory(.vxpe/platform/run run)
add_subdirectory(.vxpe/platform/main main)
