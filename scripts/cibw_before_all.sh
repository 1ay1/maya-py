#!/usr/bin/env bash
# cibw_before_all.sh — bootstrap a C++26-capable GCC inside the manylinux
# build container, BEFORE cibuildwheel compiles the wheel.
#
# maya is C++26 and wants GCC 15. The manylinux_2_28 image ships only up to
# gcc-toolset-14. We try the toolset first (fast); if maya needs strictly
# GCC 15, set MAYA_PY_GCC_BUILD=1 in the workflow to build GCC 15 from source
# (slow — cache the result in CI).
#
# The wheel stays standalone regardless: it's built against glibc 2.28 and
# statically links libstdc++/libgcc (MAYA_PY_STATIC_CXX=ON), so the user's
# machine needs no compiler and no modern C++ runtime.
set -euo pipefail

echo "[before-all] bootstrapping toolchain in $(cat /etc/os-release 2>/dev/null | head -1 || echo unknown)"

# Newer CMake than the image ships (maya needs >= 3.28).
python3 -m pip install --upgrade "cmake>=3.28" ninja >/dev/null 2>&1 || true

if [[ "${MAYA_PY_GCC_BUILD:-0}" == "1" ]]; then
    # ── Build GCC 15 from source ──────────────────────────────────────────
    GCC_VER="${MAYA_PY_GCC_VERSION:-15.1.0}"
    PREFIX="/opt/gcc-${GCC_VER}"
    if [[ ! -x "${PREFIX}/bin/g++" ]]; then
        echo "[before-all] building GCC ${GCC_VER} from source (this is slow)…"
        yum install -y wget bzip2 make >/dev/null 2>&1 || dnf install -y wget bzip2 make >/dev/null 2>&1 || true
        cd /tmp
        wget -q "https://ftp.gnu.org/gnu/gcc/gcc-${GCC_VER}/gcc-${GCC_VER}.tar.xz"
        tar xf "gcc-${GCC_VER}.tar.xz"
        cd "gcc-${GCC_VER}"
        ./contrib/download_prerequisites
        mkdir build && cd build
        ../configure --prefix="${PREFIX}" --disable-multilib \
            --enable-languages=c,c++ --disable-bootstrap
        make -j"$(nproc)"
        make install
    fi
    export PATH="${PREFIX}/bin:${PATH}"
    echo "[before-all] using $("${PREFIX}/bin/g++" --version | head -1)"
else
    # ── Use the newest gcc-toolset the image provides ─────────────────────
    # Try toolsets 15→13 in order; enable the first that exists.
    for v in 15 14 13; do
        if yum install -y "gcc-toolset-${v}" >/dev/null 2>&1 \
           || dnf install -y "gcc-toolset-${v}" >/dev/null 2>&1; then
            echo "[before-all] enabled gcc-toolset-${v}"
            # Make the toolset's gcc the default for the build that follows.
            ln -sf "/opt/rh/gcc-toolset-${v}/root/usr/bin/gcc" /usr/local/bin/gcc
            ln -sf "/opt/rh/gcc-toolset-${v}/root/usr/bin/g++" /usr/local/bin/g++
            break
        fi
    done
    g++ --version | head -1 || true
fi

echo "[before-all] done"
