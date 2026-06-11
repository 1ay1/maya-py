cmake_minimum_required(VERSION 3.28)
project(maya_py LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Compiler preflight ───────────────────────────────────────────────
# maya compiles at C++26 but the features it actually uses (views::enumerate,
# std::expected, std::format, deducing-this) all landed in GCC 14 / Clang 18.
# If we got here we're COMPILING FROM SOURCE — no prebuilt wheel matched this
# platform. On an old toolchain the compile fails deep inside maya with
# inscrutable template errors, so fail FAST with an actionable message.
#
# The intended install path on old machines is a PREBUILT WHEEL (no compiler
# needed at all). If you're seeing this, a wheel for your Python/platform
# wasn't available and pip fell back to building the source distribution.
set(_maya_min_gcc 14)
set(_maya_ok TRUE)
if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS ${_maya_min_gcc})
        set(_maya_ok FALSE)
    endif()
elseif(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS 18)
        set(_maya_ok FALSE)
    endif()
endif()

if(NOT _maya_ok)
    message(FATAL_ERROR
        "\n"
        "==============================================================\n"
        " maya-py: your C++ compiler is too old to BUILD from source.\n"
        "\n"
        "   found:    ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\n"
        "   required: GCC >= ${_maya_min_gcc} (or Clang >= 18)\n"
        "\n"
        " You should NOT need to compile maya-py at all — it ships\n"
        " PRECOMPILED standalone wheels that install with no compiler.\n"
        " pip only reached this point because no wheel matched your\n"
        " Python version / platform.\n"
        "\n"
        " Fixes, easiest first:\n"
        "   1. Upgrade pip so it can find more wheels:\n"
        "        python -m pip install --upgrade pip\n"
        "   2. Install the prebuilt wheel directly from a GitHub release:\n"
        "        pip install <url-to-the-.whl-for-your-platform>\n"
        "   3. If you truly must build from source, install a modern GCC:\n"
        "        # Ubuntu:  sudo apt install g++-14\n"
        "        # then:    pip install . -C cmake.define.CMAKE_CXX_COMPILER=g++-14\n"
        "==============================================================\n")
endif()

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

# ── Self-contained runtime (works on machines with an OLD toolchain) ───────
#
# maya is C++26, so the .so is built with a modern GCC and pulls in very new
# libstdc++ symbols (GLIBCXX_3.4.3x). An old target machine's system
# libstdc++ won't have them, so by default the wheel would fail to LOAD even
# though no compiler runs at install time.
#
# Fix: statically link libstdc++ and libgcc INTO the extension. The .so then
# carries its own C++ runtime and depends only on libc / libm / libdl —
# baseline libraries present on essentially every Linux. The wheel becomes
# truly standalone: download, unzip, import; the old compiler is irrelevant.
#
# Opt out with -DMAYA_PY_STATIC_CXX=OFF (e.g. when building a manylinux wheel
# where auditwheel + the manylinux libstdc++ already provide portability).
option(MAYA_PY_STATIC_CXX "Statically link libstdc++/libgcc into the extension" ON)

if(MAYA_PY_STATIC_CXX AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    target_link_options(_maya PRIVATE
        -static-libstdc++
        -static-libgcc
        # Hide the statically-linked C++ symbols so they can't clash with a
        # different libstdc++ already loaded in the host process.
        -Wl,--exclude-libs,ALL
    )
endif()

# Install into the package dir (scikit-build-core picks this up).
install(TARGETS _maya LIBRARY DESTINATION maya_py)
