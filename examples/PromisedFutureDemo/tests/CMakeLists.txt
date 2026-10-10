cmake_minimum_required(VERSION 3.16)
project(promised_future_host LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(promised_future_regression
  gameplay.cpp
  ../src/scene.cpp
  ../../../engine/coremre/src/graphics/VxpRender2D.cpp
  ../../../engine/coremre/src/graphics/VxpSpriteFx.cpp
  ../../../engine/coremre/src/graphics/VxpToon3D.cpp
)
target_include_directories(promised_future_regression PRIVATE ../src ../../../engine/coremre/include)
enable_testing()
add_test(NAME promised_future_gameplay COMMAND promised_future_regression)
