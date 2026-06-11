# Distribution & Standalone Wheels

[← Manual index](index.md)

This page explains how maya-py is packaged so it installs on machines with a
**very old C++ compiler — or none at all.** It's aimed at maintainers and the
curious; users just `pip install maya-py`.

## The constraint

maya is **C++26** and requires **GCC 15+**. There is no way around that for
*compiling* maya — no flag downgrades it to an older standard. So "compile maya
on the user's old machine" is impossible.

The answer is to **not compile on the user's machine at all.** maya-py ships
**prebuilt binary wheels**: a modern machine compiles everything once, into a
`.whl` that contains the finished `.so`. The user's machine just unzips it.

## What makes the wheel standalone

A precompiled `.so` can still fail to *load* on an old machine if it needs
runtime libraries the old system doesn't have. Two things prevent that:

### 1. Static C++ runtime

A C++26 binary built with GCC 15 pulls in very new `libstdc++` symbols
(`GLIBCXX_3.4.3x`). An old system `libstdc++` won't have them. So the
extension is built with:

```
-static-libstdc++ -static-libgcc -Wl,--exclude-libs,ALL
```

(see `MAYA_PY_STATIC_CXX` in `CMakeLists.txt`). The `.so` then carries its own
C++ runtime and links only `libc` / `libm`:

```
$ ldd _maya*.so
    libm.so.6 => ...
    libc.so.6 => ...
```

No `libstdc++`, no `libgcc_s`. The host's C++ toolchain is irrelevant.

### 2. Old-glibc build (manylinux)

`libc` itself can't be statically linked safely (it breaks `dlopen`/NSS), so
the binary still needs a glibc *at least as new* as the one it was built
against. Building on a 2024 distro would demand `GLIBC_2.38` (2023) — too new
for old machines.

The fix is **manylinux**: build inside a container with an old glibc. maya-py
uses `manylinux_2_28` (AlmaLinux 8, **glibc 2.28 / 2019**), so the wheel runs
on any distro with glibc 2.28 or newer. `auditwheel` (run automatically by
cibuildwheel) stamps the resulting `manylinux_2_28` platform tag.

## The build pipeline

`pyproject.toml`'s `[tool.cibuildwheel]` section drives it; the GitHub Actions
workflow `.github/workflows/wheels.yml` runs it on every `vX.Y.Z` tag.

The one wrinkle: manylinux images ship at most `gcc-toolset-14`, but maya needs
GCC 15. So `scripts/cibw_before_all.sh` bootstraps the compiler inside the
container before building:

- `MAYA_PY_GCC_BUILD=1` → builds GCC 15 from source (slow, ~30-60 min; cached
  by the runner). This is what CI uses.
- default → enables the newest `gcc-toolset` available (a fallback).

## Releasing

```bash
git tag v0.1.0
git push origin v0.1.0
```

The `wheels` workflow then:

1. builds GCC 15 + the wheel inside `manylinux_2_28` for each CPython,
2. runs `auditwheel` to tag + bundle,
3. builds the sdist,
4. attaches all artifacts to the GitHub Release.

Users install with `pip install maya-py` (or from the release `.whl`).

## The source-build fallback

If `pip` can't find a matching wheel (a Python/platform CI didn't cover), it
builds the sdist. On an old compiler that would fail deep inside maya's
templates, so `CMakeLists.txt` does a **preflight check**: if GCC < 15 (or
Clang < 19), it aborts immediately with an actionable message pointing the
user back to the prebuilt wheel.

## Platform status

| Platform | Wheel | Notes |
|----------|-------|-------|
| Linux x86-64 | ✅ via CI | `manylinux_2_28`, glibc ≥ 2.28 |
| Linux aarch64 | ⚙️ configured | same image; slower CI (emulated/native) |
| macOS | ⏳ planned | needs Homebrew GCC in CI (AppleClang is C++17) |
| Windows | ⏳ planned | needs a C++26 MinGW/MSVC toolchain |
| musl (Alpine) | ❌ skipped | maya's toolchain story on musl is untested |

## Summary

- Users: `pip install maya-py` — precompiled, no compiler, works on old
  machines.
- The `.so` is self-contained (static C++ runtime, old-glibc target).
- Source builds still need GCC 15+, and say so clearly if your compiler is too
  old.
