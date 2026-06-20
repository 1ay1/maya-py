// _maya.cpp — pybind11 bindings for the maya C++26 TUI framework.
//
// Exposes maya's *runtime* element-builder surface (box/text/styles/colors),
// the non-interactive renderers (print / render_to_string / live), and the
// simple event-loop run() — driven from Python callables.
//
// The compile-time DSL (t<"...">, type-state pipes) cannot cross the Python
// boundary, so everything here routes through the runtime builders in
// maya/element/builder.hpp, which produce the same Element trees.

#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>

#include <maya/maya.hpp>
#include <maya/platform/io.hpp>   // platform::io_write_all / stdout_handle (cross-platform)

#include "_pyevent.hpp"

#include <optional>
#include <array>
#include <cctype>
#include <string>
#include <unordered_map>
#include <vector>

namespace py = pybind11;
using namespace maya;

// Defined in _widgets.cpp — registers maya's widget renderers as a submodule.
void init_widgets(py::module_& m);
void init_program(py::module_& m);

// ── Event wrapper ──────────────────────────────────────────────────────────
//
// maya::Event is a std::variant; passed bare to Python, pybind's variant
// caster tries (and fails) to convert the active member. The opaque wrapper
// PyEvent (in _pyevent.hpp) keeps the event on the C++ side — Python only ever
// feeds it back through the key()/ctrl()/alt()/... predicates. It's shared
// with _program.cpp so Sub filters hand back the SAME registered type.

// ── Color ──────────────────────────────────────────────────────────────────
//
// Python sees a single Color class with classmethod constructors. We can't
// expose the consteval Color::hex, so a runtime hex() is provided here.

static Color color_rgb(int r, int g, int b) {
    return Color::rgb(static_cast<uint8_t>(r),
                      static_cast<uint8_t>(g),
                      static_cast<uint8_t>(b));
}

static Color color_hex(uint32_t rgb) {
    return Color::rgb(static_cast<uint8_t>((rgb >> 16) & 0xFF),
                      static_cast<uint8_t>((rgb >> 8) & 0xFF),
                      static_cast<uint8_t>(rgb & 0xFF));
}

// ── Element coercion ─────────────────────────────────────────────────────────
//
// Python child args may be Element OR str (auto-wrapped in text()).
static Element coerce_child(const py::handle& h) {
    if (py::isinstance<py::str>(h)) {
        return Element{TextElement{.content = h.cast<std::string>()}};
    }
    return h.cast<Element>();
}

// First UTF-8 codepoint of a byte range (U' ' if empty / malformed).
static inline char32_t decode_first_cp(const char* s, std::size_t len) {
    if (len == 0 || s == nullptr) return U' ';
    const unsigned char* p = reinterpret_cast<const unsigned char*>(s);
    unsigned char b = *p; char32_t cp; int n;
    if (b < 0x80) return b;
    else if ((b >> 5) == 0x6) { cp = b & 0x1F; n = 2; }
    else if ((b >> 4) == 0xE) { cp = b & 0x0F; n = 3; }
    else if ((b >> 3) == 0x1E){ cp = b & 0x07; n = 4; }
    else return b;
    for (int k = 1; k < n && k < static_cast<int>(len); ++k)
        cp = (cp << 6) | (p[k] & 0x3F);
    return cp;
}

// Build a styled TextElement from packed scalars (shared by styled_text and
// the bulk/fused row builders). fg/bg: packed 0xRRGGBB or <0 for unset.
// attrs bitmask: 1=bold 2=dim 4=italic 8=underline 16=strike 32=inverse.
static inline TextElement make_styled_text(std::string content, long fg, long bg,
                                           int attrs,
                                           TextWrap wrap = TextWrap::Wrap) {
    Style s{};
    if (fg >= 0)
        s = s.with_fg(Color::rgb((fg >> 16) & 0xFF, (fg >> 8) & 0xFF, fg & 0xFF));
    if (bg >= 0)
        s = s.with_bg(Color::rgb((bg >> 16) & 0xFF, (bg >> 8) & 0xFF, bg & 0xFF));
    if (attrs & 1)  s = s.with_bold();
    if (attrs & 2)  s = s.with_dim();
    if (attrs & 4)  s = s.with_italic();
    if (attrs & 8)  s = s.with_underline();
    if (attrs & 16) s = s.with_strikethrough();
    if (attrs & 32) s = s.with_inverse();
    return TextElement{.content = std::move(content), .style = s, .wrap = wrap};
}

static std::vector<Element> coerce_children(const py::args& args) {
    std::vector<Element> out;
    out.reserve(args.size());
    for (const auto& a : args) out.push_back(coerce_child(a));
    return out;
}

// ── Dimension coercion ──────────────────────────────────────────────────────
//
// A Python size value may be:
//   int            -> fixed cells
//   float in (0,1] -> percent (0.5 -> 50%)  [convenience]
//   "50%"          -> percent
//   "auto"         -> auto
//   Dimension      -> as-is
static Dimension coerce_dim(const py::handle& h) {
    if (py::isinstance<Dimension>(h)) return h.cast<Dimension>();
    if (py::isinstance<py::str>(h)) {
        std::string s = h.cast<std::string>();
        if (s == "auto") return Dimension::auto_();
        if (!s.empty() && s.back() == '%')
            return Dimension::percent(std::stof(s.substr(0, s.size() - 1)));
        throw py::value_error("bad dimension string: '" + s + "' (want 'auto' or 'N%')");
    }
    if (py::isinstance<py::float_>(h)) {
        double v = h.cast<double>();
        if (v > 0.0 && v <= 1.0) return Dimension::percent(static_cast<float>(v * 100.0));
        return Dimension::fixed(static_cast<int>(v));
    }
    return Dimension::fixed(h.cast<int>());
}

