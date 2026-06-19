# Production-grade roadmap — maya (C++) + maya-py

A deep-dive assessment of what's already strong and what's missing to call
both libraries "production grade," with prioritized work items.

---

## TL;DR

The engineering quality of the **core engine is already high** — the parts
that are hardest to get right (non-blocking writer with safe ANSI break
points, signal-safe terminal restore, inline-mode frame diffing, SIMD cell
diff, a real input state machine handling KKP/modifyOtherKeys/SGR mouse/OSC-52)
are done well and done deliberately. This is *not* a toy.

What separates it from "production grade" (Textual / ratatui / bubbletea
tier) is **not** the renderer — it's the surrounding **assurance, distribution,
and contract** layer:

1. **No CI on the engine** (`maya` has zero `.github/workflows`). Tests exist
   (31 suites) but nothing runs them automatically. This is the #1 gap.
2. **No sanitizer / fuzzing** on a library whose entire job is parsing
   hostile/partial byte streams from a tty.
3. **No type stubs / `py.typed`** in maya-py — Python users get no editor
   completion or `mypy` checking despite a large surface.
4. **No API stability contract** — 61 TODO/FIXME markers, a pinned-commit
   coupling between the two repos, and no semver/deprecation policy.
5. **Thin operational story** — logging, panic capture to a file, terminal
   capability detection, and degraded-mode fallbacks are partially there but
   not systematic.

---

## What's already production-grade (keep / don't regress)

**Engine (maya):**
- `Writer` non-blocking path with `safe_break_len()` — never leaves the wire
  mid-CSI/OSC/UTF-8; residue buffering preserves byte order under tty
  backpressure. The partial-write recovery (`CAN/SUB/ST/?2026l/SGR-reset`) is
  more careful than most terminals' own handling.
- Signal-safe cooked-termios capture for emergency restore on
  SIGHUP/TERM/QUIT/SEGV.
- Inline-frame state machine (`InlineFrame<Empty|Fresh|Synced|Stale|HardReset>`)
  — typestate-encoded scrollback safety.
- Synchronized output (DEC 2026) bracketing every frame → no tearing.
- Input parser: KKP (`CSI u`), xterm modifyOtherKeys=2, SGR mouse incl.
  horizontal wheel, bracketed paste, OSC-52 clipboard-over-SSH, OSC length
  bound against runaway sequences, ESC-timeout disambiguation.
- SIMD diff (AVX2/AVX512/SSE2/NEON + scalar fallback) with runtime dispatch.
- Resize coalescing (drains the whole resize burst before repaint).
- Bandwidth EMA to budget writes on slow links.

**Bindings (maya-py):**
- Genuinely clever boundary-crossing minimization: `styled_text_row` fuses an
  entire row build into one pybind call via raw CPython C-API; `memo`,
  tuple-cell specs, fast-path `box_simple`.
- Standalone wheels (static libstdc++/libgcc, manylinux_2_28, universal-ish
  matrix cp39–cp314 across Linux/macOS-arm64+intel/Windows).
- Clean separation: `_maya` (core) / `_widgets` / `_program`, with a friendly
  `easy.py` layer and a low-level surface.

---

## Priority 0 — Assurance (the real blockers)

### P0.1 CI for the engine
`maya` has **no CI**. Add `.github/workflows/ci.yml`:
- Build + `ctest` on {ubuntu-latest (gcc-14, clang-18), macos-14 (brew gcc),
  windows-2022 (MSVC 19.40)}.
- Run the 31 test suites on every push/PR. They already have 120s timeouts
  wired in CMake.
- Cache the build dir; fail the PR on any test or warning regression
  (`-Werror` in a CI-only preset).

### P0.2 Sanitizers + fuzzing on the parse/render path
The writer and input parser consume adversarial bytes. Add:
- ASan + UBSan CI job (build with `-fsanitize=address,undefined`, run ctest).
- TSan job (there's real threading: `markdown/streaming/async.cpp`,
  `canvas.cpp`, `cmd.hpp`).
- libFuzzer/AFL harnesses for: `InputParser::feed`, `safe_break_len`,
  `decode_base64`, the markdown CommonMark engine, and `Writer` op
  serialization. These are the surfaces most likely to crash on garbage.
- Run the CommonMark spec suite (`test_commonmark_spec.cpp`) as a gate.

### P0.3 maya-py CI test job (not just wheels)
`wheels.yml` builds wheels but **doesn't run the pytest suite** in CI. Add a
fast `test.yml`: build the extension once, run `pytest` (incl. the PTY tests
in `test_mouse.py`/`test_program_pty.py`) on Linux + macOS, and a no-TTY
`smoke_all.py` everywhere.

### P0.4 Golden-frame regression tests
`scripts/golden_snapshot.py` exists — wire it into CI. Snapshot the rendered
byte stream of every `examples/*.py` (headless, fixed width) and diff against
committed goldens. This catches rendering regressions the unit tests miss.

---

## Priority 1 — API contract & types

### P1.1 Ship type information for maya-py
- Add `src/maya_py/py.typed` (PEP 561 marker).
- Generate `_maya.pyi` stubs (pybind11 → `pybind11-stubgen`) and hand-write
  `.pyi` for `easy.py`/`widgets.py`/`program.py`. The public surface is huge
  (~100 symbols) and currently invisible to editors and `mypy`.
- Add a `mypy --strict` CI job over the stubs + a `ruff` lint job.

### P1.2 Decouple the repo version pinning into a contract
maya-py pins a maya git commit (`c5f8c30…`) by `FetchContent`. That's fine for
reproducibility but there's no compatibility statement. Define:
- A maya **ABI/version compatibility range** maya-py declares it supports.
- A CHANGELOG in both repos, semver, and a deprecation policy
  (warn-one-minor-before-remove).

