cmake_minimum_required(VERSION 3.28)

# macOS deployment floor — must be set BEFORE project() so the compiler probe
# and every target inherit it. 11.0 is the oldest arm64-capable release and
# is fine for x86_64 too. cibuildwheel / the caller can override via the
# MACOSX_DEPLOYMENT_TARGET env var or -DCMAKE_OSX_DEPLOYMENT_TARGET.
if(APPLE AND NOT DEFINED CMAKE_OSX_DEPLOYMENT_TARGET)
    if(DEFINED ENV{MACOSX_DEPLOYMENT_TARGET})
        set(CMAKE_OSX_DEPLOYMENT_TARGET "$ENV{MACOSX_DEPLOYMENT_TARGET}"
            CACHE STRING "Minimum macOS version")
    else()
        set(CMAKE_OSX_DEPLOYMENT_TARGET "11.0" CACHE STRING "Minimum macOS version")
    endif()
endif()

# ── macOS: prefer real GNU GCC over AppleClang ───────────────────────
# maya is C++26. AppleClang lags upstream LLVM and (depending on the Xcode
# version) misses C++26 / late-C++23 library bits maya leans on, so on macOS
# we build with Homebrew GCC instead. This MUST run before project() so the
# compiler-id probe picks GCC.
#
# We only auto-pick when the user hasn't already chosen a compiler — an
# explicit -DCMAKE_CXX_COMPILER=..., a CXX env var, or a cached entry always
# wins (escape hatch for someone who really wants Clang).
if(APPLE
   AND NOT DEFINED CMAKE_CXX_COMPILER
   AND NOT DEFINED ENV{CXX}
   AND NOT DEFINED CACHE{CMAKE_CXX_COMPILER})
    # Newest first. Homebrew installs versioned binaries (g++-15, g++-14, ...);
    # plain `g++` on macOS is an AppleClang shim, so we do NOT trust it here.
    find_program(_maya_brew_gxx
        NAMES g++-15 g++-14 g++-13
        HINTS /opt/homebrew/bin /usr/local/bin)
    if(_maya_brew_gxx)
        set(CMAKE_CXX_COMPILER "${_maya_brew_gxx}" CACHE FILEPATH
            "C++ compiler (Homebrew GCC, auto-selected on macOS)")
        message(STATUS "maya_py: macOS — using GNU GCC at ${_maya_brew_gxx}")
    else()
        message(WARNING
            "maya_py: no Homebrew GCC (g++-15/14/13) found on PATH — falling "
            "back to the default toolchain. maya needs C++26; if the build "
            "fails, install GCC with `brew install gcc` (or pass "
            "-DCMAKE_CXX_COMPILER=/opt/homebrew/bin/g++-15).")
    endif()
endif()

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
    if(CMAKE_CXX_COMPILER_ID STREQUAL "AppleClang")
        # AppleClang is NOT supported: it lags upstream LLVM and misses the
        # C++26 / late-C++23 library bits maya leans on, so it fails deep in
        # maya's templates. On macOS the build auto-selects Homebrew GCC
        # (see the pre-project() block); if we still ended up on AppleClang
        # it's because no Homebrew GCC was found — reject it here with the
        # actionable `brew install gcc` hint rather than crash mid-compile.
        set(_maya_ok FALSE)
    elseif(CMAKE_CXX_COMPILER_VERSION VERSION_LESS 18)
        # Plain upstream LLVM/Clang >= 18 is fine.
        set(_maya_ok FALSE)
    endif()
elseif(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
    # maya's C++23 feature set needs VS 2022 17.10+ (cl 19.40). Earlier
    # toolsets miss std::expected / deducing-this and fail deep in maya.
    if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS 19.40)
        set(_maya_ok FALSE)
    endif()
endif()

if(NOT _maya_ok)
    if(WIN32)
        set(_maya_toolchain_hint
            "   3. If you truly must build from source, install Visual Studio\n"
            "      2022 17.10+ (the \"Desktop development with C++\" workload)\n"
            "      so cl.exe is >= 19.40, then re-run pip install .\n")
    elseif(APPLE)
        set(_maya_toolchain_hint
            "   3. If you truly must build from source, install GNU GCC — maya\n"
            "      is C++26 and is built with GCC on macOS, not AppleClang:\n"
            "        brew install gcc          # provides g++-15 / g++-14\n"
            "        # the build auto-picks Homebrew g++; or force it with\n"
            "        # pip install . -C cmake.define.CMAKE_CXX_COMPILER=$(brew --prefix)/bin/g++-15\n")
    else()
        set(_maya_toolchain_hint
            "   3. If you truly must build from source, install a modern GCC:\n"
            "        # Ubuntu:  sudo apt install g++-14\n"
            "        # then:    pip install . -C cmake.define.CMAKE_CXX_COMPILER=g++-14\n")
    endif()
    message(FATAL_ERROR
        "\n"
        "==============================================================\n"
        " maya-py: your C++ compiler is too old to BUILD from source.\n"
        "\n"
        "   found:    ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\n"
        "   required: GCC >= ${_maya_min_gcc}, Clang >= 18, or\n"
        "             MSVC >= 19.40 (VS 2022 17.10).  AppleClang is NOT\n"
        "             supported — on macOS build with Homebrew GCC.\n"
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
        ${_maya_toolchain_hint}
        "==============================================================\n")
endif()

