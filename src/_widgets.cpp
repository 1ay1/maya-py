// _widgets.cpp — pybind11 bindings for maya's widget library.
//
// maya ships ~90 widget renderers under <maya/widget/*.hpp> that are NOT
// pulled in by <maya/maya.hpp>. Each is a small class built from data + a
// Config and convertible to Element. We bind the presentational (render-only)
// ones as Python factory functions: pass simple Python values, get an Element
// back — the SAME Element maya's own renderers produce.
//
// Interactive controls (Input, TextArea, ...) ALSO cross into Python: we host
// the stateful C++ widget by value, keep its Signals/FocusNode entirely on the
// C++ side, and expose only value/handle(event)/Element to Python — exactly how
// ScrollState (below) already works. See PyInput for the pattern; App.focus()
// routes events to the focused widget. (Earlier this file claimed interactive
// widgets "can't cross into Python" — that was never true.)

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <maya/style/style.hpp>
#include <maya/style/color.hpp>
#include <maya/element/element.hpp>
#include <maya/element/builder.hpp>

#include <maya/widget/sparkline.hpp>
#include <maya/widget/gauge.hpp>
#include <maya/widget/progress.hpp>
#include <maya/widget/badge.hpp>
#include <maya/widget/divider.hpp>
#include <maya/widget/spinner.hpp>
#include <maya/widget/table.hpp>
#include <maya/widget/callout.hpp>
#include <maya/widget/status_banner.hpp>
#include <maya/widget/breadcrumb.hpp>
#include <maya/widget/tabs.hpp>
#include <maya/widget/bar_chart.hpp>
#include <maya/widget/gradient.hpp>
#include <maya/widget/heatmap.hpp>
#include <maya/widget/scrollbar.hpp>
#include <maya/core/scroll_state.hpp>

#include <maya/widget/checkbox.hpp>
#include <maya/widget/radio.hpp>
#include <maya/widget/slider.hpp>
#include <maya/widget/select.hpp>
#include <maya/widget/button.hpp>
#include <maya/widget/calendar.hpp>
#include <maya/widget/line_chart.hpp>
#include <maya/widget/link.hpp>
#include <maya/widget/key_help.hpp>
#include <maya/widget/timeline.hpp>
#include <maya/widget/tree.hpp>
#include <maya/widget/list.hpp>
#include <maya/widget/menu.hpp>
#include <maya/widget/disclosure.hpp>
#include <maya/widget/toast.hpp>
#include <maya/widget/todo_list.hpp>
#include <maya/widget/title_chip.hpp>
#include <maya/widget/model_badge.hpp>
#include <maya/widget/file_ref.hpp>
#include <maya/widget/inline_diff.hpp>
#include <maya/widget/flame_chart.hpp>
#include <maya/widget/waterfall.hpp>
#include <maya/widget/token_stream.hpp>
#include <maya/widget/thinking.hpp>
#include <maya/widget/markdown.hpp>
#include <maya/widget/image.hpp>
#include <maya/widget/canvas.hpp>
#include <maya/widget/picker.hpp>
#include <maya/widget/plan_view.hpp>  // TaskStatus
#include <maya/widget/input.hpp>      // interactive text input / textarea

#include <maya/widget/popup.hpp>
#include <maya/widget/overlay.hpp>
#include <maya/widget/message.hpp>
#include <maya/widget/system_banner.hpp>
#include <maya/widget/phase_chip.hpp>
#include <maya/widget/context_gauge.hpp>
#include <maya/widget/context_window.hpp>
#include <maya/widget/diff_view.hpp>
#include <maya/widget/tool_call.hpp>
#include <maya/widget/git_graph.hpp>
#include <maya/widget/git_status.hpp>
#include <maya/widget/shortcut_row.hpp>
#include <maya/widget/error_block.hpp>
#include <maya/widget/modal.hpp>
#include <maya/widget/log_viewer.hpp>
#include <maya/widget/command_palette.hpp>
#include <maya/widget/activity_indicator.hpp>

#include "_pyevent.hpp"

#include <optional>
#include <string>
#include <variant>
#include <vector>
#include <functional>
#include <cmath>
#include <algorithm>

namespace py = pybind11;
using namespace maya;

// ── Interactive text input ──────────────────────────────────────────────────
// maya's Input<Cfg> is a real stateful widget (cursor, UTF-8 editing, history,
// password masking) that participates in the runtime via Signals + a FocusNode.
// The OLD binding claimed interactive controls "can't cross into Python" — but
// ScrollState (bound below) already disproves that: the signals/focus stay
// C++-side, only value/handle/Element cross. PyInput hosts the widget the same
// way: feed it events with handle(), read .value, drop .element() in the view.
//
// Cfg is a compile-time template parameter, so we hold a variant over the three
// useful instantiations (plain / password / multiline) and dispatch with visit.
struct PyInput {
    using Plain = Input<InputConfig{}>;
    using Pass  = Input<InputConfig{.password = true}>;
    using Multi = Input<InputConfig{.multiline = true}>;

    std::variant<Plain, Pass, Multi> in_;
    py::function on_submit_;
    py::function on_change_;

    static std::variant<Plain, Pass, Multi> make(bool password, bool multiline) {
        if (password) return Pass{};
        if (multiline) return Multi{};
        return Plain{};
    }

    PyInput(bool password, bool multiline) : in_(make(password, multiline)) {
        std::visit([&](auto& i) {
            // Force-focus: we drive a single widget directly rather than via a
            // FocusScope, so its handle() (which early-returns when unfocused)
            // always processes keys. App.focus() toggles this for multi-widget
            // Tab navigation.
            i.focus_node().focused.set(true);
            i.on_submit([this](std::string_view sv) { fire(on_submit_, sv); });
            i.on_change([this](std::string_view sv) { fire(on_change_, sv); });
        }, in_);
    }

    static void fire(py::function& f, std::string_view sv) {
        if (f) { py::gil_scoped_acquire g; f(py::str(std::string(sv))); }
    }

    bool handle(const PyEvent& ev) {
        if (auto* ke = std::get_if<KeyEvent>(&ev.ev))
            return std::visit([&](auto& i) { return i.handle(*ke); }, in_);
        if (auto* pe = std::get_if<PasteEvent>(&ev.ev)) {
            std::visit([&](auto& i) { i.handle_paste(*pe); }, in_);
            return true;
        }
        return false;
    }

    std::string value() const {
        return std::visit([](auto& i) -> std::string { return i.value()(); }, in_);
    }
    void set_value(const std::string& v) {
        std::visit([&](auto& i) { i.set_value(v); }, in_);
    }
    void clear() { std::visit([](auto& i) { i.clear(); }, in_); }
    void set_placeholder(const std::string& p) {
        std::visit([&](auto& i) { i.set_placeholder(p); }, in_);
    }
    bool focused() const {
        return std::visit([](auto& i) { return i.focus_node().focused(); }, in_);
    }
    void set_focused(bool f) {
        std::visit([&](auto& i) { i.focus_node().focused.set(f); }, in_);
    }
    Element build() const {
        return std::visit([](auto& i) -> Element { return i.build(); }, in_);
    }
};

// ── PyCanvas — a native char + per-cell-fg drawing grid ─────────────────────
// The dashboard / doom / fps examples each hand-rolled a software renderer in
// Python: a `Cells` grid, `braille_plot`, `braille_line`, `draw_box`, and a
// `to_element()` that emitted one styled row per line. That is precisely what
// maya's renderer already does in C++ — and doing it per-pixel in Python both
// bloats the example and dominates the frame budget. PyCanvas hosts that grid
// in C++: set a cell, accumulate braille dots, stroke a box, then build() once
// into one TextElement-per-row (each cell its own StyledRun) — zero per-cell
// boundary crossings, and faithful to maya's own PixelCanvas::build shape.
struct PyCanvas {
    int w_ = 0, h_ = 0;
    int32_t default_fg_ = -1;          // packed 0xRRGGBB, -1 = inherit
    int32_t bg_ = -1;                  // packed 0xRRGGBB applied to every cell
    std::vector<char32_t> ch_;         // w_*h_ glyphs (default U' ')
    std::vector<int32_t>  fg_;         // w_*h_ packed fg, -1 = default_fg_

    static constexpr uint8_t kBrailleDot[8] =
        {0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80};

    PyCanvas(int w, int h, int32_t bg, int32_t default_fg)
        : w_(w < 0 ? 0 : w), h_(h < 0 ? 0 : h),
          default_fg_(default_fg), bg_(bg),
          ch_(static_cast<size_t>(w_) * h_, U' '),
          fg_(static_cast<size_t>(w_) * h_, -1) {}

    MAYA_ALWAYS_INLINE bool in_bounds(int x, int y) const noexcept {
        return static_cast<unsigned>(x) < static_cast<unsigned>(w_)
            && static_cast<unsigned>(y) < static_cast<unsigned>(h_);
    }

    void clear() {
        std::fill(ch_.begin(), ch_.end(), U' ');
        std::fill(fg_.begin(), fg_.end(), -1);
    }

    void fill_bg(int32_t bg) { bg_ = bg; }

    MAYA_ALWAYS_INLINE void set_cp(int x, int y, char32_t c, int32_t fg) {
        if (!in_bounds(x, y)) return;
        size_t i = static_cast<size_t>(y) * w_ + x;
        ch_[i] = c;
        fg_[i] = fg;
    }

    static char32_t first_cp(const std::string& s) {
        if (s.empty()) return U' ';
        const unsigned char* p = reinterpret_cast<const unsigned char*>(s.data());
        unsigned char b = *p; char32_t cp; int len;
        if (b < 0x80) { cp = b; len = 1; }
        else if ((b >> 5) == 0x6) { cp = b & 0x1F; len = 2; }
        else if ((b >> 4) == 0xE) { cp = b & 0x0F; len = 3; }
        else if ((b >> 3) == 0x1E){ cp = b & 0x07; len = 4; }
        else { return b; }
        for (int k = 1; k < len && k < (int)s.size(); ++k)
            cp = (cp << 6) | (p[k] & 0x3F);
        return cp;
    }

    void set(int x, int y, const std::string& ch, int32_t fg) {
        set_cp(x, y, first_cp(ch), fg);
    }

    char32_t get_char(int x, int y) const {
        if (!in_bounds(x, y)) return U' ';
        return ch_[static_cast<size_t>(y) * w_ + x];
    }

