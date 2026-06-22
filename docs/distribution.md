# Distribution & Standalone Wheels

[← Manual index](index.md)

This page explains how maya-py is packaged so it installs on machines with a
**very old C++ compiler — or none at all.** It's aimed at maintainers and the
curious. (Users: see the [install instructions](getting-started.md#install) —
it's on PyPI, so `pip install maya-py` is all you need.)

## The constraint

maya is **C++26** by default, and the library features it leans on
(`std::expected`, `std::format`, `views::enumerate`, deducing-this) need a
recent standard library: **GCC 14** or **Clang 19**. (Clang 18 nominally has
the language features, but its bundled libstdc++ `<expected>` support is
incomplete and fails to compile maya — Clang 19 is the real floor.) That's
newer than what old user machines have, so "compile on the user's old machine"
isn't the plan.

The answer is to **not compile on the user's machine at all.** maya-py ships
**prebuilt binary wheels**: a modern machine compiles everything once, into a
`.whl` that contains the finished `.so`. The user's machine just unzips it.

## What makes the wheel standalone

A precompiled `.so` can still fail to *load* on an old machine if it needs
runtime libraries the old system doesn't have. Two things prevent that:

### 1. Static C++ runtime

A C++23 binary built with a modern GCC pulls in newer `libstdc++` symbols
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

maya-py **tracks the latest maya** — `CMakeLists.txt` fetches `master` rather
than a frozen commit, so each tagged wheel bundles whatever maya is current at
build time. The guard against an upstream render change sneaking in is the
golden snapshot (`tests/golden.txt`, checked by `scripts/check_golden.py` in
CI); regenerate it with `--update` and commit the visual diff when maya changes
output on purpose.

The one wrinkle is the compiler: the `manylinux_2_28` image (AlmaLinux 8)
ships **gcc-toolset-14**, which is exactly what maya-py needs (C++23). So
`scripts/cibw_before_all.sh` simply enables that toolset inside the container
and symlinks its `gcc`/`g++` into `/usr/local/bin` before the build:

- default (`MAYA_PY_GCC_BUILD=0`, what CI uses) → enable `gcc-toolset-14`.
- `MAYA_PY_GCC_BUILD=1` → build a newer GCC from source (slow, ~30-60 min) —
  an escape hatch, not normally needed.

## Releasing

```bash
git tag v0.1.0
git push origin v0.1.0
```

The `wheels` workflow then:

1. enables `gcc-toolset-14` and builds the wheel inside `manylinux_2_28` for
   each CPython (3.9–3.14),
2. runs `auditwheel` to tag + bundle,
3. builds the Windows (x64) and macOS (Apple Silicon / arm64) wheels and the
   sdist,
4. attaches all artifacts to the GitHub Release (the `release` job has
   `contents: write`, so this is automatic),
5. **publishes to PyPI** via Trusted Publishing (OIDC, no stored token) —
   gated on the Linux + Windows + macOS builds, with `skip-existing` so
   re-tagging a version is safe.

All three platforms (Linux, Windows, macOS arm64) build in the same matrix and
gate the publish. macOS builds with **Homebrew GCC** — `pip` / cibuildwheel
auto-picks it via the pre-`project()` block in `CMakeLists.txt`, since
AppleClang lags upstream LLVM on the C++23/26 bits maya uses.

Users just `pip install maya-py`; `pip` picks the matching wheel automatically.

## The source-build fallback

If `pip` can't find a matching wheel (a Python/platform CI didn't cover), it
builds the sdist. On an old compiler that would fail deep inside maya's
templates, so `CMakeLists.txt` does a **preflight check**: if GCC < 14 (or
Clang < 19), it aborts immediately with an actionable message pointing the
user back to the prebuilt wheel.

## Platform status

| Platform | Wheel | Notes |
|----------|-------|-------|
| Linux x86-64 | ✅ via CI | `manylinux_2_28`, glibc ≥ 2.28, CPython 3.9–3.14 |
| Windows x64 | ✅ via CI | VS 2022 (MSVC), UCRT-linked, CPython 3.9–3.14 |
| macOS arm64 | ✅ via CI | Apple Silicon, Homebrew GCC, CPython 3.9–3.14 |
| Linux aarch64 | ⚙️ configured | same image; slower CI (emulated/native) |
| musl (Alpine) | ❌ skipped | maya's toolchain story on musl is untested |

## Summary

- Users: `pip install maya-py` — precompiled on Linux, Windows, and macOS
  (Apple Silicon), no compiler, works on old machines.
- The `.so` is self-contained (static C++ runtime, old-glibc target).
- Source builds need GCC 14+ / Clang 19+, and say so clearly if your compiler
  is too old.
