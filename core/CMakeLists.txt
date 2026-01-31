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

find_package(nlohmann_json 3 REQUIRED)

add_library(fgcore STATIC
  src/path.cpp
  src/vehicle.cpp
  src/scenario.cpp
  src/controller.cpp
  src/build_config.cpp
  src/actors.cpp
  src/planner.cpp
  src/sim.cpp
  src/io.cpp
  src/safety.cpp
  src/events.cpp
  src/perception.cpp
)
target_include_directories(fgcore PUBLIC include)
target_link_libraries(fgcore PUBLIC nlohmann_json::nlohmann_json)

add_executable(fgsim src/main.cpp)
target_link_libraries(fgsim PRIVATE fgcore)
install(TARGETS fgsim RUNTIME DESTINATION bin)

if(FG_BUILD_TESTS)
  enable_testing()
  find_package(GTest REQUIRED)
  add_executable(fgcore_tests
    tests/test_math.cpp
    tests/test_rng.cpp
    tests/test_path.cpp
    tests/test_vehicle.cpp
    tests/test_scenario.cpp
    tests/test_controller.cpp
    tests/test_build_config.cpp
    tests/test_actors.cpp
    tests/test_sim.cpp
    tests/test_safety.cpp
    tests/test_events.cpp
    tests/test_perception.cpp
  )
  target_link_libraries(fgcore_tests PRIVATE fgcore GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(fgcore_tests)
endif()
