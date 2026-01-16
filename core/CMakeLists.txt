cmake_minimum_required(VERSION 3.20)
project(fleetguard_core VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(FG_BUILD_TESTS "Build unit tests" ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_compile_options(-Wall -Wextra -Wpedantic)

add_library(fgcore STATIC
  src/path.cpp
  src/vehicle.cpp
)
target_include_directories(fgcore PUBLIC include)

if(FG_BUILD_TESTS)
  enable_testing()
  find_package(GTest REQUIRED)
  add_executable(fgcore_tests
    tests/test_math.cpp
    tests/test_rng.cpp
    tests/test_path.cpp
    tests/test_vehicle.cpp
  )
  target_link_libraries(fgcore_tests PRIVATE fgcore GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(fgcore_tests)
endif()