    // Write a UTF-8 string left-to-right from (x, y), one codepoint per cell.
    void write(int x, int y, const std::string& text, int32_t fg) {
        const unsigned char* p = reinterpret_cast<const unsigned char*>(text.data());
        const unsigned char* end = p + text.size();
        int cx = x;
        while (p < end) {
            char32_t cp; int len;
            unsigned char b = *p;
            if (b < 0x80)        { cp = b; len = 1; }
            else if ((b >> 5) == 0x6) { cp = b & 0x1F; len = 2; }
            else if ((b >> 4) == 0xE) { cp = b & 0x0F; len = 3; }
            else if ((b >> 3) == 0x1E){ cp = b & 0x07; len = 4; }
            else { cp = b; len = 1; }
            for (int k = 1; k < len && p + k < end; ++k)
                cp = (cp << 6) | (p[k] & 0x3F);
            set_cp(cx++, y, cp, fg);
            p += len;
        }
    }

    void hline(int x, int y, int n, const std::string& ch, int32_t fg) {
        char32_t c = first_cp(ch);
        for (int i = 0; i < n; ++i) set_cp(x + i, y, c, fg);
    }
    void vline(int x, int y, int n, const std::string& ch, int32_t fg) {
        char32_t c = first_cp(ch);
        for (int i = 0; i < n; ++i) set_cp(x, y + i, c, fg);
    }

    void rect_fill(int x, int y, int rw, int rh, const std::string& ch, int32_t fg) {
        char32_t c = first_cp(ch);
        for (int j = 0; j < rh; ++j)
            for (int i = 0; i < rw; ++i)
                set_cp(x + i, y + j, c, fg);
    }

    // A rounded box with an optional ┤title├ on the top edge.
    void box(int x, int y, int bw, int bh, int32_t fg, const std::string& title) {
        if (bw < 2 || bh < 2) return;
        set_cp(x, y, U'\u256D', fg);
        set_cp(x + bw - 1, y, U'\u256E', fg);
        set_cp(x, y + bh - 1, U'\u2570', fg);
        set_cp(x + bw - 1, y + bh - 1, U'\u256F', fg);
        for (int i = 1; i < bw - 1; ++i) {
            set_cp(x + i, y, U'\u2500', fg);
            set_cp(x + i, y + bh - 1, U'\u2500', fg);
        }
        for (int j = 1; j < bh - 1; ++j) {
            set_cp(x, y + j, U'\u2502', fg);
            set_cp(x + bw - 1, y + j, U'\u2502', fg);
        }
        if (!title.empty()) {
            int tx = x + 2;
            set_cp(tx - 1, y, U'\u2524', fg);
            write(tx, y, title, fg);
            int n = 0;
            for (unsigned char b : title)
                if ((b & 0xC0) != 0x80) ++n;
            set_cp(tx + n, y, U'\u251C', fg);
        }
    }

    // Accumulate one braille dot at pixel (px, py) within a bw×bh cell region
    // anchored at (ox, oy). Pixel space is bw*2 wide, bh*4 tall.
    MAYA_ALWAYS_INLINE void braille_plot(int ox, int oy, int bw, int bh,
                                         int px, int py, int32_t fg) {
        int bx = px >> 1, by = py >> 2;
        if (bx < 0 || bx >= bw || by < 0 || by >= bh) return;
        int dcol = px & 1, drow = py & 3;
        int dot_idx = (drow < 3) ? (drow + dcol * 3) : (6 + dcol);
        int cx = ox + bx, cy = oy + by;
        if (!in_bounds(cx, cy)) return;
        size_t i = static_cast<size_t>(cy) * w_ + cx;
        char32_t cur = ch_[i];
        uint32_t dots = (cur >= 0x2800 && cur <= 0x28FF) ? (cur - 0x2800) : 0;
        dots |= kBrailleDot[dot_idx];
        ch_[i] = 0x2800 + dots;
        fg_[i] = fg;
    }

    void braille_line(int ox, int oy, int bw, int bh,
                      int x0, int y0, int x1, int y1, int32_t fg) {
        int dx = std::abs(x1 - x0), dy = std::abs(y1 - y0);
        int steps = std::max(dx, dy);
        if (steps == 0) { braille_plot(ox, oy, bw, bh, x0, y0, fg); return; }
        for (int i = 0; i <= steps; ++i) {
            int px = x0 + (x1 - x0) * i / steps;
            int py = y0 + (y1 - y0) * i / steps;
            braille_plot(ox, oy, bw, bh, px, py, fg);
        }
    }

    // ── Batch primitives — collapse a whole per-pixel loop into ONE crossing.
    // These are the difference between "native canvas" and "native canvas that
    // is actually fast": plotting a 2000-dot frame one Python call at a time is
    // 2000 boundary crossings; these do it in a handful.

    // Plot a flat [px0, py0, px1, py1, ...] pixel list, all in one colour.
    void plot_seq(int ox, int oy, int bw, int bh,
                  const std::vector<int>& pts, int32_t fg) {
        size_t n = pts.size() & ~size_t{1};
        for (size_t i = 0; i < n; i += 2)
            braille_plot(ox, oy, bw, bh, pts[i], pts[i + 1], fg);
    }

    // Connect a flat [px0,py0, px1,py1, ...] vertex list with braille lines.
    void polyline(int ox, int oy, int bw, int bh,
                  const std::vector<int>& pts, int32_t fg) {
        size_t n = pts.size() & ~size_t{1};
        if (n < 2) return;
        if (n == 2) { braille_plot(ox, oy, bw, bh, pts[0], pts[1], fg); return; }
        for (size_t i = 2; i < n; i += 2)
            braille_line(ox, oy, bw, bh,
                         pts[i - 2], pts[i - 1], pts[i], pts[i + 1], fg);
    }

    // Per-column filled area chart from a sampled curve. `ys` holds one target
    // pixel-y per pixel-column (0..pw-1); the column between ys[x] and
    // `baseline_py` is flooded. If `ramp` is non-empty, each cell is shaded by
    // its distance from the curve through the ramp; else `fg` is used flat.
    // `line_fg` (>=0) overdraws the curve itself (optionally `thick` px wide).
    void fill_curve(int ox, int oy, int bw, int bh,
                    const std::vector<int>& ys, int baseline_py,
                    int32_t fg, const std::vector<int32_t>& ramp,
                    int32_t line_fg, int thick) {
        int pw = bw * 2, ph = bh * 4;
        int n = static_cast<int>(ys.size());
        if (n > pw) n = pw;
        int nshade = static_cast<int>(ramp.size());
        // Stroke-only mode: no ramp AND no flat fill colour -> don't flood the
        // column, just draw the curve (used by Pen.curve()).
        const bool do_fill = (nshade > 0) || (fg >= 0);
        for (int px = 0; px < n; ++px) {
            int py = ys[px];
            if (py < 0) py = 0; else if (py >= ph) py = ph - 1;
            if (do_fill) {
                int top = py < baseline_py ? py : baseline_py;
                int bot = py < baseline_py ? baseline_py : py;
                int span = bot - top; if (span < 1) span = 1;
                for (int fy = top; fy <= bot; ++fy) {
                    int32_t c;
                    if (nshade) {
                        int si = (std::abs(fy - py) * (nshade - 1)) / span;
                        if (si >= nshade) si = nshade - 1;
                        c = ramp[si];
                    } else c = fg;
                    braille_plot(ox, oy, bw, bh, px, fy, c);
                }
            }
            if (line_fg >= 0) {
                braille_plot(ox, oy, bw, bh, px, py, line_fg);
                for (int k = 1; k < thick; ++k) {
                    if (py - k >= 0)  braille_plot(ox, oy, bw, bh, px, py - k, line_fg);
                    if (py + k < ph)  braille_plot(ox, oy, bw, bh, px, py + k, line_fg);
                }
            }
        }
    }

    // An ellipse outline centred at pixel (cx, cy).
    void ring(int ox, int oy, int bw, int bh,
              int cx, int cy, double rx, double ry, int32_t fg, int steps) {
        if (steps <= 0) steps = std::max(8, int((rx + ry) * 1.5));
        for (int s = 0; s < steps; ++s) {
            double a = 6.283185307179586 * s / steps;
            braille_plot(ox, oy, bw, bh,
                         int(cx + std::cos(a) * rx),
                         int(cy + std::sin(a) * ry), fg);
        }
    }

    // A radial sweep line from centre outward at angle `a`, `segs` segments
    // long, scaled to (rx, ry). Used for radar beams.
    void ray(int ox, int oy, int bw, int bh, int cx, int cy,
             double a, double rx, double ry, int from_seg, int to_seg,
             int32_t fg) {
        double ca = std::cos(a), sa = std::sin(a);
        int n = std::max(1, to_seg);
        for (int d = from_seg; d < to_seg; ++d) {
            double f = double(d) / n;
            braille_plot(ox, oy, bw, bh,
                         int(cx + ca * rx * f), int(cy + sa * ry * f), fg);
        }
    }