PYBIND11_MODULE(_maya, m) {
    m.doc() = "Python bindings for the maya C++26 TUI framework";

    // ── Enums ────────────────────────────────────────────────────────────
    py::enum_<FlexDirection>(m, "FlexDirection")
        .value("Row", FlexDirection::Row)
        .value("Column", FlexDirection::Column)
        .value("RowReverse", FlexDirection::RowReverse)
        .value("ColumnReverse", FlexDirection::ColumnReverse);

    py::enum_<Align>(m, "Align")
        .value("Start", Align::Start)
        .value("Center", Align::Center)
        .value("End", Align::End)
        .value("Stretch", Align::Stretch)
        .value("Baseline", Align::Baseline);

    py::enum_<Justify>(m, "Justify")
        .value("Start", Justify::Start)
        .value("Center", Justify::Center)
        .value("End", Justify::End)
        .value("SpaceBetween", Justify::SpaceBetween)
        .value("SpaceAround", Justify::SpaceAround)
        .value("SpaceEvenly", Justify::SpaceEvenly);

    py::enum_<BorderStyle>(m, "BorderStyle")
        .value("None_", BorderStyle::None)
        .value("Single", BorderStyle::Single)
        .value("Double", BorderStyle::Double)
        .value("Round", BorderStyle::Round)
        .value("Bold", BorderStyle::Bold)
        .value("SingleDouble", BorderStyle::SingleDouble)
        .value("DoubleSingle", BorderStyle::DoubleSingle)
        .value("Classic", BorderStyle::Classic)
        .value("Arrow", BorderStyle::Arrow)
        .value("Dashed", BorderStyle::Dashed);

    py::enum_<TextWrap>(m, "TextWrap")
        .value("Wrap", TextWrap::Wrap)
        .value("TruncateEnd", TextWrap::TruncateEnd)
        .value("TruncateMiddle", TextWrap::TruncateMiddle)
        .value("TruncateStart", TextWrap::TruncateStart)
        .value("NoWrap", TextWrap::NoWrap);

    py::enum_<FlexWrap>(m, "FlexWrap")
        .value("NoWrap", FlexWrap::NoWrap)
        .value("Wrap", FlexWrap::Wrap)
        .value("WrapReverse", FlexWrap::WrapReverse);

    py::enum_<Overflow>(m, "Overflow")
        .value("Visible", Overflow::Visible)
        .value("Hidden", Overflow::Hidden)
        .value("Scroll", Overflow::Scroll);

    py::enum_<BorderTextPos>(m, "BorderTextPos")
        .value("Top", BorderTextPos::Top)
        .value("Bottom", BorderTextPos::Bottom);

    py::enum_<BorderTextAlign>(m, "BorderTextAlign")
        .value("Start", BorderTextAlign::Start)
        .value("Center", BorderTextAlign::Center)
        .value("End", BorderTextAlign::End);

    py::class_<BorderSides>(m, "BorderSides")
        .def(py::init([](bool t, bool r, bool b, bool l) {
                 return BorderSides{t, r, b, l};
             }),
             py::arg("top") = true, py::arg("right") = true,
             py::arg("bottom") = true, py::arg("left") = true)
        .def_static("all", &BorderSides::all)
        .def_static("none", &BorderSides::none)
        .def_static("horizontal", &BorderSides::horizontal)
        .def_static("vertical", &BorderSides::vertical)
        .def_readwrite("top", &BorderSides::top)
        .def_readwrite("right", &BorderSides::right)
        .def_readwrite("bottom", &BorderSides::bottom)
        .def_readwrite("left", &BorderSides::left);

    py::enum_<SpecialKey>(m, "SpecialKey")
        .value("Up", SpecialKey::Up).value("Down", SpecialKey::Down)
        .value("Left", SpecialKey::Left).value("Right", SpecialKey::Right)
        .value("Home", SpecialKey::Home).value("End", SpecialKey::End)
        .value("PageUp", SpecialKey::PageUp).value("PageDown", SpecialKey::PageDown)
        .value("Tab", SpecialKey::Tab).value("BackTab", SpecialKey::BackTab)
        .value("Backspace", SpecialKey::Backspace).value("Delete", SpecialKey::Delete)
        .value("Insert", SpecialKey::Insert)
        .value("Enter", SpecialKey::Enter).value("Escape", SpecialKey::Escape)
        .value("F1", SpecialKey::F1).value("F2", SpecialKey::F2)
        .value("F3", SpecialKey::F3).value("F4", SpecialKey::F4)
        .value("F5", SpecialKey::F5).value("F6", SpecialKey::F6)
        .value("F7", SpecialKey::F7).value("F8", SpecialKey::F8)
        .value("F9", SpecialKey::F9).value("F10", SpecialKey::F10)
        .value("F11", SpecialKey::F11).value("F12", SpecialKey::F12);

    py::enum_<MouseButton>(m, "MouseButton")
        .value("Left", MouseButton::Left)
        .value("Right", MouseButton::Right)
        .value("Middle", MouseButton::Middle)
        .value("ScrollUp", MouseButton::ScrollUp)
        .value("ScrollDown", MouseButton::ScrollDown)
        .value("ScrollLeft", MouseButton::ScrollLeft)
        .value("ScrollRight", MouseButton::ScrollRight)
        .value("None_", MouseButton::None);

    py::enum_<MouseEventKind>(m, "MouseEventKind")
        .value("Press", MouseEventKind::Press)
        .value("Release", MouseEventKind::Release)
        .value("Move", MouseEventKind::Move);

    // ── Color ─────────────────────────────────────────────────────────────
    py::class_<Color>(m, "Color")
        .def_static("rgb", &color_rgb, py::arg("r"), py::arg("g"), py::arg("b"))
        .def_static("hex", &color_hex, py::arg("rgb"))
        .def_static("indexed", [](int i) { return Color::indexed(static_cast<uint8_t>(i)); })
        .def_static("default_color", &Color::default_color)
        .def_static("black", &Color::black).def_static("red", &Color::red)
        .def_static("green", &Color::green).def_static("yellow", &Color::yellow)
        .def_static("blue", &Color::blue).def_static("magenta", &Color::magenta)
        .def_static("cyan", &Color::cyan).def_static("white", &Color::white)
        .def_static("gray", &Color::gray).def_static("grey", &Color::grey)
        .def_static("bright_black", &Color::bright_black)
        .def_static("bright_red", &Color::bright_red)
        .def_static("bright_green", &Color::bright_green)
        .def_static("bright_yellow", &Color::bright_yellow)
        .def_static("bright_blue", &Color::bright_blue)
        .def_static("bright_magenta", &Color::bright_magenta)
        .def_static("bright_cyan", &Color::bright_cyan)
        .def_static("bright_white", &Color::bright_white);

    // ── Style ─────────────────────────────────────────────────────────────
    py::class_<Style>(m, "Style")
        .def(py::init<>())
        .def("with_fg", &Style::with_fg)
        .def("with_bg", &Style::with_bg)
        .def("with_bold", &Style::with_bold, py::arg("v") = true)
        .def("with_dim", &Style::with_dim, py::arg("v") = true)
        .def("with_italic", &Style::with_italic, py::arg("v") = true)
        .def("with_underline", &Style::with_underline, py::arg("v") = true)
        .def("with_strikethrough", &Style::with_strikethrough, py::arg("v") = true)
        .def("with_inverse", &Style::with_inverse, py::arg("v") = true)
        .def("merge", &Style::merge)
        .def("to_sgr", &Style::to_sgr)
        .def("empty", &Style::empty)
        .def("__or__", [](const Style& a, const Style& b) { return a.merge(b); });

    // ── Dimension ──────────────────────────────────────────────────────
    py::class_<Dimension>(m, "Dimension")
        .def_static("fixed", &Dimension::fixed, py::arg("cells"))
        .def_static("percent", &Dimension::percent, py::arg("pct"))
        .def_static("auto", &Dimension::auto_)
        .def("is_auto", &Dimension::is_auto)
        .def("is_fixed", &Dimension::is_fixed)
        .def("is_percent", &Dimension::is_percent);

    // ── Element ───────────────────────────────────────────────────────────
    // Opaque to Python; built only through the factories below.
    py::class_<Element>(m, "Element");

    // text(content, style=Style()) -> Element
    m.def("text",
          [](const std::string& content, std::optional<Style> style, TextWrap wrap) {
              TextElement t{.content = content,
                            .style = style.value_or(Style{}),
                            .wrap = wrap};
              return Element{std::move(t)};
          },
          py::arg("content"),
          py::arg("style") = std::nullopt,
          py::arg("wrap") = TextWrap::Wrap);

    m.def("blank", [] { return Element{TextElement{.content = " "}}; });

    // styled_text(content, fg, bg, attrs, wrap) -> Element  [FAST PATH]
    //
    // Builds Style + Element in ONE boundary crossing from raw scalars, so a
    // fully-styled text costs a single pybind call instead of N with_*()
    // round-trips. fg / bg are packed 0xRRGGBB ints, or -1 for "unset".
    // attrs is a bitmask: 1=bold 2=dim 4=italic 8=underline 16=strike 32=inverse.
    m.def("styled_text",
          [](const std::string& content, long fg, long bg, int attrs, TextWrap wrap) {
              return Element{make_styled_text(content, fg, bg, attrs, wrap)};
          },
          py::arg("content"), py::arg("fg") = -1, py::arg("bg") = -1,
          py::arg("attrs") = 0, py::arg("wrap") = TextWrap::Wrap);

    // styled_text_row(flat, n, direction, gap, grow) -> Element  [FUSED]
    //
    // The single biggest boundary-saver: build an ENTIRE row/col of styled
    // text PLUS its box in ONE crossing. `flat` is a FLAT Python list of
    // n*4 values interleaved [s0,fg0,bg0,a0, s1,fg1,...] — no per-cell tuple
    // objects to allocate/unpack. fg/bg packed 0xRRGGBB or <0 unset.
    // Replaces N styled_text() + 1 box_simple() with a single call.
    m.def("styled_text_row",
          [](const py::list& flat, int n, int direction, int gap, float grow) {
              std::vector<Element> kids;
              kids.reserve(static_cast<std::size_t>(n));
              // Read the flat list through the raw CPython C-API. pybind's
              // flat[i] builds a throwaway accessor proxy and .cast<> runs
              // the full type-dispatch each call; for n*4 scalars that
              // dominates the crossing. PyList_GET_ITEM is a bare array load
              // (no bounds check, no refcount), PyUnicode_AsUTF8AndSize /
              // PyLong_AsLong are the direct extractors. The Python side
              // (_fused_specs) guarantees the layout: 4 entries per cell,
              // [str, int, int, int]; anything else never reaches here.
              PyObject* lst = flat.ptr();
              for (int i = 0; i < n; ++i) {
                  const int o = i * 4;
                  PyObject* ps = PyList_GET_ITEM(lst, o);
                  Py_ssize_t slen = 0;
                  const char* sdata = PyUnicode_AsUTF8AndSize(ps, &slen);
                  std::string s = sdata ? std::string(sdata, static_cast<std::size_t>(slen))
                                        : std::string{};
                  long fg = PyLong_AsLong(PyList_GET_ITEM(lst, o + 1));
                  long bg = PyLong_AsLong(PyList_GET_ITEM(lst, o + 2));
                  int  at = static_cast<int>(PyLong_AsLong(PyList_GET_ITEM(lst, o + 3)));
                  kids.push_back(Element{make_styled_text(std::move(s), fg, bg, at)});
              }
              auto b = maya::box();
              b.direction(direction == 0 ? FlexDirection::Row
                                         : FlexDirection::Column);
              if (gap >= 0)  b.gap(gap);
              if (grow >= 0) b.grow(grow);
              return b(kids);
          },
          py::arg("flat"), py::arg("n"), py::arg("direction"),
          py::arg("gap") = -1, py::arg("grow") = -1.0f);

    // styled_grid(flat, row_lens, inner_dir, outer_gap, inner_gap) -> Element
    //                                                          [FUSED x N rows]
    //
    // The single biggest saver for LIST-heavy UIs (a col of N rows, or a row
    // of N cols, where every cell is plain styled text). Builds the ENTIRE
    // nested tree — the outer box AND all its inner boxes — in ONE crossing.
    //
    // `flat` is every cell of every inner box, concatenated, 4 scalars each:
    //   [s,fg,bg,a,  s,fg,bg,a,  ...]   (same layout as styled_text_row)
    // `row_lens` is the cell count of each inner box, in order; their sum * 4
    // must equal len(flat). The outer box runs perpendicular to the inner
    // boxes: inner_dir 0=Row means each inner box is a horizontal row and the
    // outer stacks them as a Column (the col(row,row,…) shape); inner_dir 1
    // is the transpose. This replaces N styled_text_row() + N Python row()
    // frames + 1 box_simple() with a single call — no per-row boundary cross,
    // no per-row Python dispatch.
    m.def("styled_grid",
          [](const py::list& flat, const py::list& row_lens, int inner_dir,
             int outer_gap, int inner_gap) {
              PyObject* lst = flat.ptr();
              PyObject* lens = row_lens.ptr();
              const Py_ssize_t nrows = PyList_GET_SIZE(lens);
              FlexDirection idir = inner_dir == 0 ? FlexDirection::Row
                                                  : FlexDirection::Column;
              FlexDirection odir = inner_dir == 0 ? FlexDirection::Column
                                                  : FlexDirection::Row;
              std::vector<Element> rows;
              rows.reserve(static_cast<std::size_t>(nrows));
              int cursor = 0;   // running cell index into `flat` (×4 for scalar)
              for (Py_ssize_t r = 0; r < nrows; ++r) {
                  const int cells = static_cast<int>(
                      PyLong_AsLong(PyList_GET_ITEM(lens, r)));
                  std::vector<Element> kids;
                  kids.reserve(static_cast<std::size_t>(cells));
                  for (int i = 0; i < cells; ++i) {
                      const int o = (cursor + i) * 4;
                      PyObject* ps = PyList_GET_ITEM(lst, o);
                      Py_ssize_t slen = 0;
                      const char* sdata = PyUnicode_AsUTF8AndSize(ps, &slen);
                      std::string s = sdata
                          ? std::string(sdata, static_cast<std::size_t>(slen))
                          : std::string{};
                      long fg = PyLong_AsLong(PyList_GET_ITEM(lst, o + 1));
                      long bg = PyLong_AsLong(PyList_GET_ITEM(lst, o + 2));
                      int  at = static_cast<int>(
                          PyLong_AsLong(PyList_GET_ITEM(lst, o + 3)));
                      kids.push_back(Element{
                          make_styled_text(std::move(s), fg, bg, at)});
                  }
                  cursor += cells;
                  auto ib = maya::box();
                  ib.direction(idir);
                  if (inner_gap >= 0) ib.gap(inner_gap);
                  rows.push_back(ib(kids));
              }
              auto ob = maya::box();
              ob.direction(odir);
              if (outer_gap >= 0) ob.gap(outer_gap);
              return ob(rows);
          },
          py::arg("flat"), py::arg("row_lens"), py::arg("inner_dir"),
          py::arg("outer_gap") = -1, py::arg("inner_gap") = -1);

    // cell_grid(grid, w, h, gap) -> Element   [RUN-MERGED FULL-COLOUR GRID]
    //
    // The canonical native builder for a 2-D cell grid where EVERY cell may
    // carry its own fg AND bg — the pattern hand-drawn panels build as a
    // Python `[[cell-or-None] * w] * h` then convert to `col(row(*specs)...)`.
    // That conversion is the bottleneck: it allocates one styled-text Element
    // PER CELL (w*h of them) and crosses the boundary once PER ROW.
    //
    // This takes the raw grid and builds ONE TextElement per row with
    // RUN-MERGED StyledRuns (consecutive same-(fg,bg) cells share a run), in a
    // single crossing. Fewer elements => the grid renders faster too. Output
    // is pixel-identical to the per-cell form (same glyph + same fg/bg at each
    // column; run-merging only changes the element tree, not the painted
    // cells).
    //
    // Each cell is one of:
    //   None / a 1-char str        -> that glyph, inherited colours
    //   (ch, fg)                    -> glyph + fg
    //   (ch, fg, bg)                -> glyph + fg + bg
    // fg/bg are a packed 0xRRGGBB int, an (r,g,b) tuple/list, or <0 / None for
    // unset. Missing rows / short rows are padded with blank inherited cells.
    m.def("cell_grid",
          [](const py::list& grid, int w, int h, int gap) -> Element {
              // Resolve a colour handle to packed 0xRRGGBB or -1 (unset).
              auto pack = [](PyObject* o) -> long {
                  if (o == nullptr || o == Py_None) return -1;
                  if (PyLong_Check(o)) return PyLong_AsLong(o);
                  // (r,g,b) tuple or list
                  if (PyTuple_Check(o)) {
                      if (PyTuple_GET_SIZE(o) < 3) return -1;
                      long r = PyLong_AsLong(PyTuple_GET_ITEM(o, 0));
                      long g = PyLong_AsLong(PyTuple_GET_ITEM(o, 1));
                      long b = PyLong_AsLong(PyTuple_GET_ITEM(o, 2));
                      return (r << 16) | (g << 8) | b;
                  }
                  if (PyList_Check(o)) {
                      if (PyList_GET_SIZE(o) < 3) return -1;
                      long r = PyLong_AsLong(PyList_GET_ITEM(o, 0));
                      long g = PyLong_AsLong(PyList_GET_ITEM(o, 1));
                      long b = PyLong_AsLong(PyList_GET_ITEM(o, 2));
                      return (r << 16) | (g << 8) | b;
                  }
                  return -1;
              };
              auto style_of = [](long fg, long bg, int attrs) -> Style {
                  Style s{};
                  if (fg >= 0)
                      s = s.with_fg(Color::rgb((fg >> 16) & 0xFF,
                                               (fg >> 8) & 0xFF, fg & 0xFF));
                  if (bg >= 0)
                      s = s.with_bg(Color::rgb((bg >> 16) & 0xFF,
                                               (bg >> 8) & 0xFF, bg & 0xFF));
                  if (attrs & 1)  s = s.with_bold();
                  if (attrs & 2)  s = s.with_dim();
                  if (attrs & 4)  s = s.with_italic();
                  if (attrs & 8)  s = s.with_underline();
                  if (attrs & 16) s = s.with_strikethrough();
                  if (attrs & 32) s = s.with_inverse();
                  return s;
              };
              PyObject* g = grid.ptr();
              const Py_ssize_t nrows_in = PyList_GET_SIZE(g);
              std::vector<Element> rows;
              rows.reserve(static_cast<std::size_t>(h));
              for (int y = 0; y < h; ++y) {
                  PyObject* rowobj = (y < nrows_in)
                      ? PyList_GET_ITEM(g, y) : nullptr;
                  const bool is_list = rowobj && PyList_Check(rowobj);
                  const Py_ssize_t ncells = is_list
                      ? PyList_GET_SIZE(rowobj) : 0;
                  std::string content;
                  content.reserve(static_cast<std::size_t>(w) * 2);
                  std::vector<StyledRun> runs;
                  // run accumulator
                  long run_fg = -2, run_bg = -2; int run_at = 0;  // -2 = none
                  std::size_t run_start = 0;
                  auto flush = [&] {
                      if (run_fg == -2) return;
                      if (run_fg >= 0 || run_bg >= 0 || run_at != 0)
                          runs.push_back(StyledRun{
                              run_start, content.size() - run_start,
                              style_of(run_fg, run_bg, run_at)});
                      run_fg = -2; run_bg = -2; run_at = 0;
                  };
                  for (int x = 0; x < w; ++x) {
                      char32_t ch = U' ';
                      long fg = -1, bg = -1; int at = 0;
                      if (x < ncells) {
                          PyObject* cell = PyList_GET_ITEM(rowobj, x);
                          if (cell == Py_None) {
                              ch = U' ';
                          } else if (PyUnicode_Check(cell)) {
                              Py_ssize_t sl = 0;
                              const char* sd = PyUnicode_AsUTF8AndSize(cell, &sl);
                              ch = decode_first_cp(sd, static_cast<std::size_t>(sl));
                          } else if (PyTuple_Check(cell)) {
                              Py_ssize_t cn = PyTuple_GET_SIZE(cell);
                              if (cn >= 1) {
                                  PyObject* cs = PyTuple_GET_ITEM(cell, 0);
                                  if (PyUnicode_Check(cs)) {
                                      Py_ssize_t sl = 0;
                                      const char* sd =
                                          PyUnicode_AsUTF8AndSize(cs, &sl);
                                      ch = decode_first_cp(
                                          sd, static_cast<std::size_t>(sl));
                                  }
                              }
                              if (cn >= 2) fg = pack(PyTuple_GET_ITEM(cell, 1));
                              if (cn >= 3) bg = pack(PyTuple_GET_ITEM(cell, 2));
                              if (cn >= 4) {
                                  PyObject* ao = PyTuple_GET_ITEM(cell, 3);
                                  if (PyLong_Check(ao))
                                      at = static_cast<int>(PyLong_AsLong(ao));
                              }
                          }
                      }
                      if (fg != run_fg || bg != run_bg || at != run_at) {
                          flush();
                          run_fg = fg; run_bg = bg; run_at = at;
                          run_start = content.size();
                      }
                      detail::encode_utf8(ch, content);
                  }
                  flush();
                  rows.push_back(Element{TextElement{
                      .content = std::move(content),
                      .style = {},
                      .wrap = TextWrap::NoWrap,
                      .runs = std::move(runs),
                  }});
              }
              auto ob = maya::box();
              ob.direction(FlexDirection::Column);
              if (gap >= 0) ob.gap(gap);
              return ob(rows);
          },
          py::arg("grid"), py::arg("w"), py::arg("h"), py::arg("gap") = 0);

    // box_simple(children, direction, gap, grow) -> Element  [FAST PATH]
    //
    // The overwhelming-majority box: a plain row/col with at most a gap and
    // an optional grow, no border/padding/sizing. Takes a pre-built child
    // LIST + scalars positionally, so pybind does NO kwargs-dict construction
    // and the body does NO opts.contains() probing (the full box() runs ~25
    // dict lookups from C++ per call). children is an already-coerced list of
    // Element; direction 0=Row 1=Column; gap<0 means unset; grow<0 unset.
    m.def("box_simple",
          [](const std::vector<Element>& children, int direction, int gap,
             float grow) {
              auto b = maya::box();
              b.direction(direction == 0 ? FlexDirection::Row
                                         : FlexDirection::Column);
              if (gap >= 0)  b.gap(gap);
              if (grow >= 0) b.grow(grow);
              return b(children);
          },
          py::arg("children"), py::arg("direction"),
          py::arg("gap") = -1, py::arg("grow") = -1.0f);

    // box_titled(children, direction, gap, grow, border, pad, title,
    //            border_color) -> Element  [FAST PATH for card()]
    //
    // card()/titled panels are the most common container, but a `title=`
    // forced them onto the full box() path (kwargs dict + ~25 opts.contains()
    // probes in C++). This builds the exact card shape — a bordered, padded
    // box with a centred ` title ` on the top edge — from positional scalars,
    // no dict, no probing. children is a pre-coerced Element list; border is a
    // BorderStyle index (<0 = none); pad<0 = unset; title empty = no title;
    // border_color packed 0xRRGGBB or <0 unset.
    m.def("box_titled",
          [](const std::vector<Element>& children, int direction, int gap,
             float grow, int border, int pad, const std::string& title,
             long border_color) {
              auto b = maya::box();
              b.direction(direction == 0 ? FlexDirection::Row
                                         : FlexDirection::Column);
              if (gap >= 0)  b.gap(gap);
              if (grow >= 0) b.grow(grow);
              if (pad >= 0)  b.padding(pad, pad, pad, pad);
              if (border >= 0)
                  b.border(static_cast<BorderStyle>(border));
              if (border_color >= 0)
                  b.border_color(Color::rgb((border_color >> 16) & 0xFF,
                                            (border_color >> 8) & 0xFF,
                                            border_color & 0xFF));
              if (!title.empty())
                  b.border_text(" " + title + " ");
              return b(children);
          },
          py::arg("children"), py::arg("direction"), py::arg("gap") = -1,
          py::arg("grow") = -1.0f, py::arg("border") = -1, py::arg("pad") = -1,
          py::arg("title") = "", py::arg("border_color") = -1);

    // box(*children, **opts) -> Element
    //
    // Full mirror of maya's BoxBuilder. Recognised opts:
    //   direction, wrap, gap, padding, margin
    //   border, border_color, border_text, border_sides
    //   bg, fg, style, overflow
    //   grow, shrink, basis, align, align_self, justify
    //   width, height, min_width, min_height, max_width, max_height
    // padding/margin accept int or 1/2/4-tuple; size opts accept
    // int / float / "N%" / "auto" / Dimension. border_text accepts a
    // str, or a (str, pos) / (str, pos, align) tuple. style accepts a Style.
    m.def("box",
          [](py::args children, const py::kwargs& opts) {
              auto b = maya::box();

              auto edges = [](BoxBuilder& bb, const py::handle& p, bool is_pad) {
                  std::array<int, 4> e{};
                  int n = 1;
                  if (py::isinstance<py::tuple>(p) || py::isinstance<py::list>(p)) {
                      auto tup = p.cast<py::sequence>();
                      n = static_cast<int>(tup.size());
                      if (n == 1) e = {tup[0].cast<int>(), tup[0].cast<int>(),
                                       tup[0].cast<int>(), tup[0].cast<int>()};
                      else if (n == 2) { int v = tup[0].cast<int>(), h = tup[1].cast<int>();
                                         e = {v, h, v, h}; }
                      else if (n == 4) e = {tup[0].cast<int>(), tup[1].cast<int>(),
                                            tup[2].cast<int>(), tup[3].cast<int>()};
                      else throw py::value_error("padding/margin tuple must have 1, 2, or 4 ints");
                  } else {
                      int v = p.cast<int>();
                      e = {v, v, v, v};
                  }
                  if (is_pad) bb.padding(e[0], e[1], e[2], e[3]);
                  else        bb.margin(e[0], e[1], e[2], e[3]);
              };

              if (opts.contains("direction"))
                  b.direction(opts["direction"].cast<FlexDirection>());
              if (opts.contains("wrap"))
                  b.wrap(opts["wrap"].cast<FlexWrap>());
              if (opts.contains("gap"))
                  b.gap(opts["gap"].cast<int>());
              if (opts.contains("padding")) edges(b, opts["padding"], true);
              if (opts.contains("margin"))  edges(b, opts["margin"], false);

              if (opts.contains("border"))
                  b.border(opts["border"].cast<BorderStyle>());
              if (opts.contains("border_color"))
                  b.border_color(opts["border_color"].cast<Color>());
              if (opts.contains("border_sides"))
                  b.border_sides(opts["border_sides"].cast<BorderSides>());
              if (opts.contains("border_text")) {
                  auto t = opts["border_text"];
                  if (py::isinstance<py::tuple>(t) || py::isinstance<py::list>(t)) {
                      auto tup = t.cast<py::sequence>();
                      auto txt = tup[0].cast<std::string>();
                      auto pos = tup.size() > 1 ? tup[1].cast<BorderTextPos>()
                                                : BorderTextPos::Top;
                      if (tup.size() > 2)
                          b.border_text(txt, pos, tup[2].cast<BorderTextAlign>());
                      else
                          b.border_text(txt, pos);
                  } else {
                      b.border_text(t.cast<std::string>());
                  }
              }
              if (opts.contains("border_text_end")) {
                  auto t = opts["border_text_end"];
                  if (py::isinstance<py::tuple>(t) || py::isinstance<py::list>(t)) {
                      auto tup = t.cast<py::sequence>();
                      auto txt = tup[0].cast<std::string>();
                      auto pos = tup.size() > 1 ? tup[1].cast<BorderTextPos>()
                                                : BorderTextPos::Top;
                      auto al  = tup.size() > 2 ? tup[2].cast<BorderTextAlign>()
                                                : BorderTextAlign::End;
                      b.border_text_end(txt, pos, al);
                  } else {
                      b.border_text_end(t.cast<std::string>());
                  }
              }

              if (opts.contains("bg"))    b.bg(opts["bg"].cast<Color>());
              if (opts.contains("fg"))    b.fg(opts["fg"].cast<Color>());
              if (opts.contains("style")) b.style(opts["style"].cast<Style>());
              if (opts.contains("overflow"))
                  b.overflow(opts["overflow"].cast<Overflow>());

              if (opts.contains("grow"))   b.grow(opts["grow"].cast<float>());
              if (opts.contains("shrink")) b.shrink(opts["shrink"].cast<float>());
              if (opts.contains("basis"))  b.basis(coerce_dim(opts["basis"]));
              if (opts.contains("align"))
                  b.align_items(opts["align"].cast<Align>());
              if (opts.contains("align_self"))
                  b.align_self(opts["align_self"].cast<Align>());
              if (opts.contains("justify"))
                  b.justify(opts["justify"].cast<Justify>());

              if (opts.contains("width"))      b.width(coerce_dim(opts["width"]));
              if (opts.contains("height"))     b.height(coerce_dim(opts["height"]));
              if (opts.contains("min_width"))  b.min_width(coerce_dim(opts["min_width"]));
              if (opts.contains("min_height")) b.min_height(coerce_dim(opts["min_height"]));
              if (opts.contains("max_width"))  b.max_width(coerce_dim(opts["max_width"]));
              if (opts.contains("max_height")) b.max_height(coerce_dim(opts["max_height"]));

              auto kids = coerce_children(children);
              return b(kids);
          });

    // Convenience: vstack / hstack — thin wrappers that fix direction then
    // delegate to the box() Python object (so all kwargs work identically).
    auto box_obj = m.attr("box");
    m.def("vstack", [box_obj](py::args children, py::kwargs opts) {
        opts["direction"] = FlexDirection::Column;
        return box_obj(*children, **opts).cast<Element>();
    });
    m.def("hstack", [box_obj](py::args children, py::kwargs opts) {
        opts["direction"] = FlexDirection::Row;
        return box_obj(*children, **opts).cast<Element>();
    });

    // center(*children, **opts) -> Element
    // A box that centers its children on both axes (align+justify Center).
    m.def("center", [box_obj](py::args children, py::kwargs opts) {
        opts["align"] = Align::Center;
        opts["justify"] = Justify::Center;
        return box_obj(*children, **opts).cast<Element>();
    });

    // zstack(*layers) -> Element
    // Layer children on top of each other; first child sets the size.
    m.def("zstack", [](py::args layers) {
        return maya::detail::zstack(coerce_children(layers));
    });

    // nothing() -> Element  (zero-row transparent fragment)
    m.def("nothing", [] { return maya::detail::nothing(); });

    // component(render_fn) -> Element
    // Lazy element: render_fn(width, height) -> Element, called once the
    // layout allocates a size. Lets Python size-aware widgets (charts,
    // gauges) fill whatever the flexbox gives them.
    //
    // GIL SAFETY: maya copies the ComponentElement (and thus this callback's
    // captures) by value MANY times during paint/cache, with the GIL
    // RELEASED (run()/live() drop it for the blocking loop). A captured
    // py::function would inc/decref a PyObject on every copy without the GIL
    // → heap corruption → segfault. So we stash the callable behind a
    // shared_ptr: copying the std::function only bumps the shared_ptr
    // refcount (no Python touch). The Python object is released exactly once,
    // by a deleter that takes the GIL first.
    m.def("component",
          [](py::function render_fn, std::optional<float> grow,
             std::optional<py::object> width, std::optional<py::object> height) {
              auto fn = std::shared_ptr<py::function>(
                  new py::function(std::move(render_fn)),
                  [](py::function* p) {
                      py::gil_scoped_acquire gil;
                      delete p;
                  });
              auto cb = maya::detail::component(
                  [fn](int w, int h) -> Element {
                      py::gil_scoped_acquire gil;
                      py::object r = (*fn)(w, h);
                      if (py::isinstance<py::str>(r))
                          return Element{TextElement{.content = r.cast<std::string>()}};
                      if (!py::isinstance<Element>(r))
                          throw py::type_error(
                              "component render_fn must return a maya Element or str, got "
                              + std::string(py::str(r.get_type().attr("__name__"))));
                      return r.cast<Element>();
                  });
              if (grow)   cb.grow(*grow);
              if (width)  cb.width(coerce_dim(*width));
              if (height) cb.height(coerce_dim(*height));
              return static_cast<Element>(cb);
          },
          py::arg("render_fn"), py::arg("grow") = std::nullopt,
          py::arg("width") = std::nullopt, py::arg("height") = std::nullopt);

    // ── Renderers ─────────────────────────────────────────────────────────
    m.def("print_element",
          [](const Element& e, std::optional<int> width) {
              if (width) maya::print(e, *width);
              else maya::print(e);
          },
          py::arg("element"), py::arg("width") = std::nullopt);

    // render_to_string(element, width) -> str
    //
    // Reuses thread-local scratch (Canvas + StylePool + layout_nodes) across
    // calls, so repeated renders (live overlays, the bench, any redraw loop
    // that goes through to_string) pay ZERO per-call heap allocation for the
    // 80×N cell grid and the layout-node vector. Mirrors maya's
    // render_to_string body but keeps the buffers warm between invocations.
    m.def("render_to_string",
          [](const Element& e, int width) -> std::string {
              thread_local StylePool pool;
              thread_local std::vector<layout::LayoutNode> layout_nodes;
              thread_local Canvas canvas{1, 1, &pool};
              thread_local int last_width = -1;
              thread_local int last_used_rows = 0;   // rows touched last call

              constexpr int kInitH = 120;   // covers the common < 2-screen case
              if (width != last_width || canvas.height() < kInitH) {
                  canvas.resize(width, kInitH);
                  last_width = width;
                  last_used_rows = canvas.height();   // full clear after resize
              }
              canvas.set_style_pool(&pool);
              // Clear only the rows the previous render actually wrote (plus a
              // small margin) instead of the whole kInitH-row grid — most
              // frames use a fraction of the canvas, so a full clear() wastes
              // cycles zeroing blank rows. clear_rows(n) caps at height().
              {
                  int n = last_used_rows + 4;
                  if (n > canvas.height()) n = canvas.height();
                  canvas.clear_rows(n);
              }
              render_tree(e, canvas, pool, theme::dark, layout_nodes,
                          /*auto_height=*/true);

              int rows = content_height(canvas);
              if (rows >= canvas.height() && !layout_nodes.empty()) {
                  int needed = layout_nodes[0].computed.size.height.raw();
                  if (needed > canvas.height()) {
                      canvas.resize(width, needed + 8);
                      canvas.clear();
                      render_tree(e, canvas, pool, theme::dark, layout_nodes,
                                  /*auto_height=*/true);
                      rows = content_height(canvas);
                  }
              }
              if (rows < 0) { last_used_rows = 0; return {}; }
              last_used_rows = rows + 1;

              // Encode straight from the packed cell buffer. Two wins over
              // the old get(x,y) loop:
              //  (1) last_content_col(y) gives each row's trimmed extent
              //      in O(1) (maya maintains it incrementally) — no need to
              //      emit width trailing blanks then rescan-and-trim them.
              //  (2) reading the row pointer + masking the low 32 bits
              //      (Cell::character) skips get()'s bounds check and the
              //      full Cell::unpack (style/link/width fields we discard).
              const uint64_t* cells = canvas.cells();
              const int cw = canvas.width();
              std::string result;
              result.reserve(static_cast<std::size_t>((width + 1) * (rows + 1)));
              for (int y = 0; y <= rows; ++y) {
                  int last = canvas.last_content_col(y);
                  if (last > width - 1) last = width - 1;
                  const uint64_t* rowp = cells + static_cast<std::size_t>(y) * cw;
                  // Match the old trim semantics: drop trailing cells whose
                  // CHARACTER is a space, regardless of style. last_content_col
                  // counts a styled (e.g. bg-coloured) space as content, but
                  // to_string emits characters only, so a trailing styled
                  // space is indistinguishable from a plain one and must be
                  // trimmed identically.
                  while (last >= 0) {
                      char32_t c = static_cast<char32_t>(rowp[last] & 0xFFFFFFFFu);
                      if (c == U' ' || c == U'\0') --last; else break;
                  }
                  for (int x = 0; x <= last; ++x) {
                      char32_t ch = static_cast<char32_t>(rowp[x] & 0xFFFFFFFFu);
                      if (ch == U'\0') ch = U' ';
                      detail::encode_utf8(ch, result);
                  }
                  if (y < rows) result += '\n';
              }
              return result;
          },
          py::arg("element"), py::arg("width") = 80);

    // ── live() — inline render loop ───────────────────────────────────────
    // render_fn: (dt: float) -> Element. Call maya.quit() to stop.
    m.def("live",
          [](py::function render_fn, int fps, int max_width, bool cursor) {
              LiveConfig cfg{.fps = fps, .max_width = max_width, .cursor = cursor};
              // Release the GIL for the blocking loop so Python signal handlers
              // (Ctrl-C → KeyboardInterrupt) can run; the render callback below
              // re-acquires it. Without this the interpreter is frozen for the
              // whole loop and Ctrl-C is dead.
              py::gil_scoped_release nogil;
              maya::live(cfg, [&render_fn](float dt) -> Element {
                  py::gil_scoped_acquire gil;
                  // Let a pending KeyboardInterrupt (or other async signal)
                  // surface as a C++ exception that unwinds the loop and
                  // restores the terminal via maya's RAII cleanup.
                  if (PyErr_CheckSignals() != 0) throw py::error_already_set();
                  py::object r = render_fn(dt);
                  if (!py::isinstance<Element>(r))
                      throw py::type_error(
                          "live render_fn must return a maya Element, got "
                          + std::string(py::str(r.get_type().attr("__name__"))));
                  return r.cast<Element>();
              });
          },
          py::arg("render_fn"), py::arg("fps") = 30,
          py::arg("max_width") = 0, py::arg("cursor") = false);

    m.def("quit", &maya::quit);
    // Runtime mouse-capture toggle (see maya::set_mouse). Call from an App
    // handler to hand the wheel back to the terminal (off) or recapture it (on).
    m.def("set_mouse", &maya::set_mouse, py::arg("on"));

    // ── Event (opaque) + predicates ───────────────────────────────────────
    // maya's Event is std::variant<KeyEvent, MouseEvent, ...>. pybind11/stl.h
    // installs a variant caster that would try to convert the active member
    // to Python — but those member types aren't registered, so the cast
    // fails. Python never inspects the event directly (it only goes back
    // through the key()/ctrl()/... predicates below), so wrap it in an opaque
    // struct that pybind treats as a plain registered class, not a variant.
    py::class_<PyEvent>(m, "Event");

    // ── synthetic event factories (headless driving / testing) ───────────
    // The native run() loop is the only place real Events come from. For
    // in-process tests and a headless Pilot driver, these build the SAME
    // PyEvent the loop would deliver, so every key()/ctrl()/mouse_* predicate
    // and every App/Program handler treats them identically to live input.
    auto mods_of = [](bool ctrl, bool alt, bool shift, bool super_) {
        return maya::Modifiers{.ctrl = ctrl, .alt = alt,
                               .shift = shift, .super_ = super_};
    };
    // first UTF-8 codepoint of s (0 if empty / malformed lead byte)
    auto first_cp = [](const std::string& s) -> char32_t {
        if (s.empty()) return 0;
        unsigned char c0 = static_cast<unsigned char>(s[0]);
        if (c0 < 0x80) return c0;
        int n = (c0 >= 0xF0) ? 3 : (c0 >= 0xE0) ? 2 : (c0 >= 0xC0) ? 1 : 0;
        char32_t cp = c0 & (0x3F >> n);
        for (int k = 1; k <= n && k < static_cast<int>(s.size()); ++k)
            cp = (cp << 6) | (static_cast<unsigned char>(s[k]) & 0x3F);
        return cp;
    };

    // make_key("a") / make_key("enter", ctrl=True) -> Event
    // A single printable char becomes a CharKey; a special-key NAME (matching
    // SpecialKey, case-insensitive) becomes that SpecialKey.
    m.def("make_key",
          [first_cp, mods_of](const std::string& s, bool ctrl, bool alt,
                              bool shift, bool super_) {
              static const std::unordered_map<std::string, SpecialKey> kSpecial = {
                  {"up", SpecialKey::Up}, {"down", SpecialKey::Down},
                  {"left", SpecialKey::Left}, {"right", SpecialKey::Right},
                  {"home", SpecialKey::Home}, {"end", SpecialKey::End},
                  {"pageup", SpecialKey::PageUp}, {"pagedown", SpecialKey::PageDown},
                  {"tab", SpecialKey::Tab}, {"backtab", SpecialKey::BackTab},
                  {"backspace", SpecialKey::Backspace}, {"delete", SpecialKey::Delete},
                  {"insert", SpecialKey::Insert}, {"enter", SpecialKey::Enter},
                  {"escape", SpecialKey::Escape}, {"esc", SpecialKey::Escape},
                  {"space", SpecialKey::Enter},  // overwritten below
                  {"f1", SpecialKey::F1}, {"f2", SpecialKey::F2}, {"f3", SpecialKey::F3},
                  {"f4", SpecialKey::F4}, {"f5", SpecialKey::F5}, {"f6", SpecialKey::F6},
                  {"f7", SpecialKey::F7}, {"f8", SpecialKey::F8}, {"f9", SpecialKey::F9},
                  {"f10", SpecialKey::F10}, {"f11", SpecialKey::F11}, {"f12", SpecialKey::F12},
              };
              std::string low;
              low.reserve(s.size());
              for (char ch : s) low += static_cast<char>(std::tolower(
                  static_cast<unsigned char>(ch)));
              KeyEvent ke{};
              ke.mods = mods_of(ctrl, alt, shift, super_);
              if (low == "space") {
                  ke.key = CharKey{U' '};
              } else if (auto it = kSpecial.find(low); it != kSpecial.end()) {
                  ke.key = it->second;
              } else {
                  ke.key = CharKey{first_cp(s)};
              }
              return PyEvent{Event{std::move(ke)}};
          },
          py::arg("key"), py::arg("ctrl") = false, py::arg("alt") = false,
          py::arg("shift") = false, py::arg("super") = false,
          "Build a synthetic key Event (for headless driving / tests).");

    // make_mouse(col, row, button="left", kind="press") -> Event
    m.def("make_mouse",
          [mods_of](int col, int row, const std::string& button,
                    const std::string& kind, bool ctrl, bool alt, bool shift) {
              static const std::unordered_map<std::string, MouseButton> kBtn = {
                  {"left", MouseButton::Left}, {"right", MouseButton::Right},
                  {"middle", MouseButton::Middle},
                  {"scrollup", MouseButton::ScrollUp},
                  {"scrolldown", MouseButton::ScrollDown},
                  {"none", MouseButton::None},
              };
              static const std::unordered_map<std::string, MouseEventKind> kKind = {
                  {"press", MouseEventKind::Press},
                  {"release", MouseEventKind::Release},
                  {"move", MouseEventKind::Move},
              };
              MouseEvent me{};
              auto bit = kBtn.find(button);
              me.button = bit != kBtn.end() ? bit->second : MouseButton::Left;
              auto kit = kKind.find(kind);
              me.kind = kit != kKind.end() ? kit->second : MouseEventKind::Press;
              me.x = Columns{col};
              me.y = Rows{row};
              me.mods = mods_of(ctrl, alt, shift, false);
              return PyEvent{Event{me}};
          },
          py::arg("col"), py::arg("row"), py::arg("button") = "left",
          py::arg("kind") = "press", py::arg("ctrl") = false,
          py::arg("alt") = false, py::arg("shift") = false,
          "Build a synthetic mouse Event (for headless driving / tests).");

    // make_scroll("up"|"down", col=1, row=1) -> Event
    m.def("make_scroll",
          [](const std::string& dir, int col, int row) {
              MouseEvent me{};
              me.button = (dir == "up") ? MouseButton::ScrollUp
                                        : MouseButton::ScrollDown;
              me.kind = MouseEventKind::Press;
              me.x = Columns{col};
              me.y = Rows{row};
              return PyEvent{Event{me}};
          },
          py::arg("direction"), py::arg("col") = 1, py::arg("row") = 1,
          "Build a synthetic scroll-wheel Event.");

    // make_paste(text) -> Event
    m.def("make_paste",
          [](const std::string& text) {
              return PyEvent{Event{PasteEvent{text}}};
          },
          py::arg("text"), "Build a synthetic bracketed-paste Event.");

    // make_resize(cols, rows) -> Event
    m.def("make_resize",
          [](int cols, int rows) {
              return PyEvent{Event{ResizeEvent{Columns{cols}, Rows{rows}}}};
          },
          py::arg("cols"), py::arg("rows"), "Build a synthetic resize Event.");

    m.def("key", [](const PyEvent& ev, const std::string& s) {
        if (s.size() == 1) return maya::key(ev.ev, s[0]);
        return false;
    });
    m.def("key_special", [](const PyEvent& ev, SpecialKey sk) { return maya::key(ev.ev, sk); });
    m.def("ctrl", [](const PyEvent& ev, const std::string& s) {
        return s.size() == 1 && maya::ctrl(ev.ev, s[0]);
    });
    m.def("alt", [](const PyEvent& ev, const std::string& s) {
        return s.size() == 1 && maya::alt(ev.ev, s[0]);
    });
    m.def("any_key", [](const PyEvent& ev) { return maya::any_key(ev.ev); });
    m.def("resized", [](const PyEvent& ev) { return maya::resized(ev.ev); });

    // event_char(ev) -> str | None : the typed character for a plain key press
    // (a single printable codepoint, with no Ctrl/Alt/Super held). Returns None
    // for special keys (arrows, Enter, ...) and modified combos. This is the
    // primitive that makes text entry possible from Python.
    m.def("event_char", [](const PyEvent& ev) -> py::object {
        if (auto* k = std::get_if<KeyEvent>(&ev.ev)) {
            if (k->mods.ctrl || k->mods.alt || k->mods.super_) return py::none();
            if (auto* ch = std::get_if<CharKey>(&k->key)) {
                std::string s;
                detail::encode_utf8(ch->codepoint, s);
                return py::str(s);
            }
        }
        return py::none();
    });

    // pasted(ev) -> str | None : bracketed-paste text (one event per paste).
    m.def("pasted", [](const PyEvent& ev) -> py::object {
        if (auto* p = std::get_if<PasteEvent>(&ev.ev)) return py::str(p->content);
        return py::none();
    });

    // resize_size(ev) -> (cols, rows) | None : new terminal size on a resize.
    m.def("resize_size", [](const PyEvent& ev) -> py::object {
        if (auto* r = std::get_if<ResizeEvent>(&ev.ev))
            return py::make_tuple(r->width.raw(), r->height.raw());
        return py::none();
    });

    // string_width(s) -> int : display width in terminal columns (CJK/emoji
    // count as 2). Use for manual alignment/truncation in component() callbacks.
    m.def("string_width", [](const std::string& s) { return maya::string_width(s); });

    // ── Mouse predicates ──────────────────────────────────────────────────
    // Mouse events only arrive when run(mouse=True) / App(mouse=True).
    m.def("mouse_clicked",
          [](const PyEvent& ev, MouseButton btn) { return maya::mouse_clicked(ev.ev, btn); },
          py::arg("ev"), py::arg("button") = MouseButton::Left);
    m.def("mouse_released",
          [](const PyEvent& ev, MouseButton btn) { return maya::mouse_released(ev.ev, btn); },
          py::arg("ev"), py::arg("button") = MouseButton::Left);
    m.def("mouse_moved", [](const PyEvent& ev) { return maya::mouse_moved(ev.ev); });
    m.def("scrolled_up", [](const PyEvent& ev) { return maya::scrolled_up(ev.ev); });
    m.def("scrolled_down", [](const PyEvent& ev) { return maya::scrolled_down(ev.ev); });
    m.def("is_mouse", [](const PyEvent& ev) { return maya::as_mouse(ev.ev) != nullptr; });

    // mouse_pos(ev) -> (col, row) | None   (1-based terminal cell, as the
    // SGR mouse protocol reports it; top-left is (1, 1))
    m.def("mouse_pos", [](const PyEvent& ev) -> py::object {
        auto p = maya::mouse_pos(ev.ev);
        if (!p) return py::none();
        return py::make_tuple(p->col, p->row);
    });

    // mouse_button(ev) -> MouseButton | None
    m.def("mouse_button", [](const PyEvent& ev) -> py::object {
        const MouseEvent* me = maya::as_mouse(ev.ev);
        if (!me) return py::none();
        return py::cast(me->button);
    });

    // mouse_kind(ev) -> MouseEventKind | None
    m.def("mouse_kind", [](const PyEvent& ev) -> py::object {
        const MouseEvent* me = maya::as_mouse(ev.ev);
        if (!me) return py::none();
        return py::cast(me->kind);
    });

    // scroll_handle(state, ev) -> bool
    // Route an event to a ScrollState (key arrows/pgup/home/end + mouse
    // wheel + scrollbar drag). Returns True if the event was consumed.
    // ScrollState is registered in the _widgets submodule but pybind's type
    // registry is process-wide, so we accept it as a py::object and cast.
    m.def("scroll_handle", [](py::object state, const PyEvent& ev) -> bool {
        ScrollState& s = state.cast<ScrollState&>();
        return s.handle_event(ev.ev);
    }, py::arg("state"), py::arg("ev"));

    // ── run() — simple event loop (Fullscreen / Inline) ──────────────────
    // event_fn: (Event) -> bool   (False => quit)
    // render_fn: () -> Element
    m.def("run",
          [](py::function event_fn, py::function render_fn,
             const std::string& title, bool inline_mode, bool mouse, int fps) {
              RunConfig cfg{};
              cfg.title = title;
              cfg.mouse = mouse;
              cfg.fps = fps;
              cfg.mode = inline_mode ? Mode::Inline : Mode::Fullscreen;

              // Belt-and-suspenders mouse-off: maya's Runtime emits the
              // disable on its normal+destructor paths, but a Python callback
              // that throws (KeyboardInterrupt, a bug in view()) unwinds
              // through pybind here. This guard guarantees the terminal is
              // taken out of mouse-reporting mode on EVERY exit so the user's
              // shell never echoes raw SGR mouse reports. Idempotent with
              // maya's own off-sequence (a second disable is a harmless no-op).
              struct MouseGuard {
                  bool on;
                  ~MouseGuard() {
                      if (on) {
                          // Cross-platform terminal write (POSIX fd / Win32
                          // HANDLE) via maya's platform layer — no raw
                          // ::write(1, ...), which doesn't exist on Windows.
                          (void)maya::platform::io_write_all(
                              maya::platform::stdout_handle(),
                              "\x1b[?1007l\x1b[?1006l\x1b[?1002l\x1b[?1000l");
                      }
                  }
              } mouse_guard{mouse};

              // Release the GIL for the blocking loop (Ctrl-C stays live); the
              // callbacks re-acquire it. maya's RAII restores the terminal if
              // a callback throws (incl. KeyboardInterrupt), so the user's
              // shell is never left in raw mode / alt-screen.
              py::gil_scoped_release nogil;
              maya::run(cfg,
                  [&event_fn](const Event& ev) -> bool {
                      py::gil_scoped_acquire gil;
                      if (PyErr_CheckSignals() != 0) throw py::error_already_set();
                      py::object r = event_fn(PyEvent{ev});
                      return r.is_none() ? true : r.cast<bool>();
                  },
                  [&render_fn]() -> Element {
                      py::gil_scoped_acquire gil;
                      if (PyErr_CheckSignals() != 0) throw py::error_already_set();
                      py::object r = render_fn();
                      if (!py::isinstance<Element>(r))
                          throw py::type_error(
                              "App view must return a maya Element, got "
                              + std::string(py::str(r.get_type().attr("__name__"))));
                      return r.cast<Element>();
                  });
          },
          py::arg("event_fn"), py::arg("render_fn"),
          py::arg("title") = "", py::arg("inline_mode") = false,
          py::arg("mouse") = false, py::arg("fps") = 0);

    // Widget renderers (registered last so the core types they reference in
    // default args — Style, Color, BorderStyle — already exist).
    init_widgets(m);
    init_program(m);
}
