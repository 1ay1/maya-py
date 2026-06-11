// _widgets.cpp — pybind11 bindings for maya's widget library.
//
// maya ships ~90 widget renderers under <maya/widget/*.hpp> that are NOT
// pulled in by <maya/maya.hpp>. Each is a small class built from data + a
// Config and convertible to Element. We bind the presentational (render-only)
// ones as Python factory functions: pass simple Python values, get an Element
// back — the SAME Element maya's own renderers produce.
//
// Interactive controls (Input, TextArea, List, Tree, Tabs navigation) need
// the Program runtime + focus + signals, which can't cross into Python, so
// only their static appearance is exposed where a public render path exists.

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

#include <optional>
#include <string>
#include <vector>

namespace py = pybind11;
using namespace maya;

void init_widgets(py::module_& m) {
    auto w = m.def_submodule("_widgets", "maya widget renderers");

    // ── enums ───────────────────────────────────────────────────────────
    py::enum_<GaugeStyle>(w, "GaugeStyle")
        .value("Arc", GaugeStyle::Arc)
        .value("Bar", GaugeStyle::Bar);

    py::enum_<ColumnAlign>(w, "ColumnAlign")
        .value("Left", ColumnAlign::Left)
        .value("Center", ColumnAlign::Center)
        .value("Right", ColumnAlign::Right);

    // ── sparkline(data, label, color, show_min_max, show_last) ──────────
    w.def("sparkline",
          [](std::vector<float> data, std::string label, std::optional<Color> color,
             bool show_min_max, bool show_last) {
              SparklineConfig cfg{};
              if (color) cfg.color = *color;
              cfg.show_min_max = show_min_max;
              cfg.show_last = show_last;
              Sparkline s{std::move(data), cfg};
              if (!label.empty()) s.set_label(label);
              return static_cast<Element>(s);
          },
          py::arg("data"), py::arg("label") = "",
          py::arg("color") = std::nullopt,
          py::arg("show_min_max") = false, py::arg("show_last") = false);

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
}