    static void encode_utf8(std::string& out, char32_t cp) {
        if (cp < 0x80) out.push_back(static_cast<char>(cp));
        else if (cp < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else if (cp < 0x10000) {
            out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
        }
    }

    // Build one Element: a vstack of rows, each a single TextElement whose
    // per-cell glyphs carry their own StyledRun (fg + the canvas bg).
    Element build() const {
        if (w_ == 0 || h_ == 0) return dsl::nothing();
        Color bg = (bg_ >= 0)
            ? Color::rgb((bg_ >> 16) & 0xFF, (bg_ >> 8) & 0xFF, bg_ & 0xFF)
            : Color{};
        bool has_bg = bg_ >= 0;
        std::vector<Element> rows;
        rows.reserve(static_cast<size_t>(h_));
        for (int y = 0; y < h_; ++y) {
            std::string content;
            content.reserve(static_cast<size_t>(w_) * 3);
            std::vector<StyledRun> runs;
            runs.reserve(static_cast<size_t>(w_));
            const char32_t* cr = &ch_[static_cast<size_t>(y) * w_];
            const int32_t*  fr = &fg_[static_cast<size_t>(y) * w_];
            for (int x = 0; x < w_; ++x) {
                size_t start = content.size();
                encode_utf8(content, cr[x]);
                int32_t f = fr[x] < 0 ? default_fg_ : fr[x];
                Style s;
                if (f >= 0)
                    s = s.with_fg(Color::rgb((f >> 16) & 0xFF, (f >> 8) & 0xFF, f & 0xFF));
                if (has_bg) s = s.with_bg(bg);
                runs.push_back(StyledRun{start, content.size() - start, s});
            }
            rows.push_back(Element{TextElement{
                .content = std::move(content),
                .style = {},
                .wrap = TextWrap::NoWrap,
                .runs = std::move(runs),
            }});
        }
        return dsl::v(std::move(rows)).build();
    }
};

void init_widgets(py::module_& m) {
    auto w = m.def_submodule("_widgets", "maya widget renderers");

    // ── Input — interactive text field (single-line / password / multiline) ──
    // The first real interactive widget hosted in Python: feed it App events
    // with handle(), read .value, place .element() in the view.
    py::class_<PyInput>(w, "Input")
        .def(py::init<bool, bool>(),
             py::arg("password") = false, py::arg("multiline") = false)
        .def("handle", &PyInput::handle, py::arg("event"),
             "Feed an App event (key or paste). Returns True if consumed.")
        .def("clear", &PyInput::clear)
        .def("element", &PyInput::build, "Render to an Element (box + cursor).")
        .def("set_placeholder", &PyInput::set_placeholder, py::arg("text"))
        .def("on_submit",
             [](PyInput& self, py::function f) { self.on_submit_ = std::move(f); },
             py::arg("fn"), "Call fn(text) when Enter is pressed.")
        .def("on_change",
             [](PyInput& self, py::function f) { self.on_change_ = std::move(f); },
             py::arg("fn"), "Call fn(text) on every edit.")
        .def_property("value", &PyInput::value, &PyInput::set_value)
        .def_property("focused", &PyInput::focused, &PyInput::set_focused);

    // ── Grid — a native braille/char drawing grid ──────────────────────────
    // All colours are packed 0xRRGGBB ints (or -1 = inherit) so per-cell draws
    // never touch the Color type or cross a boundary; the Python wrapper packs
    // names/tuples/#hex once. build() emits one TextElement per row.
    py::class_<PyCanvas>(w, "Grid")
        .def(py::init<int, int, int32_t, int32_t>(),
             py::arg("width"), py::arg("height"),
             py::arg("bg") = -1, py::arg("default_fg") = -1)
        .def_readonly("width", &PyCanvas::w_)
        .def_readonly("height", &PyCanvas::h_)
        .def("clear", &PyCanvas::clear)
        .def("fill_bg", &PyCanvas::fill_bg, py::arg("bg"))
        .def("set", &PyCanvas::set,
             py::arg("x"), py::arg("y"), py::arg("ch"), py::arg("fg") = -1)
        .def("get_char",
             [](const PyCanvas& c, int x, int y) {
                 std::string out; PyCanvas::encode_utf8(out, c.get_char(x, y));
                 return out;
             }, py::arg("x"), py::arg("y"))
        .def("write", &PyCanvas::write,
             py::arg("x"), py::arg("y"), py::arg("text"), py::arg("fg") = -1)
        .def("hline", &PyCanvas::hline,
             py::arg("x"), py::arg("y"), py::arg("n"),
             py::arg("ch") = "\u2500", py::arg("fg") = -1)
        .def("vline", &PyCanvas::vline,
             py::arg("x"), py::arg("y"), py::arg("n"),
             py::arg("ch") = "\u2502", py::arg("fg") = -1)
        .def("rect_fill", &PyCanvas::rect_fill,
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"),
             py::arg("ch") = " ", py::arg("fg") = -1)
        .def("box", &PyCanvas::box,
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"),
             py::arg("fg") = -1, py::arg("title") = "")
        .def("plot", &PyCanvas::braille_plot,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("px"), py::arg("py"), py::arg("fg") = -1)
        .def("line", &PyCanvas::braille_line,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("x0"), py::arg("y0"), py::arg("x1"), py::arg("y1"),
             py::arg("fg") = -1)
        .def("plot_seq", &PyCanvas::plot_seq,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("pts"), py::arg("fg") = -1)
        .def("polyline", &PyCanvas::polyline,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("pts"), py::arg("fg") = -1)
        .def("fill_curve", &PyCanvas::fill_curve,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("ys"), py::arg("baseline_py"), py::arg("fg") = -1,
             py::arg("ramp") = std::vector<int32_t>{},
             py::arg("line_fg") = -1, py::arg("thick") = 1)
        .def("ring", &PyCanvas::ring,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("cx"), py::arg("cy"), py::arg("rx"), py::arg("ry"),
             py::arg("fg") = -1, py::arg("steps") = 0)
        .def("ray", &PyCanvas::ray,
             py::arg("ox"), py::arg("oy"), py::arg("bw"), py::arg("bh"),
             py::arg("cx"), py::arg("cy"), py::arg("a"), py::arg("rx"),
             py::arg("ry"), py::arg("from_seg"), py::arg("to_seg"),
             py::arg("fg") = -1)
        .def("element", &PyCanvas::build, "Build the grid into an Element.");

    // ── enums ───────────────────────────────────────────────────────────
    py::enum_<GaugeStyle>(w, "GaugeStyle")
        .value("Arc", GaugeStyle::Arc)
        .value("Bar", GaugeStyle::Bar);

    py::enum_<ColumnAlign>(w, "ColumnAlign")
        .value("Left", ColumnAlign::Left)
        .value("Center", ColumnAlign::Center)
        .value("Right", ColumnAlign::Right);

    py::enum_<ButtonVariant>(w, "ButtonVariant")
        .value("Default", ButtonVariant::Default)
        .value("Primary", ButtonVariant::Primary)
        .value("Danger", ButtonVariant::Danger)
        .value("Ghost", ButtonVariant::Ghost);

    py::enum_<TaskStatus>(w, "TaskStatus")
        .value("Pending", TaskStatus::Pending)
        .value("InProgress", TaskStatus::InProgress)
        .value("Completed", TaskStatus::Completed);

    py::enum_<ToastLevel>(w, "ToastLevel")
        .value("Info", ToastLevel::Info)
        .value("Success", ToastLevel::Success)
        .value("Warning", ToastLevel::Warning)
        .value("Error", ToastLevel::Error);

    py::enum_<TodoItemStatus>(w, "TodoItemStatus")
        .value("Pending", TodoItemStatus::Pending)
        .value("InProgress", TodoItemStatus::InProgress)
        .value("Completed", TodoItemStatus::Completed);

    py::enum_<TodoListStatus>(w, "TodoListStatus")
        .value("Pending", TodoListStatus::Pending)
        .value("Running", TodoListStatus::Running)
        .value("Done", TodoListStatus::Done)
        .value("Failed", TodoListStatus::Failed);

    // ── sparkline(data, label, color, show_min_max, show_last) ──────────
    w.def("sparkline",
          [](std::vector<float> data, std::string label, std::optional<Color> color,
             bool show_min_max, bool show_last, std::optional<float> range_min,
             std::optional<float> range_max) {
              SparklineConfig cfg{};
              if (color) cfg.color = *color;
              cfg.show_min_max = show_min_max;
              cfg.show_last = show_last;
              Sparkline s{std::move(data), cfg};
              if (!label.empty()) s.set_label(label);
              if (range_min) s.set_min(*range_min);
              if (range_max) s.set_max(*range_max);
              return static_cast<Element>(s);
          },
          py::arg("data"), py::arg("label") = "",
          py::arg("color") = std::nullopt,
          py::arg("show_min_max") = false, py::arg("show_last") = false,
          py::arg("range_min") = std::nullopt, py::arg("range_max") = std::nullopt);

    // ── gauge(value, label, color, style) ───────────────────────────────
    w.def("gauge",
          [](float value, std::string label, std::optional<Color> color, GaugeStyle style) {
              Gauge g{value, std::move(label), color.value_or(Color::blue()), style};
              return static_cast<Element>(g);
          },
          py::arg("value"), py::arg("label") = "",
          py::arg("color") = std::nullopt, py::arg("style") = GaugeStyle::Arc);

    // ── progress(value, label, width, fill, track, show_track, show_pct) ─
    w.def("progress",
          [](float value, std::string label, int width,
             std::optional<Color> fill, std::optional<Color> track,
             bool show_track, bool show_percentage) {
              ProgressConfig cfg{};
              cfg.width = width;
              if (fill)  cfg.fill_color = *fill;
              if (track) cfg.bg_color = *track;
              cfg.show_track = show_track;
              cfg.show_percentage = show_percentage;
              ProgressBar p{cfg};
              p.set(value);
              if (!label.empty()) p.set_label(label);
              return static_cast<Element>(p);
          },
          py::arg("value"), py::arg("label") = "", py::arg("width") = 0,
          py::arg("fill") = std::nullopt, py::arg("track") = std::nullopt,
          py::arg("show_track") = true, py::arg("show_percentage") = true);

    // ── badge(label, style, kind) ───────────────────────────────────────
    w.def("badge",
          [](std::string label, std::optional<Style> style, const std::string& kind) {
              if (kind == "success") return static_cast<Element>(Badge::success(label));
              if (kind == "error")   return static_cast<Element>(Badge::error(label));
              if (kind == "warning") return static_cast<Element>(Badge::warning(label));
              if (kind == "info")    return static_cast<Element>(Badge::info(label));
              if (kind == "tool")    return static_cast<Element>(Badge::tool(label));
              Badge::Config c{};
              if (style) c.style = *style;
              return static_cast<Element>(Badge{std::move(label), std::move(c)});
          },
          py::arg("label"), py::arg("style") = std::nullopt, py::arg("kind") = "");

    // ── divider(label, line, line_color) ────────────────────────────────
    w.def("divider",
          [](std::string label, BorderStyle line, std::optional<Color> line_color) {
              DividerConfig cfg{};
              cfg.line = line;
              if (line_color) cfg.line_style = Style{}.with_fg(*line_color);
              Divider d{label, cfg};
              return static_cast<Element>(d);
          },
          py::arg("label") = "", py::arg("line") = BorderStyle::Single,
          py::arg("line_color") = std::nullopt);

    // ── spinner(style) ──────────────────────────────────────────────────
    w.def("spinner",
          [](std::optional<Style> style) {
              Spinner s = style ? Spinner{*style} : Spinner{};
              return static_cast<Element>(s);
          },
          py::arg("style") = std::nullopt);

    // ── table(columns, rows, **opts) ────────────────────────────────────
    // columns: list of str (header) OR (header, width, align) tuples.
    w.def("table",
          [](const py::list& columns, std::vector<std::vector<std::string>> rows,
             bool stripe, bool bordered, const std::string& title, int cell_padding) {
              std::vector<ColumnDef> cols;
              for (const auto& col : columns) {
                  ColumnDef cd{};
                  if (py::isinstance<py::str>(col)) {
                      cd.header = col.cast<std::string>();
                  } else {
                      auto t = col.cast<py::sequence>();
                      cd.header = t[0].cast<std::string>();
                      if (t.size() > 1) cd.width = t[1].cast<int>();
                      if (t.size() > 2) cd.align = t[2].cast<ColumnAlign>();
                  }
                  cols.push_back(std::move(cd));
              }
              TableConfig cfg{};
              cfg.stripe_rows = stripe;
              cfg.show_border = bordered;
              cfg.title = title;
              cfg.cell_padding = cell_padding;
              Table tbl{std::move(cols), cfg};
              tbl.set_rows(std::move(rows));
              return static_cast<Element>(tbl);
          },
          py::arg("columns"), py::arg("rows"),
          py::arg("stripe") = true, py::arg("bordered") = false,
          py::arg("title") = "", py::arg("cell_padding") = 1);

    // ── callout(title, body, kind) ──────────────────────────────────────
    w.def("callout",
          [](std::string title, std::string body, const std::string& kind) {
              Severity sev = Severity::Info;
              if (kind == "success") sev = Severity::Success;
              else if (kind == "warning") sev = Severity::Warning;
              else if (kind == "error") sev = Severity::Error;
              return static_cast<Element>(Callout{sev, std::move(title), std::move(body)});
          },
          py::arg("title"), py::arg("body") = "", py::arg("kind") = "info");

    // ── status_banner(text, kind) ───────────────────────────────────────
    w.def("status_banner",
          [](std::string text, const std::string& kind) {
              StatusBanner::Config c{};
              c.text = std::move(text);
              if (kind == "warning" || kind == "warn") c.kind = StatusBanner::Kind::Warn;
              else if (kind == "error") c.kind = StatusBanner::Kind::Error;
              return static_cast<Element>(StatusBanner{std::move(c)});
          },
          py::arg("text"), py::arg("kind") = "info");

    // ── error_block(error_type, message, detail, hint, severity, trace) ─
    // A boxed error panel: severity icon + type + message, optional detail/
    // hint lines and a stack trace. severity: "error"|"warning"|"info".
    w.def("error_block",
          [](std::string error_type, std::string message, std::string detail,
             std::string hint, const std::string& severity,
             std::vector<std::string> trace) {
              ErrorBlock e{std::move(error_type), std::move(message)};
              if (!detail.empty()) e.set_detail(std::move(detail));
              if (!hint.empty())   e.set_hint(std::move(hint));
              ErrorSeverity sev = ErrorSeverity::Error;
              if (severity == "warning" || severity == "warn") sev = ErrorSeverity::Warning;
              else if (severity == "info") sev = ErrorSeverity::Info;
              e.set_severity(sev);
              if (!trace.empty()) {
                  e.set_show_trace(true);
                  for (auto& line : trace) e.add_trace_line(std::move(line));
              }
              return static_cast<Element>(e);
          },
          py::arg("error_type"), py::arg("message") = "",
          py::arg("detail") = "", py::arg("hint") = "",
          py::arg("severity") = "error",
          py::arg("trace") = std::vector<std::string>{});

    // ── modal(title, content, buttons, focused) ─────────────────────────
    // A centered dialog: title bar, body element, footer of action buttons.
    // buttons: list of str, or (label, variant) where variant is
    // "default"|"primary"|"danger". `focused` highlights that button index.
    w.def("modal",
          [](std::string title, std::optional<Element> content,
             const py::list& buttons, int focused) {
              std::vector<ModalButton> bs;
              for (const auto& item : buttons) {
                  ModalButton b{};
                  if (py::isinstance<py::str>(item)) {
                      b.label = item.cast<std::string>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      b.label = t[0].cast<std::string>();
                      if (py::len(t) > 1) {
                          std::string v = t[1].cast<std::string>();
                          if (v == "primary") b.variant = ModalButton::Primary;
                          else if (v == "danger") b.variant = ModalButton::Danger;
                      }
                  }
                  bs.push_back(std::move(b));
              }
              Element body = content ? *content : Element{TextElement{.content = ""}};
              Modal m{std::move(title), std::move(body), std::move(bs)};
              m.show();
              // Highlight a button by faking focus + setting the index signal.
              m.focus_node().focused.set(true);
              if (focused > 0)
                  const_cast<Signal<int>&>(m.focused_button()).set(focused);
              return static_cast<Element>(m);
          },
          py::arg("title"), py::arg("content") = std::nullopt,
          py::arg("buttons") = py::list{}, py::arg("focused") = 0);

    // ── log_viewer(entries, visible, level) ─────────────────────────────
    // A scrolling log panel. entries: list of (timestamp, message, level) or
    // dicts {timestamp, message, level}. level: "debug"|"info"|"warn"|"error".
    w.def("log_viewer",
          [](const py::list& entries, int visible, int scroll) {
              auto parse_lvl = [](const std::string& s) {
                  if (s == "debug") return LogLevel::Debug;
                  if (s == "warn" || s == "warning") return LogLevel::Warn;
                  if (s == "error") return LogLevel::Error;
                  return LogLevel::Info;
              };
              LogViewer lv{};
              if (visible > 0) lv.set_visible(visible);
              for (const auto& item : entries) {
                  LogEntry e{};
                  if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("timestamp")) e.timestamp = d["timestamp"].cast<std::string>();
                      if (d.contains("message"))   e.message = d["message"].cast<std::string>();
                      if (d.contains("level"))     e.level = parse_lvl(d["level"].cast<std::string>());
                  } else {
                      auto t = item.cast<py::sequence>();
                      e.timestamp = t[0].cast<std::string>();
                      if (py::len(t) > 1) e.message = t[1].cast<std::string>();
                      if (py::len(t) > 2) e.level = parse_lvl(t[2].cast<std::string>());
                  }
                  lv.push(std::move(e));
              }
              return static_cast<Element>(lv);
          },
          py::arg("entries"), py::arg("visible") = 0, py::arg("scroll") = 0);

    // ── command_palette(commands, cursor, query) ────────────────────────
    // A fuzzy command menu. commands: list of (name, description, shortcut)
    // or dicts {name, description, shortcut}.
    w.def("command_palette",
          [](const py::list& commands, int cursor) {
              std::vector<Command> cs;
              for (const auto& item : commands) {
                  Command c{};
                  if (py::isinstance<py::str>(item)) {
                      c.name = item.cast<std::string>();
                  } else if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("name"))        c.name = d["name"].cast<std::string>();
                      if (d.contains("description")) c.description = d["description"].cast<std::string>();
                      if (d.contains("shortcut"))    c.shortcut = d["shortcut"].cast<std::string>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      c.name = t[0].cast<std::string>();
                      if (py::len(t) > 1) c.description = t[1].cast<std::string>();
                      if (py::len(t) > 2) c.shortcut = t[2].cast<std::string>();
                  }
                  cs.push_back(std::move(c));
              }
              CommandPalette p{std::move(cs)};
              p.show();
              if (cursor > 0) const_cast<Signal<int>&>(p.cursor()).set(cursor);
              return static_cast<Element>(p);
          },
          py::arg("commands"), py::arg("cursor") = 0);

    // ── activity_indicator(detail, color) ───────────────────────────────
    // The animated "working…" ticker (rotating word pool + sweep). Pass an
    // optional trailing token (e.g. an elapsed time) as `detail`.
    w.def("activity_indicator",
          [](std::string detail, std::optional<Color> color) {
              ActivityIndicator::Config cfg{};
              cfg.detail = std::move(detail);
              if (color) cfg.edge_color = *color;
              return static_cast<Element>(ActivityIndicator{cfg});
          },
          py::arg("detail") = "", py::arg("color") = std::nullopt);

    // ── breadcrumb(segments) ────────────────────────────────────────────
    w.def("breadcrumb",
          [](std::vector<std::string> segments) {
              return static_cast<Element>(Breadcrumb{std::move(segments)});
          },
          py::arg("segments"));

    // ── tabs(labels, active) ────────────────────────────────────────────
    w.def("tabs",
          [](std::vector<std::string> labels, int active) {
              Tabs t{std::move(labels)};
              t.set_active(active);
              return static_cast<Element>(t);
          },
          py::arg("labels"), py::arg("active") = 0);

    // ── bar_chart(bars, max_value, default_color) ───────────────────────
    // bars: list of (label, value) or (label, value, color) tuples.
    w.def("bar_chart",
          [](const py::list& bars, float max_value, std::optional<Color> default_color) {
              std::vector<Bar> bs;
              for (const auto& item : bars) {
                  auto t = item.cast<py::sequence>();
                  Bar b{};
                  b.label = t[0].cast<std::string>();
                  b.value = t[1].cast<float>();
                  if (t.size() > 2 && !t[2].is_none()) b.color = t[2].cast<Color>();
                  bs.push_back(std::move(b));
              }
              BarChart chart{std::move(bs), max_value};
              if (default_color) chart.set_default_color(*default_color);
              return static_cast<Element>(chart);
          },
          py::arg("bars"), py::arg("max_value") = 0.0f,
          py::arg("default_color") = std::nullopt);

    // ── gradient(text, start, end) ──────────────────────────────────────
    w.def("gradient",
          [](const std::string& text, Color start, Color end) {
              return gradient(text, start, end);
          },
          py::arg("text"), py::arg("start"), py::arg("end"));

    // ── heatmap(grid, low, high, x_labels, y_labels) ────────────────────
    w.def("heatmap",
          [](std::vector<std::vector<float>> grid, std::optional<Color> low,
             std::optional<Color> high, std::vector<std::string> x_labels,
             std::vector<std::string> y_labels) {
              Heatmap h{std::move(grid)};
              if (low)  h.set_low_color(*low);
              if (high) h.set_high_color(*high);
              if (!x_labels.empty()) h.set_x_labels(std::move(x_labels));
              if (!y_labels.empty()) h.set_y_labels(std::move(y_labels));
              return static_cast<Element>(h);
          },
          py::arg("grid"), py::arg("low") = std::nullopt, py::arg("high") = std::nullopt,
          py::arg("x_labels") = std::vector<std::string>{},
          py::arg("y_labels") = std::vector<std::string>{});

    // ── checkbox(label, checked) ────────────────────────────────────────
    w.def("checkbox",
          [](std::string label, bool checked) {
              Checkbox c{std::move(label), checked};
              return static_cast<Element>(c);
          },
          py::arg("label"), py::arg("checked") = false);

    // ── toggle(label, on) ───────────────────────────────────────────────
    w.def("toggle",
          [](std::string label, bool on) {
              ToggleSwitch t{std::move(label), on};
              return static_cast<Element>(t);
          },
          py::arg("label"), py::arg("on") = false);

    // ── radio(items, selected, visible_count, on/off indicators) ────────
    w.def("radio",
          [](std::vector<std::string> items, int selected, int visible_count,
             const std::string& selected_indicator,
             const std::string& unselected_indicator) {
              RadioConfig cfg{};
              if (visible_count > 0) cfg.visible_count = visible_count;
              if (!selected_indicator.empty()) cfg.selected_indicator = selected_indicator;
              if (!unselected_indicator.empty()) cfg.unselected_indicator = unselected_indicator;
              Radio r{std::move(items), cfg};
              r.set_selected(selected);
              return static_cast<Element>(r);
          },
          py::arg("items"), py::arg("selected") = 0, py::arg("visible_count") = 0,
          py::arg("selected_indicator") = "", py::arg("unselected_indicator") = "");

    // ── select(items, cursor, indicator, visible_count, inactive_prefix) ─
    w.def("select",
          [](std::vector<std::string> items, int cursor,
             const std::string& indicator, int visible_count,
             const std::string& inactive_prefix) {
              SelectConfig cfg{};
              if (!indicator.empty()) cfg.indicator = indicator;
              if (!inactive_prefix.empty()) cfg.inactive_prefix = inactive_prefix;
              if (visible_count > 0) cfg.visible_count = visible_count;
              Select s{std::move(items), cfg};
              if (cursor > 0) const_cast<Signal<int>&>(s.cursor()).set(cursor);
              return static_cast<Element>(s);
          },
          py::arg("items"), py::arg("cursor") = 0,
          py::arg("indicator") = "", py::arg("visible_count") = 0,
          py::arg("inactive_prefix") = "");

    // ── slider(value, label, min, max, step, width, fill, track) ────────
    // width must be > 0 for a static render: the dynamic-width path returns a
    // ComponentElement capturing the Slider, which dangles once this factory
    // returns. A fixed track width builds a concrete element.
    w.def("slider",
          [](float value, std::string label, float vmin, float vmax, float step,
             int width, std::optional<Color> fill, std::optional<Color> track) {
              SliderConfig cfg{};
              cfg.min = vmin;
              cfg.max = vmax;
              cfg.step = step;
              cfg.width = width > 0 ? width : 24;
              if (fill)  cfg.fill_color = *fill;
              if (track) cfg.track_color = *track;
              Slider s{std::move(label), cfg};
              s.set_value(value);
              return static_cast<Element>(s);
          },
          py::arg("value"), py::arg("label") = "",
          py::arg("min") = 0.0f, py::arg("max") = 1.0f, py::arg("step") = 0.01f,
          py::arg("width") = 24,
          py::arg("fill") = std::nullopt, py::arg("track") = std::nullopt);

    // ── button(label, variant) ──────────────────────────────────────────
    w.def("button",
          [](std::string label, ButtonVariant variant) {
              Button b{std::move(label), {}, variant};
              return static_cast<Element>(b);
          },
          py::arg("label"), py::arg("variant") = ButtonVariant::Default);

    // ── calendar(year, month, today=(y,m,d)) ────────────────────────────
    w.def("calendar",
          [](int year, int month, std::optional<py::sequence> today) {
              if (today && py::len(*today) >= 3) {
                  return static_cast<Element>(
                      Calendar{year, month, (*today)[0].cast<int>(),
                               (*today)[1].cast<int>(), (*today)[2].cast<int>()});
              }
              return static_cast<Element>(Calendar{year, month});
          },
          py::arg("year"), py::arg("month"), py::arg("today") = std::nullopt);

    // ── line_chart(data, height, label, color) ──────────────────────────
    w.def("line_chart",
          [](std::vector<float> data, int height, std::string label,
             std::optional<Color> color) {
              LineChart c{std::move(data), height};
              if (!label.empty()) c.set_label(label);
              if (color) c.set_color(*color);
              return static_cast<Element>(c);
          },
          py::arg("data"), py::arg("height") = 8, py::arg("label") = "",
          py::arg("color") = std::nullopt);

    // ── link(text, url, show_icon, color) ───────────────────────────────
    w.def("link",
          [](std::string text, std::string url, bool show_icon,
             std::optional<Color> color) {
              Link l{};
              l.text = std::move(text);
              l.url = std::move(url);
              l.show_icon = show_icon;
              if (color) l.link_style = Style{}.with_fg(*color).with_underline();
              return static_cast<Element>(l);
          },
          py::arg("text"), py::arg("url") = "", py::arg("show_icon") = false,
          py::arg("color") = std::nullopt);

    // ── key_help(bindings, title) ───────────────────────────────────────
    // bindings: list of (key, description) or (key, description, group).
    w.def("key_help",
          [](const py::list& bindings, const std::string& title) {
              std::vector<KeyBinding> bs;
              for (const auto& item : bindings) {
                  auto t = item.cast<py::sequence>();
                  KeyBinding b{};
                  b.key = t[0].cast<std::string>();
                  if (py::len(t) > 1) b.description = t[1].cast<std::string>();
                  if (py::len(t) > 2) b.group = t[2].cast<std::string>();
                  bs.push_back(std::move(b));
              }
              KeyHelp k{std::move(bs)};
              if (!title.empty()) k.set_title(title);
              return static_cast<Element>(k);
          },
          py::arg("bindings"), py::arg("title") = "");

    // ── timeline(events, show_connector, compact, frame, track_width) ───
    // events: list of dicts/tuples (label, detail, duration, status, bar_width).
    w.def("timeline",
          [](const py::list& events, bool show_connector, bool compact,
             int frame, int track_width) {
              std::vector<TimelineEvent> evs;
              for (const auto& item : events) {
                  TimelineEvent ev{};
                  if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("label"))    ev.label = d["label"].cast<std::string>();
                      if (d.contains("detail"))   ev.detail = d["detail"].cast<std::string>();
                      if (d.contains("duration")) ev.duration = d["duration"].cast<std::string>();
                      if (d.contains("status"))   ev.status = d["status"].cast<TaskStatus>();
                      if (d.contains("bar_width"))ev.bar_width = d["bar_width"].cast<int>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      ev.label = t[0].cast<std::string>();
                      if (py::len(t) > 1) ev.detail = t[1].cast<std::string>();
                      if (py::len(t) > 2) ev.duration = t[2].cast<std::string>();
                      if (py::len(t) > 3) ev.status = t[3].cast<TaskStatus>();
                      if (py::len(t) > 4) ev.bar_width = t[4].cast<int>();
                  }
                  evs.push_back(std::move(ev));
              }
              Timeline tl{};
              for (auto& ev : evs) tl.add(std::move(ev));
              tl.set_show_connector(show_connector);
              tl.set_compact(compact);
              tl.set_frame(frame);
              tl.set_track_width(track_width);
              return static_cast<Element>(tl);
          },
          py::arg("events"), py::arg("show_connector") = true,
          py::arg("compact") = false, py::arg("frame") = 0,
          py::arg("track_width") = 40);

    // ── tree(root) — root is a nested dict {label, children, expanded} ──
    w.def("tree",
          [](const py::dict& root, const std::string& expanded_icon,
             const std::string& collapsed_icon, const std::string& leaf_prefix,
             int indent_width) {
              std::function<TreeNode(const py::dict&)> conv =
                  [&](const py::dict& d) -> TreeNode {
                  TreeNode n{};
                  if (d.contains("label")) n.label = d["label"].cast<std::string>();
                  if (d.contains("expanded")) n.expanded = d["expanded"].cast<bool>();
                  if (d.contains("selected")) n.selected = d["selected"].cast<bool>();
                  if (d.contains("children")) {
                      for (const auto& c : d["children"].cast<py::list>())
                          n.children.push_back(conv(c.cast<py::dict>()));
                  }
                  return n;
              };
              TreeConfig cfg{};
              if (!expanded_icon.empty()) cfg.expanded_icon = expanded_icon;
              if (!collapsed_icon.empty()) cfg.collapsed_icon = collapsed_icon;
              if (!leaf_prefix.empty()) cfg.leaf_prefix = leaf_prefix;
              if (indent_width > 0) cfg.indent_width = indent_width;
              Tree t{conv(root), cfg};
              return static_cast<Element>(t);
          },
          py::arg("root"), py::arg("expanded_icon") = "",
          py::arg("collapsed_icon") = "", py::arg("leaf_prefix") = "",
          py::arg("indent_width") = 0);

    // ── list(items, cursor, filterable, visible_count) ──────────────────
    // items: list of str, or dicts/tuples (label, description, icon).
    w.def("list_view",
          [](const py::list& items, int cursor, bool filterable, int visible_count,
             const std::string& indicator, const std::string& inactive_prefix) {
              std::vector<ListItem> lis;
              for (const auto& item : items) {
                  ListItem li{};
                  if (py::isinstance<py::str>(item)) {
                      li.label = item.cast<std::string>();
                  } else if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("label"))       li.label = d["label"].cast<std::string>();
                      if (d.contains("description")) li.description = d["description"].cast<std::string>();
                      if (d.contains("icon"))        li.icon = d["icon"].cast<std::string>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      li.label = t[0].cast<std::string>();
                      if (py::len(t) > 1) li.description = t[1].cast<std::string>();
                      if (py::len(t) > 2) li.icon = t[2].cast<std::string>();
                  }
                  lis.push_back(std::move(li));
              }
              ListConfig cfg{};
              cfg.filterable = filterable;
              if (visible_count > 0) cfg.visible_count = visible_count;
              if (!indicator.empty()) cfg.indicator = indicator;
              if (!inactive_prefix.empty()) cfg.inactive_prefix = inactive_prefix;
              List l{std::move(lis), cfg};
              if (cursor > 0) const_cast<Signal<int>&>(l.cursor()).set(cursor);
              return static_cast<Element>(l);
          },
          py::arg("items"), py::arg("cursor") = 0,
          py::arg("filterable") = false, py::arg("visible_count") = 0,
          py::arg("indicator") = "", py::arg("inactive_prefix") = "");

    // ── menu(items) — items: str, or (label, shortcut, enabled, separator) ─
    w.def("menu",
          [](const py::list& items, int cursor) {
              std::vector<MenuItem> mis;
              for (const auto& item : items) {
                  MenuItem mi{};
                  if (py::isinstance<py::str>(item)) {
                      mi.label = item.cast<std::string>();
                  } else if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("label"))     mi.label = d["label"].cast<std::string>();
                      if (d.contains("shortcut"))  mi.shortcut = d["shortcut"].cast<std::string>();
                      if (d.contains("enabled"))   mi.enabled = d["enabled"].cast<bool>();
                      if (d.contains("separator")) mi.separator = d["separator"].cast<bool>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      mi.label = t[0].cast<std::string>();
                      if (py::len(t) > 1) mi.shortcut = t[1].cast<std::string>();
                      if (py::len(t) > 2) mi.enabled = t[2].cast<bool>();
                      if (py::len(t) > 3) mi.separator = t[3].cast<bool>();
                  }
                  mis.push_back(std::move(mi));
              }
              Menu mn{std::move(mis)};
              if (cursor > 0) const_cast<Signal<int>&>(mn.cursor()).set(cursor);
              return static_cast<Element>(mn);
          },
          py::arg("items"), py::arg("cursor") = 0);

    // ── disclosure(label, open, content, open_icon, closed_icon) ───────
    w.def("disclosure",
          [](std::string label, bool open, std::optional<Element> content,
             const std::string& open_icon, const std::string& closed_icon) {
              Disclosure::Config cfg{};
              cfg.label = std::move(label);
              if (!open_icon.empty()) cfg.open_icon = open_icon;
              if (!closed_icon.empty()) cfg.closed_icon = closed_icon;
              Disclosure d{cfg};
              d.set_open(open);
              if (content) return d.build(*content);
              return d.build();
          },
          py::arg("label"), py::arg("open") = false,
          py::arg("content") = std::nullopt,
          py::arg("open_icon") = "", py::arg("closed_icon") = "");

    // ── toast(messages, duration, fade_time, max_visible) ──────────────
    w.def("toast",
          [](const py::list& messages, float duration, float fade_time,
             int max_visible) {
              ToastManager::Config cfg{};
              cfg.duration = duration;
              cfg.fade_time = fade_time;
              if (max_visible > 0) cfg.max_visible = max_visible;
              ToastManager tm{cfg};
              for (const auto& item : messages) {
                  if (py::isinstance<py::str>(item)) {
                      tm.push(item.cast<std::string>(), ToastLevel::Info);
                  } else {
                      auto t = item.cast<py::sequence>();
                      ToastLevel lvl = ToastLevel::Info;
                      if (py::len(t) > 1) lvl = t[1].cast<ToastLevel>();
                      tm.push(t[0].cast<std::string>(), lvl);
                  }
              }
              return static_cast<Element>(tm);
          },
          py::arg("messages"), py::arg("duration") = 3.0f,
          py::arg("fade_time") = 0.5f, py::arg("max_visible") = 0);

    // ── todo_list(items, description, status, elapsed, expanded) ─────────
    // items: (content, status) tuples or strings.
    w.def("todo_list",
          [](const py::list& items, std::string description,
             TodoListStatus status, float elapsed, bool expanded) {
              std::vector<TodoListItem> tis;
              for (const auto& item : items) {
                  TodoListItem ti{};
                  if (py::isinstance<py::str>(item)) {
                      ti.content = item.cast<std::string>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      ti.content = t[0].cast<std::string>();
                      if (py::len(t) > 1) ti.status = t[1].cast<TodoItemStatus>();
                  }
                  tis.push_back(std::move(ti));
              }
              TodoListTool tl{};
              tl.set_items(std::move(tis));
              if (!description.empty()) tl.set_description(description);
              tl.set_status(status);
              tl.set_elapsed(elapsed);
              tl.set_expanded(expanded);
              return static_cast<Element>(tl);
          },
          py::arg("items"), py::arg("description") = "",
          py::arg("status") = TodoListStatus::Pending,
          py::arg("elapsed") = 0.0f, py::arg("expanded") = true);

    // ── title_chip(title, edge_color, text_color, max_chars) ────────────
    w.def("title_chip",
          [](std::string title, std::optional<Color> edge,
             std::optional<Color> text, int max_chars) {
              TitleChip::Config cfg{};
              cfg.title = std::move(title);
              if (edge) cfg.edge_color = *edge;
              if (text) cfg.text_color = *text;
              if (max_chars > 0) cfg.max_chars = static_cast<std::size_t>(max_chars);
              return static_cast<Element>(TitleChip{cfg});
          },
          py::arg("title"), py::arg("edge_color") = std::nullopt,
          py::arg("text_color") = std::nullopt, py::arg("max_chars") = 0);

    // ── model_badge(model, compact) ─────────────────────────────────────
    w.def("model_badge",
          [](std::string model, bool compact) {
              ModelBadge mb{std::move(model)};
              mb.set_compact(compact);
              return static_cast<Element>(mb);
          },
          py::arg("model"), py::arg("compact") = false);

    // ── file_ref(path, line, show_icon) ─────────────────────────────────
    w.def("file_ref",
          [](std::string path, int line, bool show_icon) {
              FileRef fr{std::move(path), line};
              FileRef::Config cfg{};
              cfg.show_icon = show_icon;
              return fr.build(cfg);
          },
          py::arg("path"), py::arg("line") = 0, py::arg("show_icon") = true);

    // ── inline_diff(before, after, label, show_header) ──────────────────
    w.def("inline_diff",
          [](std::string before, std::string after, std::string label,
             bool show_header) {
              InlineDiffConfig cfg{};
              cfg.show_header = show_header;
              InlineDiff d{std::move(before), std::move(after), cfg};
              if (!label.empty()) d.set_label(std::move(label));
              return static_cast<Element>(d);
          },
          py::arg("before"), py::arg("after"), py::arg("label") = "",
          py::arg("show_header") = true);

    // ── flame_chart(spans, time_scale, width, show_times) ───────────────
    // spans: (label, start, duration, depth, color) tuples.
    w.def("flame_chart",
          [](const py::list& spans, float time_scale, int width, bool show_times,
             int max_depth) {
              FlameChart fc{time_scale};
              fc.set_width(width);
              fc.set_show_times(show_times);
              if (max_depth > 0) fc.set_max_depth(max_depth);
              for (const auto& item : spans) {
                  auto t = item.cast<py::sequence>();
                  std::string label = t[0].cast<std::string>();
                  float start = t[1].cast<float>();
                  float dur = t[2].cast<float>();
                  int depth = py::len(t) > 3 ? t[3].cast<int>() : 0;
                  Color color = (py::len(t) > 4 && !t[4].is_none())
                                    ? t[4].cast<Color>() : Color{};
                  fc.add_span(std::move(label), start, dur, depth, color);
              }
              return static_cast<Element>(fc);
          },
          py::arg("spans"), py::arg("time_scale") = 0.0f,
          py::arg("width") = 60, py::arg("show_times") = true,
          py::arg("max_depth") = 0);

    // ── waterfall(entries, time_scale, bar_width, show_labels, frame) ───
    // entries: (label, start, duration, color) tuples.
    w.def("waterfall",
          [](const py::list& entries, float time_scale, int bar_width,
             bool show_labels, int frame, bool show_times) {
              Waterfall wf{};
              wf.set_time_scale(time_scale);
              wf.set_bar_width(bar_width);
              wf.set_show_labels(show_labels);
              wf.set_show_times(show_times);
              wf.set_frame(frame);
              for (const auto& item : entries) {
                  auto t = item.cast<py::sequence>();
                  WaterfallEntry e{};
                  e.label = t[0].cast<std::string>();
                  e.start = t[1].cast<float>();
                  e.duration = t[2].cast<float>();
                  if (py::len(t) > 3 && !t[3].is_none()) e.color = t[3].cast<Color>();
                  wf.add(std::move(e));
              }
              return static_cast<Element>(wf);
          },
          py::arg("entries"), py::arg("time_scale") = 0.0f,
          py::arg("bar_width") = 30, py::arg("show_labels") = true,
          py::arg("frame") = 0, py::arg("show_times") = true);

    // ── token_stream(total, rate, peak, elapsed, history, color, compact) ─
    // Live token-rate visualizer: sparkline + stats. `history` is a list of
    // per-tick rates (floats).
    w.def("token_stream",
          [](int total_tokens, float tokens_per_sec, float peak_rate,
             float elapsed, const std::vector<float>& history,
             std::optional<Color> color, bool compact) {
              TokenStream ts{};
              ts.set_total_tokens(total_tokens);
              ts.set_tokens_per_sec(tokens_per_sec);
              ts.set_peak_rate(peak_rate);
              ts.set_elapsed(elapsed);
              ts.set_rate_history(history);
              if (color) ts.set_color(*color);
              ts.set_compact(compact);
              return static_cast<Element>(ts);
          },
          py::arg("total_tokens") = 0, py::arg("tokens_per_sec") = 0.0f,
          py::arg("peak_rate") = 0.0f, py::arg("elapsed") = 0.0f,
          py::arg("history") = std::vector<float>{},
          py::arg("color") = std::nullopt, py::arg("compact") = false);

    // ── thinking(content, active, expanded, max_lines) ──────────────────
    w.def("thinking",
          [](std::string content, bool active, bool expanded, int max_lines) {
              ThinkingBlock t{};
              t.set_content(content);
              t.set_active(active);
              t.set_expanded(expanded);
              if (max_lines > 0) t.set_max_visible_lines(max_lines);
              return static_cast<Element>(t);
          },
          py::arg("content") = "", py::arg("active") = false,
          py::arg("expanded") = true, py::arg("max_lines") = 0);

    // ── markdown(source) — full GFM render to an Element ────────────────
    w.def("markdown",
          [](const std::string& source) {
              return maya::markdown(source);
          },
          py::arg("source"));

    // ── image(pixels, color) — pixels: 2-D list of bools (braille) ──────
    w.def("image",
          [](const std::vector<std::vector<int>>& pixels, std::optional<Color> color) {
              int h = static_cast<int>(pixels.size());
              int wd = 0;
              for (const auto& row : pixels) wd = std::max(wd, static_cast<int>(row.size()));
              Image img{wd, h, color.value_or(Color::white())};
              for (int y = 0; y < h; ++y)
                  for (int x = 0; x < static_cast<int>(pixels[y].size()); ++x)
                      if (pixels[y][x]) img.set_pixel(x, y, true);
              return static_cast<Element>(img);
          },
          py::arg("pixels"), py::arg("color") = std::nullopt);

    // ── canvas(pixels) — pixels: 2-D list of Color|None (half-block) ────
    w.def("canvas",
          [](const py::list& pixels) {
              int h = static_cast<int>(py::len(pixels));
              int wd = 0;
              for (const auto& row : pixels)
                  wd = std::max(wd, static_cast<int>(py::len(row.cast<py::sequence>())));
              PixelCanvas c{wd, h};
              int y = 0;
              for (const auto& row : pixels) {
                  auto r = row.cast<py::sequence>();
                  for (int x = 0; x < static_cast<int>(py::len(r)); ++x) {
                      if (!r[x].is_none()) c.set_pixel(x, y, r[x].cast<Color>());
                  }
                  ++y;
              }
              return static_cast<Element>(c);
          },
          py::arg("pixels"));

    // ── PixelCanvas — a stateful half-block drawing surface ──────────────
    // Resolution is width × (height*2) pixels. Draw imperatively with
    // set_pixel/line/rect/fill, then drop element() into a layout. This is
    // the maya PixelCanvas drawing API (vs. the canvas() grid factory above).
    py::class_<PixelCanvas>(w, "PixelCanvas")
        .def(py::init<int, int>(), py::arg("width"), py::arg("height"))
        .def_property_readonly("width", &PixelCanvas::width)
        .def_property_readonly("height", &PixelCanvas::height)
        .def_property_readonly("pixel_height", &PixelCanvas::pixel_height)
        .def("set_pixel",
             [](PixelCanvas& c, int x, int y, Color color) { c.set_pixel(x, y, color); },
             py::arg("x"), py::arg("y"), py::arg("color"))
        .def("line",
             [](PixelCanvas& c, int x1, int y1, int x2, int y2, Color color) {
                 c.line(x1, y1, x2, y2, color);
             },
             py::arg("x1"), py::arg("y1"), py::arg("x2"), py::arg("y2"), py::arg("color"))
        .def("rect",
             [](PixelCanvas& c, int x, int y, int wd, int ht, Color color) {
                 c.rect(x, y, wd, ht, color);
             },
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"), py::arg("color"))
        .def("fill", [](PixelCanvas& c, Color color) { c.fill(color); }, py::arg("color"))
        .def("clear", &PixelCanvas::clear)
        .def("element", [](const PixelCanvas& c) { return static_cast<Element>(c); });

    // ── picker(rows, title, accent, selected, header, footer, ...) ──────
    // A bordered command-palette / fuzzy-picker panel. `rows` are structured
    // (leading, trailing, selected, active) entries the widget styles itself
    // (edge bar + bold on the selected row). Rendered statically: the list
    // paints inline (no live ScrollState), so keep it within `viewport_h`
    // rows or pass a longer list and let it clip from the top.
    w.def("picker",
          [](const py::list& rows, std::string title, std::optional<Color> accent,
             int selected, std::vector<Element> header, std::vector<Element> footer,
             const py::list& items, int min_width, int viewport_h,
             std::optional<Color> cursor_color, std::optional<Color> active_color) {
              Picker::Config cfg{};
              if (!title.empty()) cfg.title = " " + title + " ";
              if (accent) cfg.accent = *accent;
              cfg.selected = selected;
              cfg.header = std::move(header);
              cfg.footer = std::move(footer);
              cfg.min_width = min_width;
              cfg.viewport_h = viewport_h;
              if (cursor_color) cfg.cursor_color = *cursor_color;
              if (active_color) cfg.active_color = *active_color;

              for (const auto& item : rows) {
                  Picker::Config::Row row{};
                  if (py::isinstance<py::str>(item)) {
                      row.leading = item.cast<std::string>();
                  } else if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("leading"))  row.leading = d["leading"].cast<std::string>();
                      if (d.contains("trailing")) row.trailing = d["trailing"].cast<std::string>();
                      if (d.contains("selected")) row.selected = d["selected"].cast<bool>();
                      if (d.contains("active"))   row.active = d["active"].cast<bool>();
                      if (d.contains("leading_style"))  row.leading_style = d["leading_style"].cast<Style>();
                      if (d.contains("trailing_style")) row.trailing_style = d["trailing_style"].cast<Style>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      row.leading = t[0].cast<std::string>();
                      if (py::len(t) > 1) row.trailing = t[1].cast<std::string>();
                      if (py::len(t) > 2) row.selected = t[2].cast<bool>();
                      if (py::len(t) > 3) row.active = t[3].cast<bool>();
                  }
                  cfg.rows.push_back(std::move(row));
              }
              // Raw pre-built item Elements (escape hatch; ignored if rows set).
              if (cfg.rows.empty()) {
                  for (const auto& it : items) cfg.items.push_back(it.cast<Element>());
              }
              return static_cast<Element>(Picker{std::move(cfg)});
          },
          py::arg("rows") = py::list{}, py::arg("title") = "",
          py::arg("accent") = std::nullopt, py::arg("selected") = -1,
          py::arg("header") = std::vector<Element>{},
          py::arg("footer") = std::vector<Element>{},
          py::arg("items") = py::list{}, py::arg("min_width") = 50,
          py::arg("viewport_h") = 14,
          py::arg("cursor_color") = std::nullopt,
          py::arg("active_color") = std::nullopt);

    // ── enums for the new widgets ───────────────────────────────────────
    py::enum_<PopupStyle>(w, "PopupStyle")
        .value("Info", PopupStyle::Info)
        .value("Warning", PopupStyle::Warning)
        .value("Error", PopupStyle::Error);

    py::enum_<BannerLevel>(w, "BannerLevel")
        .value("Info", BannerLevel::Info)
        .value("Success", BannerLevel::Success)
        .value("Warning", BannerLevel::Warning)
        .value("Error", BannerLevel::Error);

    py::enum_<ToolCallStatus>(w, "ToolCallStatus")
        .value("Pending", ToolCallStatus::Pending)
        .value("Running", ToolCallStatus::Running)
        .value("Completed", ToolCallStatus::Completed)
        .value("Failed", ToolCallStatus::Failed)
        .value("Confirmation", ToolCallStatus::Confirmation);

    py::enum_<ToolCallKind>(w, "ToolCallKind")
        .value("Read", ToolCallKind::Read)
        .value("Edit", ToolCallKind::Edit)
        .value("Execute", ToolCallKind::Execute)
        .value("Search", ToolCallKind::Search)
        .value("Delete", ToolCallKind::Delete)
        .value("Move", ToolCallKind::Move)
        .value("Fetch", ToolCallKind::Fetch)
        .value("Think", ToolCallKind::Think)
        .value("Agent", ToolCallKind::Agent)
        .value("Other", ToolCallKind::Other);

    // ── popup(content, style) ───────────────────────────────────────────
    w.def("popup",
          [](std::string content, PopupStyle style) {
              return static_cast<Element>(Popup{std::move(content), style});
          },
          py::arg("content"), py::arg("style") = PopupStyle::Info);

    // ── overlay(base, overlay, present) ─────────────────────────────────
    w.def("overlay",
          [](Element base, Element over, bool present) {
              Overlay::Config cfg{};
              cfg.base = std::move(base);
              cfg.overlay = std::move(over);
              cfg.present = present;
              return static_cast<Element>(Overlay{std::move(cfg)});
          },
          py::arg("base"), py::arg("overlay"), py::arg("present") = true);

    // ── user_message(content) / assistant_message(content) ──────────────
    // content is a string (user) or a pre-built Element (both).
    w.def("user_message",
          [](py::object content) {
              if (py::isinstance<py::str>(content))
                  return UserMessage::build(content.cast<std::string>());
              return UserMessage::build(content.cast<Element>());
          },
          py::arg("content"));
    w.def("assistant_message",
          [](Element content) { return AssistantMessage::build(std::move(content)); },
          py::arg("content"));

    // ── system_banner(message, level, dismissable) ──────────────────────
    w.def("system_banner",
          [](std::string message, BannerLevel level, bool dismissable) {
              SystemBanner b{std::move(message), level};
              b.set_dismissable(dismissable);
              return static_cast<Element>(b);
          },
          py::arg("message"), py::arg("level") = BannerLevel::Info,
          py::arg("dismissable") = false);

    // ── phase_chip(verb, glyph, color, breathing, frame, verb_width, elapsed) ─
    w.def("phase_chip",
          [](std::string verb, std::string glyph, std::optional<Color> color,
             bool breathing, int frame, int verb_width, float elapsed_secs) {
              PhaseChip::Config cfg{};
              cfg.verb = std::move(verb);
              cfg.glyph = std::move(glyph);
              if (color) cfg.color = *color;
              cfg.breathing = breathing;
              cfg.frame = frame;
              cfg.verb_width = verb_width;
              cfg.elapsed_secs = elapsed_secs;
              return static_cast<Element>(PhaseChip{std::move(cfg)});
          },
          py::arg("verb"), py::arg("glyph") = "", py::arg("color") = std::nullopt,
          py::arg("breathing") = false, py::arg("frame") = 0,
          py::arg("verb_width") = 10, py::arg("elapsed_secs") = -1.0f);

    // ── context_gauge(used, max, cells, show_bar) ───────────────────────
    w.def("context_gauge",
          [](int used, int max, int cells, bool show_bar) {
              ContextGauge::Config cfg{};
              cfg.used = used;
              cfg.max = max;
              cfg.cells = cells;
              cfg.show_bar = show_bar;
              return static_cast<Element>(ContextGauge{cfg});
          },
          py::arg("used"), py::arg("max"), py::arg("cells") = 10,
          py::arg("show_bar") = true);

    // ── context_window(segments, max_tokens, width, show_labels, show_percent) ─
    // segments: list of (label, tokens) or (label, tokens, color) tuples.
    w.def("context_window",
          [](const py::list& segments, int max_tokens, int width,
             bool show_labels, bool show_percent) {
              ContextWindow cw{max_tokens};
              if (width > 0) cw.set_width(width);
              cw.set_show_labels(show_labels);
              cw.set_show_percent(show_percent);
              for (const auto& item : segments) {
                  auto t = item.cast<py::sequence>();
                  std::string label = t[0].cast<std::string>();
                  int tokens = t[1].cast<int>();
                  if (py::len(t) > 2 && !t[2].is_none())
                      cw.add_segment(std::move(label), tokens, t[2].cast<Color>());
                  else
                      cw.add_segment(std::move(label), tokens);
              }
              return static_cast<Element>(cw);
          },
          py::arg("segments"), py::arg("max_tokens") = 200000,
          py::arg("width") = 0, py::arg("show_labels") = true,
          py::arg("show_percent") = true);

    // ── diff_view(path, diff, show_border, show_line_numbers) ───────────
    w.def("diff_view",
          [](std::string path, std::string diff, bool show_border,
             bool show_line_numbers) {
              DiffView::Config cfg{};
              cfg.show_border = show_border;
              cfg.show_line_numbers = show_line_numbers;
              return DiffView{std::move(path), std::move(diff), cfg}.build();
          },
          py::arg("path"), py::arg("diff"), py::arg("show_border") = true,
          py::arg("show_line_numbers") = true);

    // ── tool_call(name, kind, description, status, elapsed, expanded, content) ─
    w.def("tool_call",
          [](std::string name, ToolCallKind kind, std::string description,
             ToolCallStatus status, float elapsed, bool expanded,
             std::optional<Element> content) {
              ToolCall::Config cfg{};
              cfg.tool_name = std::move(name);
              cfg.kind = kind;
              cfg.description = std::move(description);
              ToolCall tc{std::move(cfg)};
              tc.set_status(status);
              tc.set_elapsed(elapsed);
              tc.set_expanded(expanded);
              if (content) tc.set_content(*content);
              return static_cast<Element>(tc);
          },
          py::arg("name"), py::arg("kind") = ToolCallKind::Other,
          py::arg("description") = "", py::arg("status") = ToolCallStatus::Pending,
          py::arg("elapsed") = 0.0f, py::arg("expanded") = false,
          py::arg("content") = std::nullopt);

    // ── git_graph(commits, max_branches, show_hash, show_author, show_time) ─
    // commits: list of dicts {hash, message, author, time, branch, is_merge, is_head}
    // or (hash, message, author, time, branch, is_merge, is_head) tuples.
    w.def("git_graph",
          [](const py::list& commits, int max_branches, bool show_hash,
             bool show_author, bool show_time) {
              GitGraph g{};
              if (max_branches > 0) g.set_max_branches(max_branches);
              g.set_show_hash(show_hash);
              g.set_show_author(show_author);
              g.set_show_time(show_time);
              for (const auto& item : commits) {
                  GitCommit c{};
                  if (py::isinstance<py::dict>(item)) {
                      auto d = item.cast<py::dict>();
                      if (d.contains("hash"))     c.hash = d["hash"].cast<std::string>();
                      if (d.contains("message"))  c.message = d["message"].cast<std::string>();
                      if (d.contains("author"))   c.author = d["author"].cast<std::string>();
                      if (d.contains("time"))     c.time = d["time"].cast<std::string>();
                      if (d.contains("branch"))   c.branch = d["branch"].cast<int>();
                      if (d.contains("is_merge")) c.is_merge = d["is_merge"].cast<bool>();
                      if (d.contains("is_head"))  c.is_head = d["is_head"].cast<bool>();
                  } else {
                      auto t = item.cast<py::sequence>();
                      c.hash = t[0].cast<std::string>();
                      if (py::len(t) > 1) c.message = t[1].cast<std::string>();
                      if (py::len(t) > 2) c.author = t[2].cast<std::string>();
                      if (py::len(t) > 3) c.time = t[3].cast<std::string>();
                      if (py::len(t) > 4) c.branch = t[4].cast<int>();
                      if (py::len(t) > 5) c.is_merge = t[5].cast<bool>();
                      if (py::len(t) > 6) c.is_head = t[6].cast<bool>();
                  }
                  g.add_commit(std::move(c));
              }
              return static_cast<Element>(g);
          },
          py::arg("commits"), py::arg("max_branches") = 0,
          py::arg("show_hash") = true, py::arg("show_author") = false,
          py::arg("show_time") = true);

    // ── git_status(branch, ahead, behind, modified, staged, untracked, ...) ─
    w.def("git_status",
          [](std::string branch, int ahead, int behind, int modified,
             int staged, int untracked, int deleted, int conflicts,
             bool compact, std::vector<std::string> changed_files) {
              GitStatusWidget g{};
              g.set_branch(std::move(branch));
              g.set_ahead(ahead);
              g.set_behind(behind);
              g.set_dirty(modified, staged, untracked);
              g.set_deleted(deleted);
              g.set_conflicts(conflicts);
              g.set_compact(compact);
              for (auto& f : changed_files) g.add_changed_file(std::move(f));
              return static_cast<Element>(g);
          },
          py::arg("branch") = "", py::arg("ahead") = 0, py::arg("behind") = 0,
          py::arg("modified") = 0, py::arg("staged") = 0, py::arg("untracked") = 0,
          py::arg("deleted") = 0, py::arg("conflicts") = 0, py::arg("compact") = true,
          py::arg("changed_files") = std::vector<std::string>{});

    // ── shortcut_row(bindings, text_color) ──────────────────────────────
    // bindings: list of (key, label) or (key, label, color, priority) tuples.
    w.def("shortcut_row",
          [](const py::list& bindings, std::optional<Color> text_color) {
              ShortcutRow::Config cfg{};
              if (text_color) cfg.text_color = *text_color;
              for (const auto& item : bindings) {
                  ShortcutRow::Binding b{};
                  auto t = item.cast<py::sequence>();
                  b.key = t[0].cast<std::string>();
                  if (py::len(t) > 1) b.label = t[1].cast<std::string>();
                  if (py::len(t) > 2 && !t[2].is_none()) b.key_color = t[2].cast<Color>();
                  if (py::len(t) > 3) b.priority = t[3].cast<int>();
                  cfg.bindings.push_back(std::move(b));
              }
              return static_cast<Element>(ShortcutRow{std::move(cfg)});
          },
          py::arg("bindings"), py::arg("text_color") = std::nullopt);

    // ── plan_view(tasks) ────────────────────────────────────────────────
    // tasks: list of str (pending) or (label, status) tuples; status is the
    // TaskStatus enum or pending/in_progress/completed.
    w.def("plan_view",
          [](const py::list& tasks) {
              PlanView pv{};
              for (const auto& item : tasks) {
                  PlanView::Task t{};
                  if (py::isinstance<py::str>(item)) {
                      t.label = item.cast<std::string>();
                  } else {
                      auto seq = item.cast<py::sequence>();
                      t.label = seq[0].cast<std::string>();
                      if (py::len(seq) > 1) t.status = seq[1].cast<TaskStatus>();
                  }
                  pv.tasks.push_back(std::move(t));
              }
              return static_cast<Element>(pv);
          },
          py::arg("tasks"));


    // ── ScrollState ─────────────────────────────────────────────────────
    // A mutable scroll position. Hold one in your Python state, build the
    // viewport() around your content + a scrollbar(), and route events to
    // it with handle_event(ev). The renderer writes back max_x / max_y
    // after layout so the next frame clamps correctly.
    py::class_<ScrollState>(w, "ScrollState")
        .def(py::init<>())
        .def_readwrite("x", &ScrollState::x)
        .def_readwrite("y", &ScrollState::y)
        .def_readwrite("max_x", &ScrollState::max_x)
        .def_readwrite("max_y", &ScrollState::max_y)
        .def_readwrite("step_x", &ScrollState::step_x)
        .def_readwrite("step_y", &ScrollState::step_y)
        .def_readwrite("auto_dispatch", &ScrollState::auto_dispatch)
        .def("scroll_by", &ScrollState::scroll_by, py::arg("dx"), py::arg("dy"))
        .def("scroll_to", &ScrollState::scroll_to, py::arg("x"), py::arg("y"))
        .def("scroll_to_top", &ScrollState::scroll_to_top)
        .def("scroll_to_bottom", &ScrollState::scroll_to_bottom)
        .def("scroll_to_left", &ScrollState::scroll_to_left)
        .def("scroll_to_right", &ScrollState::scroll_to_right)
        .def("scroll_to_origin", &ScrollState::scroll_to_origin)
        .def("at_top", &ScrollState::at_top)
        .def("at_bottom", &ScrollState::at_bottom)
        .def("at_left", &ScrollState::at_left)
        .def("at_right", &ScrollState::at_right)
        .def("clamp", &ScrollState::clamp)
        // Painted-region bounds, written back by the renderer each frame.
        // viewport_bounds is the on-screen rect (0-based canvas coords) the
        // viewport() content occupies — use it to hit-test clicks against
        // the content WITHOUT hardcoding screen offsets.
        .def_property_readonly("viewport_bounds", [](const ScrollState& s) {
            return py::make_tuple(s.viewport_bounds.x, s.viewport_bounds.y,
                                  s.viewport_bounds.w, s.viewport_bounds.h);
        })
        .def_property_readonly("bar_v_bounds", [](const ScrollState& s) {
            return py::make_tuple(s.bar_v_bounds.x, s.bar_v_bounds.y,
                                  s.bar_v_bounds.w, s.bar_v_bounds.h);
        })
        .def_property_readonly("bar_h_bounds", [](const ScrollState& s) {
            return py::make_tuple(s.bar_h_bounds.x, s.bar_h_bounds.y,
                                  s.bar_h_bounds.w, s.bar_h_bounds.h);
        });

    // ── ScrollbarStyle ──────────────────────────────────────────────────
    // Glyphs + colors. Use a preset (line/block/slim/...) or build one and
    // tweak track_color / thumb_color.
    py::class_<ScrollbarStyle>(w, "ScrollbarStyle")
        .def(py::init<>())
        .def_readwrite("track_color", &ScrollbarStyle::track_color)
        .def_readwrite("thumb_color", &ScrollbarStyle::thumb_color)
        .def_static("line", &ScrollbarStyle::line)
        .def_static("block", &ScrollbarStyle::block)
        .def_static("slim", &ScrollbarStyle::slim)
        .def_static("heavy", &ScrollbarStyle::heavy)
        .def_static("double_line", &ScrollbarStyle::double_line)
        .def_static("dotted", &ScrollbarStyle::dotted)
        .def_static("dashed", &ScrollbarStyle::dashed)
        .def_static("braille", &ScrollbarStyle::braille)
        .def_static("ascii", &ScrollbarStyle::ascii)
        .def_static("shadow", &ScrollbarStyle::shadow)
        .def_static("minimal", &ScrollbarStyle::minimal)
        .def_static("neon", &ScrollbarStyle::neon)
        .def_static("retro", &ScrollbarStyle::retro)
        .def_static("danger", &ScrollbarStyle::danger)
        .def_static("pixel", &ScrollbarStyle::pixel);

    // ── scrollbar_y / scrollbar_x ───────────────────────────────────────
    // The bar reflects `state` over a track `viewport` cells tall/wide.
    // The ScrollState reference must outlive the rendered frame (hold it
    // in your Python state).
    w.def("scrollbar_y",
          [](ScrollState& s, int viewport, std::optional<ScrollbarStyle> style) {
              return maya::scrollbar_y(s, viewport, style.value_or(ScrollbarStyle{}));
          },
          py::arg("state"), py::arg("viewport"), py::arg("style") = std::nullopt,
          py::keep_alive<0, 1>());
    w.def("scrollbar_x",
          [](ScrollState& s, int viewport, std::optional<ScrollbarStyle> style) {
              return maya::scrollbar_x(s, viewport, style.value_or(ScrollbarStyle{}));
          },
          py::arg("state"), py::arg("viewport"), py::arg("style") = std::nullopt,
          py::keep_alive<0, 1>());

    // ── viewport(content, state, width, height) ─────────────────────────
    // Clip `content` to a width×height window scrolled by `state` (the
    // runtime equivalent of maya's `content | scroll(state, w, h)` pipe).
    // width/height of 0 means "fill available space on that axis". The
    // renderer writes max_x / max_y back into `state` after layout.
    w.def("viewport",
          [](const Element& content, ScrollState& s, int width, int height,
             float grow) {
              // Wrap content in a box, then set the scroll fields the
              // builder doesn't expose — mirrors dsl::scroll()'s WrappedNode.
              auto b = maya::box();
              if (width > 0)  b.width(Dimension::fixed(width));
              if (height > 0) b.height(Dimension::fixed(height));
              if (grow > 0.0f) b.grow(grow);
              Element built = b(content);
              if (auto* bx = maya::as_box(built)) {
                  bx->overflow         = Overflow::Scroll;
                  bx->layout.scroll_x  = s.x;
                  bx->layout.scroll_y  = s.y;
                  bx->scroll_state     = &s;
                  bx->scroll_role      = ScrollRole::Viewport;
              }
              return built;
          },
          py::arg("content"), py::arg("state"),
          py::arg("width") = 0, py::arg("height") = 0, py::arg("grow") = 0.0f,
          py::keep_alive<0, 2>());
}
