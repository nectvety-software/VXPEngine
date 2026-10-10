cmake_minimum_required(VERSION 3.16)
project(super_scaler_host LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(super_scaler_regression
  gameplay.cpp
  ../src/scene.cpp
  ../../../engine/coremre/src/graphics/VxpRender2D.cpp
  ../../../engine/coremre/src/graphics/VxpSuperScaler.cpp
)
target_include_directories(super_scaler_regression PRIVATE ../src ../../../engine/coremre/include)
enable_testing()
add_test(NAME super_scaler_gameplay COMMAND super_scaler_regression)
