# Changelog

All notable changes to maya-py are recorded here. Versions follow
[semantic versioning](https://semver.org/) (though the API is young and the
minor series may still shift).

## 0.2.13

Rebuilt against the latest **maya** (`master`, C++26 core) and hardened the
widget bindings.

### Fixed

- **Use-after-free in four stateful widgets.** maya's `List`, `Menu`,
  `SearchResult`, and `CommandPalette` now build lazily — their
  `operator Element()` returns an element that captures `this`. The Python
  bindings previously returned a *stack-local* widget, so the resulting element
  held a dangling pointer that was dereferenced at render time
  (`MemoryError: std::bad_alloc` / `vector::reserve`). Each widget is now
  heap-owned and kept alive for the element's whole lifetime.
  Affected factories: [`list_view`](widgets.md), [`menu`](widgets.md),
  [`search_result`](widgets.md), [`command_palette`](widgets.md).

### Added

- **`Align.Auto` / `align_self="auto"`.** The default cross-axis value for a
  child; it inherits the container's `align`. See
  [Layout → align](layout.md#align-cross-axis-alignment).

## 0.2.11

- Prior release. See the
  [GitHub releases](https://github.com/1ay1/maya-py/releases) for the full
  history of earlier versions.
