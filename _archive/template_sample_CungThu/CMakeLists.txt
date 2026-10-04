cmake_minimum_required (VERSION 3.10)

project ("CungThuBongDen")

# ---------------------------------------------------------------------------
# App identity / packing parameters
#   APP_NAME  : output file name (CungThuBongDen.vxp)
#   APPID     : -1 personal (IMSI-locked), 0 = development.
#               VXPEngine cấp một App ID riêng cho mỗi project khi tạo dự án.
#   CERTID    : 1 = personal/dev cert, 100 = trusted retail cert
#   CERT      : path to PEM private key used by PackApp when signing
#
# Bảo mật: khóa ký retail (certid 100) là tài sản của VXPEngine, KHÔNG nằm
# trong project. Project luôn ở mặc định chưa ký (CERTID=1, CERT=none); khi
# build bản signed, VXPEngine truyền -DAPPID/-DCERTID/-DCERT từ khóa của engine
# (hoặc qua VXP_APPID / VXP_CERTID / VXP_CERT cho build_arm_signed.sh).
# Không bao giờ copy khóa ký vào thư mục dự án.
# ---------------------------------------------------------------------------
set(APP_NAME "CungThuBongDen")
set(DEVELOPER_NAME "VXPstore")
set(RAM "800")
set(IMSI "91234567890" CACHE STRING "Imsi of first SIM-card (Nokia needs a leading 9)")
set(API "File Audio ProMng")
set(APPID "0" CACHE STRING "App id")
set(CERTID "1" CACHE STRING "Cert id")
set(CERT "none" CACHE STRING "Path to cert")
option(BACKGROUND "App can work background" OFF)

set(MRE_SDK "$ENV{MRE_SDK}" CACHE STRING "MRE SDK dir")
set(TinyMRESDK "$ENV{TinyMRESDK}" CACHE STRING "TinyMRESDK dir")

if(BACKGROUND)
    add_definitions(-DSUPPORT_BG)
endif()

include(cmake/MreUtils.cmake)

# --- VXPEngine core: coremre — riêng cho MRE VXP + Arduino, dựa trên PixelRoot32-Game-Engine, đã loại bỏ PixelRoot32 gốc ---
# Core dùng chung: ưu tiên gói coremre đã ký do VXPEngine truyền qua
# -DCOREMRE_PACKAGE_DIR; project cũ còn engine/ trong cây thì dùng tại chỗ.
if(DEFINED COREMRE_PACKAGE_DIR AND EXISTS "${COREMRE_PACKAGE_DIR}/cmake/UseCoremre.cmake")
    include("${COREMRE_PACKAGE_DIR}/cmake/UseCoremre.cmake")
elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/engine/coremre/CMakeLists.txt")
    add_subdirectory(engine/coremre)
else()
    message(FATAL_ERROR "Thieu core coremre: chay qua VXPEngine hoac truyen -DCOREMRE_PACKAGE_DIR=<goi core>")
endif()

add_subdirectory(resources)
add_subdirectory(mreapi)
add_subdirectory(run)

add_subdirectory(main)
