cmake_minimum_required(VERSION 3.16)
project(lost_latency_host LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(lost_latency_regression
  gameplay.cpp
  ../src/scene.cpp
  ../../../engine/coremre/src/graphics/VxpRender2D.cpp
  ../../../engine/coremre/src/graphics/VxpSpriteFx.cpp
  ../../../engine/coremre/src/graphics/VxpRaycast3D.cpp
)
target_include_directories(lost_latency_regression PRIVATE ../src ../../../engine/coremre/include)
enable_testing()
add_test(NAME lost_latency_gameplay COMMAND lost_latency_regression)