# maya needs -march=native OFF for a portable extension; it also force-enables
# IPO which we don't want fighting pybind11. Keep the build lean.
set(MAYA_NATIVE_TUNING OFF CACHE BOOL "" FORCE)
set(MAYA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(MAYA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF CACHE BOOL "" FORCE)

# ── Disable C++ module dependency scanning ─────────────────────────────────
# With Ninja + a C++20-or-later standard, CMake 3.28+ scans every TU for
# module dependencies, injecting `-fmodules-ts -fmodule-mapper=... -fdeps-
# format=p1689r5` into each GCC compile. Neither maya nor this extension uses
# C++ modules, so the scan buys us nothing — and on macOS it is actively
# fatal: under -fmodules-ts, Homebrew GCC mis-preprocesses the system SDK's
# <string.h> (Annex K block), failing with "'rsize_t' has not been declared"
# deep inside Apple's _string.h. Turn scanning off for every target in this
# build (set BEFORE the targets are created so maya's subdir inherits it).
# Harmless on Linux/Windows, which were never hitting the SDK quirk.
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)

include(FetchContent)

# ── maya ──────────────────────────────────────────────────────────────────
# Prefer a sibling checkout if present (offline / hacking), else clone.
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../maya-src/CMakeLists.txt")
    message(STATUS "maya_py: using local maya at ../maya-src")
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../maya-src" maya_build)
else()
    # Pinned to a specific maya commit (not a moving `master`) so release
    # wheels are reproducible. Includes: truecolor→256/16 color downgrade,
    # blocking-writer fix for print() wide-frame truncation, Zed terminal
    # full-row repaint, and DEC-2026 sync close. Bump deliberately when pulling
    # in new maya changes.
    FetchContent_Declare(maya
        GIT_REPOSITORY https://github.com/1ay1/maya.git
        GIT_TAG        155a1b06e075b39da72c71694389910808614096)
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

# maya's CMakeLists forces cxx_std_26 via target_compile_features(PUBLIC),
# which propagates through the link interface and raises the EXTENSION to
# -std=c++26 too. The features maya actually uses are all C++23, and GCC 14
# only offers C++26 as experimental -std=c++2c. Strip the propagated feature
# requirement and pin both targets to C++23 so the build is stable on
# gcc-toolset-14. Harmless on newer compilers.
set_property(TARGET maya PROPERTY INTERFACE_COMPILE_FEATURES "")
set_property(TARGET maya PROPERTY COMPILE_FEATURES "")
set_target_properties(maya PROPERTIES CXX_STANDARD 23 CXX_STANDARD_REQUIRED ON
    CXX_SCAN_FOR_MODULES OFF)

# ── the extension ─────────────────────────────────────────────────────────
pybind11_add_module(_maya src/_maya.cpp src/_widgets.cpp src/_program.cpp)
set_target_properties(_maya PROPERTIES CXX_STANDARD 23 CXX_STANDARD_REQUIRED ON
    CXX_SCAN_FOR_MODULES OFF)
target_link_libraries(_maya PRIVATE maya::maya)

# ── MSVC / Windows build hygiene ───────────────────────────────────────────
# maya's sources are UTF-8 and contain large templated TUs; MSVC needs to be
# told both. NOMINMAX / WIN32_LEAN_AND_MEAN keep <windows.h> (pulled in by
# maya's win32 platform layer) from defining min/max macros and bloating the
# include. UNICODE makes the Win32 console APIs take wide strings, matching
# maya's win32 backend.
if(MSVC)
    target_compile_options(maya PRIVATE /utf-8 /bigobj /EHsc)
    target_compile_options(_maya PRIVATE /utf-8 /bigobj /EHsc)
    target_compile_definitions(_maya PRIVATE
        NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
    target_compile_definitions(maya PRIVATE
        NOMINMAX WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
endif()

# ── Self-contained runtime (works on machines without the build toolchain) ─
#
# maya is C++26, so the extension is built with a modern GCC and pulls in very
# new libstdc++ symbols. An end-user machine won't have that libstdc++ (on
# Linux it'd be too old; on macOS it lives only in the builder's Homebrew),
# so by default the wheel would fail to LOAD even though no compiler runs at
# install time.
#
# Fix: statically link libstdc++ and libgcc INTO the extension. It then
# carries its own C++ runtime and depends only on the platform's baseline
# system libraries. The wheel becomes truly standalone: download, unzip,
# import; the builder's GCC is irrelevant to the user.
#
# Opt out with -DMAYA_PY_STATIC_CXX=OFF (e.g. a manylinux wheel where
# auditwheel + the manylinux libstdc++ already provide portability).
option(MAYA_PY_STATIC_CXX "Statically link libstdc++/libgcc into the extension" ON)

if(MAYA_PY_STATIC_CXX AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    # -static-libstdc++/-static-libgcc are GCC driver flags and work on both
    # Linux (GNU ld) and macOS (when building with Homebrew GCC) — they bake
    # the C++ runtime into the module so it doesn't chase the builder's
    # libstdc++ at load time.
    target_link_options(_maya PRIVATE -static-libstdc++ -static-libgcc)
    # --exclude-libs hides the statically-linked C++ symbols so they can't
    # clash with a different libstdc++ already loaded in the host process.
    # It's a GNU-ld feature; Apple's ld64 doesn't understand it, so gate it
    # to non-Apple (Linux) builds only.
    if(NOT APPLE)
        target_link_options(_maya PRIVATE -Wl,--exclude-libs,ALL)
    endif()
endif()

# Install into the package dir (scikit-build-core picks this up). The
# extension is LIBRARY on POSIX (.so/.dylib) and RUNTIME on Windows (.pyd is
# treated as a DLL), so list both destinations for a portable install rule.
install(TARGETS _maya
    LIBRARY DESTINATION maya_py
    RUNTIME DESTINATION maya_py)
