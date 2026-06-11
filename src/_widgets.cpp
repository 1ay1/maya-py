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
#include <maya/widget/thinking.hpp>
#include <maya/widget/markdown.hpp>
#include <maya/widget/image.hpp>
#include <maya/widget/canvas.hpp>
#include <maya/widget/picker.hpp>
#include <maya/widget/plan_view.hpp>  // TaskStatus

#include <optional>
#include <string>
#include <vector>
#include <functional>

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

    // ── radio(items, selected, visible_count) ───────────────────────────
    w.def("radio",
          [](std::vector<std::string> items, int selected, int visible_count) {
              RadioConfig cfg{};
              if (visible_count > 0) cfg.visible_count = visible_count;
              Radio r{std::move(items), cfg};
              r.set_selected(selected);
              return static_cast<Element>(r);
          },
          py::arg("items"), py::arg("selected") = 0, py::arg("visible_count") = 0);

    // ── select(items, cursor, indicator, visible_count) ─────────────────
    w.def("select",
          [](std::vector<std::string> items, int cursor,
             const std::string& indicator, int visible_count) {
              SelectConfig cfg{};
              if (!indicator.empty()) cfg.indicator = indicator;
              if (visible_count > 0) cfg.visible_count = visible_count;
              Select s{std::move(items), cfg};
              if (cursor > 0) const_cast<Signal<int>&>(s.cursor()).set(cursor);
              return static_cast<Element>(s);
          },
          py::arg("items"), py::arg("cursor") = 0,
          py::arg("indicator") = "", py::arg("visible_count") = 0);

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
          [](const py::dict& root) {
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
              Tree t{conv(root)};
              return static_cast<Element>(t);
          },
          py::arg("root"));

    // ── list(items, cursor, filterable, visible_count) ──────────────────
    // items: list of str, or dicts/tuples (label, description, icon).
    w.def("list_view",
          [](const py::list& items, int cursor, bool filterable, int visible_count) {
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
              List l{std::move(lis), cfg};
              if (cursor > 0) const_cast<Signal<int>&>(l.cursor()).set(cursor);
              return static_cast<Element>(l);
          },
          py::arg("items"), py::arg("cursor") = 0,
          py::arg("filterable") = false, py::arg("visible_count") = 0);

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

    // ── disclosure(label, open, content) ────────────────────────────────
    w.def("disclosure",
          [](std::string label, bool open, std::optional<Element> content) {
              Disclosure::Config cfg{};
              cfg.label = std::move(label);
              Disclosure d{cfg};
              d.set_open(open);
              if (content) return d.build(*content);
              return d.build();
          },
          py::arg("label"), py::arg("open") = false,
          py::arg("content") = std::nullopt);

    // ── toast(messages) — list of (message, level) ──────────────────────
    w.def("toast",
          [](const py::list& messages) {
              ToastManager::Config cfg{};
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
          py::arg("messages"));

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
          [](const py::list& spans, float time_scale, int width, bool show_times) {
              FlameChart fc{time_scale};
              fc.set_width(width);
              fc.set_show_times(show_times);
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
          py::arg("width") = 60, py::arg("show_times") = true);

    // ── waterfall(entries, time_scale, bar_width, show_labels, frame) ───
    // entries: (label, start, duration, color) tuples.
    w.def("waterfall",
          [](const py::list& entries, float time_scale, int bar_width,
             bool show_labels, int frame) {
              Waterfall wf{};
              wf.set_time_scale(time_scale);
              wf.set_bar_width(bar_width);
              wf.set_show_labels(show_labels);
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
          py::arg("frame") = 0);

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
