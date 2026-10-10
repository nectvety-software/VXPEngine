cmake_minimum_required(VERSION 3.16)
project(pocket_pitch_host LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_executable(pocket_pitch_regression
  gameplay.cpp
  ../src/scene.cpp
  ../../../engine/coremre/src/graphics/VxpRender2D.cpp
)
target_include_directories(pocket_pitch_regression PRIVATE ../src ../../../engine/coremre/include)
enable_testing()
add_test(NAME pocket_pitch_gameplay COMMAND pocket_pitch_regression)
