cmake_minimum_required(VERSION 3.28)
project(maya_py LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# maya needs -march=native OFF for a portable extension; it also force-enables
# IPO which we don't want fighting pybind11. Keep the build lean.
set(MAYA_NATIVE_TUNING OFF CACHE BOOL "" FORCE)
set(MAYA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(MAYA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF CACHE BOOL "" FORCE)

include(FetchContent)

# ── maya ──────────────────────────────────────────────────────────────────
# Prefer a sibling checkout if present (offline / hacking), else clone.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../maya-src/CMakeLists.txt")
    message(STATUS "maya_py: using local maya at ../maya-src")
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../maya-src" maya_build)
else()
    FetchContent_Declare(maya
        GIT_REPOSITORY https://github.com/1ay1/maya.git
        GIT_TAG        master)
    FetchContent_MakeAvailable(maya)
endif()

# ── pybind11 ──────────────────────────────────────────────────────────────
find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
    FetchContent_Declare(pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG        v2.13.6)
    FetchContent_MakeAvailable(pybind11)
endif()

# When pulled in via add_subdirectory / FetchContent the target is plain
# `maya` (the maya:: namespace only exists on the installed export).
if(NOT TARGET maya::maya)
    add_library(maya::maya ALIAS maya)
endif()

# maya builds a static lib; linking it into a shared Python module needs PIC.
set_property(TARGET maya PROPERTY POSITION_INDEPENDENT_CODE ON)

# ── the extension ─────────────────────────────────────────────────────────
pybind11_add_module(_maya src/_maya.cpp)
target_link_libraries(_maya PRIVATE maya::maya)

# Install into the package dir (scikit-build-core picks this up).
install(TARGETS _maya LIBRARY DESTINATION maya_py)
