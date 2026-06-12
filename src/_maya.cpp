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

#include "_pyevent.hpp"

#include <optional>
#include <array>
#include <unistd.h>
#include <string>
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
              for (int i = 0; i < n; ++i) {
                  const int o = i * 4;
                  kids.push_back(Element{make_styled_text(
                      flat[o].cast<std::string>(),
                      flat[o + 1].cast<long>(), flat[o + 2].cast<long>(),
                      flat[o + 3].cast<int>())});
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

              constexpr int kInitH = 120;   // covers the common < 2-screen case
              if (width != last_width || canvas.height() < kInitH) {
                  canvas.resize(width, kInitH);
                  last_width = width;
              }
              canvas.set_style_pool(&pool);
              canvas.clear();
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
              if (rows < 0) return {};

              std::string result;
              result.reserve(static_cast<std::size_t>((width + 1) * (rows + 1)));
              for (int y = 0; y <= rows; ++y) {
                  std::size_t row_start = result.size();
                  for (int x = 0; x < width; ++x) {
                      char32_t ch = canvas.get(x, y).character;
                      if (ch == U'\0') ch = U' ';
                      detail::encode_utf8(ch, result);
                  }
                  std::size_t end = result.size();
                  while (end > row_start && result[end - 1] == ' ') --end;
                  result.resize(end);
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

    // ── Event (opaque) + predicates ───────────────────────────────────────
    // maya's Event is std::variant<KeyEvent, MouseEvent, ...>. pybind11/stl.h
    // installs a variant caster that would try to convert the active member
    // to Python — but those member types aren't registered, so the cast
    // fails. Python never inspects the event directly (it only goes back
    // through the key()/ctrl()/... predicates below), so wrap it in an opaque
    // struct that pybind treats as a plain registered class, not a variant.
    py::class_<PyEvent>(m, "Event");
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
                          const char off[] =
                              "\x1b[?1007l\x1b[?1006l\x1b[?1002l\x1b[?1000l";
                          ssize_t r = ::write(1, off, sizeof(off) - 1);
                          (void)r;
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