### P1.3 Burn down the 61 TODO/FIXME
Triage into: (a) bugs → issues + tests, (b) "won't do" → delete the comment,
(c) real roadmap → CHANGELOG. A production lib shouldn't ship 61 unexplained
markers.

---

## Priority 2 — Robustness & operability

### P2.1 Terminal capability detection + degraded modes
Today color downgrade (truecolor→256→16) exists, but there's no systematic
capability probe. Add:
- `$TERM`/`$COLORTERM`/`terminfo` + DA1/DA2 query-based detection of:
  truecolor, KKP, synchronized output, bracketed paste, mouse, hyperlinks.
- A `--no-color` / `NO_COLOR` env honoring path (the [NO_COLOR](https://no-color.org)
  standard) and a "dumb terminal" fallback that emits plain text.
- Width override via `$COLUMNS`/`$LINES` when `TIOCGWINSZ` fails (CI/pipes).

### P2.2 Panic / crash diagnostics
The emergency terminal-restore path is good; add a **post-restore crash
report**: on fatal signal or uncaught C++ exception, after restoring the tty,
write a one-line cause + optional backtrace to stderr or a log file
(`MAYA_LOG=path`). maya-py should translate C++ exceptions into typed Python
exceptions (not generic `RuntimeError`).

### P2.3 Structured logging hook
A library can't `printf` to a tty it's drawing on. Add an opt-in log sink
(`MAYA_LOG` file / ring buffer / user callback) used by both repos for
diagnostics. Textual's devtools console is the model.

### P2.4 Accessibility & i18n correctness
- Verify `unicode_width` against the current Unicode version (there's a
  `test_unicode_width.cpp` and a generated table — pin the Unicode version and
  add a regen script + CI check that it's up to date).
- Grapheme-cluster awareness for emoji ZWJ sequences and combining marks in
  cursor/selection math (likely a latent bug class in input widgets).
- A screen-reader / plain-text render mode for accessibility.

---

## Priority 3 — Distribution & supply chain

### P3.1 Wheel hardening
- Sign releases / publish via PyPI **Trusted Publishing (OIDC)** — no
  long-lived token. Generate SLSA provenance + a build SBOM.
- Add `musllinux` wheels (currently skipped) — Alpine/containers are common
  for agent deployments.
- Run `auditwheel`/`delocate`/`delvewheel` verification as a gate, and an
  `abi3` evaluation (a single stable-ABI wheel per platform would cut the
  matrix 6× — feasible if the pybind surface uses the limited API).

### P3.2 Reproducible-build verification
Two independent builds of the same tag should produce byte-identical wheels
(or at least identical `.so` hashes after stripping). Add a CI check.

### P3.3 Install-time smoke beyond import
The cibuildwheel `test-command` only renders one card. Run a small headless
render of 3–4 widgets + a scroll viewport to catch link-time/SIMD-dispatch
breakage on the target arch.

---

## Priority 4 — Feature parity with the leaders

Benchmarks against the field (Textual, Rich, ratatui, bubbletea, FTXUI):

| Capability | maya status | gap |
|---|---|---|
| Flexbox layout | ✅ Yoga | — |
| Cell-diff rendering | ✅ SIMD | best-in-class |
| Inline + fullscreen | ✅ | — |
| Mouse / KKP / paste | ✅ | — |
| Widget library | ✅ 44+ native | — |
| Markdown streaming | ✅ (impressive) | — |
| **CSS-like theming / hot reload** | ⚠️ `theme.hpp` exists | no live stylesheet / hot reload (Textual's win) |
| **Async / concurrency model** | ⚠️ Cmd/Sub + threads | no first-class async task API in Python (Textual `@work`) |
| **Testing harness for apps** | ⚠️ PTY tests | no `Pilot`-style headless driver to script keypresses + assert on rendered output |
| **Focus / tab-order / a11y tree** | ⚠️ `core/focus.hpp` | no declarative focus chain or a11y surfacing |
| **Devtools / inspector** | ❌ | Textual's console + DOM inspector are a big DX edge |
| **Animation/easing system** | ⚠️ frame ticks | no declarative animation/transition primitives |

### P4.1 App test harness (highest-leverage feature)
Build a headless `Pilot` for maya-py: drive an `App`/`Program` without a tty,
inject key/mouse events, step frames, and assert on `to_string()` output or a
queryable element tree. This makes *user* apps testable and is the single
biggest credibility signal for "production framework."

### P4.2 Live theming
Promote `style/theme.hpp` to a runtime-swappable theme object exposed in
maya-py, with named tokens (`fg.muted`, `border.focus`) so apps restyle
without touching layout code.

### P4.3 Python async integration
Let `App` cooperate with `asyncio` (run the event loop in a thread or
integrate a selector), so handlers can `await`. Today long work blocks the
frame loop.

---

## Suggested sequencing

1. **Week 1–2:** P0.1 + P0.3 (CI for both repos running existing tests). Cheap,
   immediate, stops regressions. Then P1.1 (`py.typed` + stubs).
2. **Week 3–4:** P0.2 (sanitizers + fuzzing) and P0.4 (golden frames).
3. **Month 2:** P2 (capabilities, crash diagnostics, logging), P1.2/P1.3
   (version contract, TODO burn-down).
4. **Month 3:** P4.1 (test harness) — the feature that most changes
   perception — then P3 (supply chain) and remaining P4.

---

## One-paragraph verdict

The renderer and terminal layer are already at or above the quality bar of
the established frameworks; the work to be "production grade" is almost
entirely **process and contract**, not core rewrites: turn on CI, fuzz the
parsers, ship types, publish a stability promise, and add an app-test harness.
Do P0 + P1.1 + P4.1 and this is credibly production grade.
