// _program.cpp — the FULL maya MVU runtime, exposed to Python 1:1.
//
// maya's primary API is a Program: pure init/update/view/subscribe over a
// Model + Msg, with side effects described as Cmd data and event sources as
// Sub data. The C++ entry point run<P> is a compile-time template keyed on
// the Program type, so it can't be instantiated from a dynamic Python type.
//
// Instead we instantiate maya's OWN runtime machinery at Msg = py::object and
// replicate the run<P> event loop here verbatim (same poll cadence, same Cmd
// interpreter, same Sub dispatch, same timer reconcile, same RAF/animation
// scheduling). Python gets the identical model — not a simplified imperative
// shim. Cmd and Sub are bound as opaque value types built by the same smart
// constructors the C++ side uses.

#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include <pybind11/stl.h>

#include <maya/maya.hpp>
#include <maya/platform/io.hpp>   // platform::io_write_all / stdout_handle (cross-platform)

#include "_pyevent.hpp"

#include <chrono>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;
using namespace maya;

// Msg is an arbitrary Python object. Model is held as a py::object too; the
// pure functions are Python callables.
using Msg  = py::object;
using PCmd = Cmd<Msg>;
using PSub = Sub<Msg>;

// ── Helpers to coerce Python return values ──────────────────────────────────

// update()/init() return (model, Cmd) or just model. Normalize to a pair.
static std::pair<py::object, PCmd> split_model_cmd(py::handle r) {
    if (py::isinstance<py::tuple>(r)) {
        auto t = r.cast<py::tuple>();
        if (t.size() == 2 && py::isinstance<PCmd>(t[1])) {
            return {py::reinterpret_borrow<py::object>(t[0]), t[1].cast<PCmd>()};
        }
    }
    // bare model → no command
    return {py::reinterpret_borrow<py::object>(r), PCmd::none()};
}

static PSub call_subscribe(py::object& subscribe_fn, py::object& model) {
    if (subscribe_fn.is_none()) return PSub::none();
    py::object r = subscribe_fn(model);
    if (r.is_none()) return PSub::none();
    return r.cast<PSub>();
}

// ── Cmd / Sub bindings ──────────────────────────────────────────────────────

static void bind_cmd_sub(py::module_& m) {
    // ── Cmd ─────────────────────────────────────────────────────────────
    py::class_<PCmd> cmd(m, "Cmd",
        "A side effect described as data. update() returns (model, Cmd); the\n"
        "runtime performs the effect. Same semantics as maya's C++ Cmd<Msg>.");

    cmd.def_static("none", &PCmd::none, "No effect.");
    cmd.def_static("quit", &PCmd::quit, "Quit the application.");

    cmd.def_static("batch",
        [](py::args cmds) {
            std::vector<PCmd> v;
            v.reserve(cmds.size());
            for (auto c : cmds) v.push_back(c.cast<PCmd>());
            return PCmd::batch(std::move(v));
        },
        "Run several commands.");

    cmd.def_static("after",
        [](double ms, Msg msg) {
            return PCmd::after(std::chrono::milliseconds((long)ms), std::move(msg));
        },
        py::arg("ms"), py::arg("msg"),
        "Dispatch `msg` once after `ms` milliseconds (one-shot timer).");

    cmd.def_static("set_title",
        [](const std::string& t) { return PCmd::set_title(t); },
        py::arg("title"), "Set the terminal window title.");

    cmd.def_static("write_clipboard",
        [](const std::string& s) { return PCmd::write_clipboard(s); },
        py::arg("text"), "Write text to the system clipboard (OSC 52).");

    cmd.def_static("query_clipboard", &PCmd::query_clipboard,
        "Request the system clipboard; reply arrives as a paste event.");

    cmd.def_static("task",
        [](py::function fn) {
            // fn(dispatch) — runs on the shared BG worker pool. It receives a
            // dispatch callable; calling dispatch(msg) feeds the message back
            // into update(). The work runs WITHOUT the GIL held; reacquire it
            // inside the callback before touching Python.
            return PCmd{ typename PCmd::Task{
                [fn](std::function<void(Msg)> dispatch) {
                    py::gil_scoped_acquire gil;
                    auto py_dispatch = py::cpp_function(
                        [dispatch](Msg m) { dispatch(std::move(m)); });
                    fn(py_dispatch);
                }
            }};
        },
        py::arg("fn"),
        "Run fn(dispatch) on a background worker; call dispatch(msg) to feed\n"
        "a result back into update(). For short async work (fetch, IO).");

    cmd.def_static("isolated_task",
        [](py::function fn) {
            return PCmd{ typename PCmd::IsolatedTask{
                [fn](std::function<void(Msg)> dispatch) {
                    py::gil_scoped_acquire gil;
                    auto py_dispatch = py::cpp_function(
                        [dispatch](Msg m) { dispatch(std::move(m)); });
                    fn(py_dispatch);
                }
            }};
        },
        py::arg("fn"),
        "Like task() but on a dedicated detached thread — for work that may\n"
        "wedge on a blocking syscall (slow mounts, hung subprocess).");

    cmd.def_static("commit_scrollback",
        [](int rows) { return PCmd::commit_scrollback(rows); },
        py::arg("rows"),
        "Mark the top `rows` rows of the last inline frame as scrollback.");

    cmd.def_static("commit_scrollback_overflow", &PCmd::commit_scrollback_overflow,
        "Commit all inline rows that have provably overflowed the viewport.");

    cmd.def_static("force_redraw", &PCmd::force_redraw,
        "Soft repaint of the live viewport (Ctrl-L style).");

    cmd.def_static("reset_inline", &PCmd::reset_inline,
        "Hard inline reset (wipes viewport + saved-lines). For wholesale\n"
        "content swaps (thread switch / new thread).");

    // ── Sub ─────────────────────────────────────────────────────────────
    py::class_<PSub> sub(m, "Sub",
        "A declarative event source. subscribe(model) returns a Sub; the\n"
        "runtime turns matching events into messages. Same as maya's Sub<Msg>.");

    sub.def_static("none", &PSub::none, "No subscriptions.");

    sub.def_static("batch",
        [](py::args subs) {
            std::vector<PSub> v;
            v.reserve(subs.size());
            for (auto s : subs) v.push_back(s.cast<PSub>());
            return PSub::batch(std::move(v));
        },
        "Combine several subscriptions.");

    sub.def_static("on_key",
        [](py::function f) {
            return PSub::on_key([f](const KeyEvent& k) -> std::optional<Msg> {
                py::gil_scoped_acquire gil;
                py::object r = f(PyEvent{Event{k}});
                if (r.is_none()) return std::nullopt;
                return r;
            });
        },
        py::arg("filter"),
        "filter(event) -> msg | None. Called on key events; return a message\n"
        "to dispatch, or None to ignore.");

    sub.def_static("on_mouse",
        [](py::function f) {
            return PSub::on_mouse([f](const MouseEvent& me) -> std::optional<Msg> {
                py::gil_scoped_acquire gil;
                py::object r = f(PyEvent{Event{me}});
                if (r.is_none()) return std::nullopt;
                return r;
            });
        },
        py::arg("filter"),
        "filter(event) -> msg | None for mouse events.");

    sub.def_static("on_resize",
        [](py::function f) {
            return PSub::on_resize([f](Size sz) -> Msg {
                py::gil_scoped_acquire gil;
                return f(sz.width, sz.height);
            });
        },
        py::arg("fn"),
        "fn(width, height) -> msg on terminal resize.");

    sub.def_static("on_paste",
        [](py::function f) {
            return PSub::on_paste([f](std::string s) -> Msg {
                py::gil_scoped_acquire gil;
                return f(s);
            });
        },
        py::arg("fn"),
        "fn(text) -> msg on bracketed paste.");

    sub.def_static("every",
        [](double ms, Msg msg) {
            return PSub::every(std::chrono::milliseconds((long)ms), std::move(msg));
        },
        py::arg("ms"), py::arg("msg"),
        "Emit `msg` every `ms` milliseconds (animation / polling).");

    sub.def_static("on_animation_frame",
        [](Msg msg) { return PSub::on_animation_frame(std::move(msg)); },
        py::arg("msg"),
        "Emit `msg` at ~60fps (16ms). Sugar for every(16, msg).");
}

// ── run_program — the maya MVU loop, replicated for Python ──────────────────

static void run_program(py::object init_fn,
                        py::object update_fn,
                        py::object view_fn,
                        py::object subscribe_fn,
                        const std::string& title,
                        bool inline_mode,
                        bool mouse,
                        int fps) {
    RunConfig cfg{};
    cfg.title = title;
    cfg.mouse = mouse;
    cfg.fps   = fps;
    cfg.mode  = inline_mode ? Mode::Inline : Mode::Fullscreen;

    // init() → (model, Cmd) or model
    py::object model;
    PCmd init_cmd = PCmd::none();
    {
        py::object r = init_fn();
        auto [m, c] = split_model_cmd(r);
        model    = m;
        init_cmd = c;
    }

    // Belt-and-suspenders mouse-off on every exit path (a throwing Python
    // callback unwinds through here). Idempotent with maya's own off-emit.
    struct MouseGuard {
        bool on;
        ~MouseGuard() {
            if (on) {
                // Cross-platform terminal write (POSIX fd / Win32 HANDLE).
                (void)maya::platform::io_write_all(
                    maya::platform::stdout_handle(),
                    "\x1b[?1007l\x1b[?1006l\x1b[?1002l\x1b[?1000l");
            }
        }
    } mouse_guard{mouse};

    auto result = detail::Runtime::create(cfg);
    if (!result) {
        throw std::runtime_error("maya: failed to initialize terminal: "
                                 + result.error().message);
    }
    auto rt = std::move(*result);

    // Background queue for Cmd::task / Cmd::isolated_task dispatch.
    std::shared_ptr<detail::BackgroundQueue<Msg>> bg_queue;
    if (auto bgq = detail::BackgroundQueue<Msg>::create()) {
        bg_queue = std::move(*bgq);
    } else {
        bg_queue = std::make_shared<detail::BackgroundQueue<Msg>>(
            platform::NativeWakeFd{});
    }
    rt.set_wake_handle(bg_queue->wake_handle());

    std::vector<Msg> pending_msgs;
    std::vector<typename detail::CmdContext<Msg>::TimerEntry> timers;
    detail::CmdContext<Msg> ctx{rt, pending_msgs, timers, bg_queue};

    // Drain pending messages through update(). GIL must be held: this runs
    // Python. The C++ run<P> drain loop, line-for-line.
    auto drain_pending = [&] {
        while (!pending_msgs.empty()) {
            auto msgs = std::move(pending_msgs);
            pending_msgs.clear();
            for (auto& msg : msgs) {
                py::object r = update_fn(model, msg);
                auto [new_model, cmd] = split_model_cmd(r);
                model = new_model;
                detail::execute_cmd(cmd, ctx);
            }
        }
    };

    auto get_sub = [&]() -> PSub { return call_subscribe(subscribe_fn, model); };

    // Startup effects.
    if (!init_cmd.is_none()) {
        detail::execute_cmd(init_cmd, ctx);
        drain_pending();
    }

    PSub current_sub = get_sub();

    // Initial resize so view() knows the terminal size.
    {
        auto sz = rt.size();
        Event ev{ResizeEvent{sz.width, sz.height}};
        detail::dispatch_through_sub(current_sub, ev, pending_msgs);
        drain_pending();
        current_sub = get_sub();
    }

    bool needs_render = true;
    auto next_frame_at = std::chrono::steady_clock::time_point{};

    // GIL is held on entry (pybind). We release it ONLY across rt.poll()
    // (the blocking wait) and reacquire for everything that touches Python.
    while (rt.is_running()) {
        // PyErr / KeyboardInterrupt check each iteration.
        if (PyErr_CheckSignals() != 0) throw py::error_already_set();

        auto poll_timeout = needs_render
            ? std::chrono::milliseconds(0)
            : std::chrono::milliseconds(100);
        if (!needs_render && cfg.fps > 0)
            poll_timeout = std::chrono::milliseconds(1000 / std::max(1, cfg.fps));
        if (rt.has_pending_writes())
            poll_timeout = std::min(poll_timeout, std::chrono::milliseconds(8));
        if (rt.has_pending_input())
            poll_timeout = std::min(poll_timeout, std::chrono::milliseconds(16));
        if (!timers.empty()) {
            auto now = std::chrono::steady_clock::now();
            for (auto& t : timers) {
                auto until = std::chrono::duration_cast<std::chrono::milliseconds>(
                    t.fire_at - now);
                poll_timeout = std::min(poll_timeout,
                    std::max(std::chrono::milliseconds(0), until));
            }
        }
        if (!needs_render
            && next_frame_at != std::chrono::steady_clock::time_point{}) {
            auto now = std::chrono::steady_clock::now();
            auto until = std::chrono::duration_cast<std::chrono::milliseconds>(
                next_frame_at - now);
            poll_timeout = std::min(poll_timeout,
                std::max(std::chrono::milliseconds(0), until));
        }

        // Blocking wait — release the GIL so Ctrl-C and BG threads run.
        maya::detail::Runtime::PollResult pr;
        {
            py::gil_scoped_release nogil;
            auto poll_result = rt.poll(poll_timeout);
            if (!poll_result) break;
            pr = *poll_result;
        }

        if (pr.resize) {
            rt.handle_resize();
            for (;;) {
                py::gil_scoped_release nogil;
                auto more = rt.poll(std::chrono::milliseconds(0));
                if (!more || !more->resize) break;
                rt.handle_resize();
            }
            auto sz = rt.size();
            Event ev{ResizeEvent{sz.width, sz.height}};
            detail::dispatch_through_sub(current_sub, ev, pending_msgs);
            needs_render = true;
        }

        if (pr.input) {
            auto events = rt.read_events();
            if (!events) break;
            for (auto& ev : *events) {
                for (auto* s : detail::live_scroll_states())
                    if (s && s->auto_dispatch) (void)s->handle_event(ev);
                detail::dispatch_through_sub(current_sub, ev, pending_msgs);
            }
        }

        if (pr.wake) bg_queue->drain_wake();
        for (auto& msg : bg_queue->drain()) pending_msgs.push_back(std::move(msg));

        for (auto& ev : rt.flush_timeouts()) {
            for (auto* s : detail::live_scroll_states())
                if (s && s->auto_dispatch) (void)s->handle_event(ev);
            detail::dispatch_through_sub(current_sub, ev, pending_msgs);
        }

        if (!pending_msgs.empty()) { drain_pending(); needs_render = true; }

        // Expired one-shot/interval timers.
        {
            auto now = std::chrono::steady_clock::now();
            for (auto it = timers.begin(); it != timers.end(); ) {
                if (now >= it->fire_at) {
                    pending_msgs.push_back(std::move(it->msg));
                    it = timers.erase(it);
                } else { ++it; }
            }
            if (!pending_msgs.empty()) { drain_pending(); needs_render = true; }
        }

        if (cfg.fps > 0) needs_render = true;

        if (next_frame_at != std::chrono::steady_clock::time_point{}
            && std::chrono::steady_clock::now() >= next_frame_at)
            needs_render = true;

        // Reconcile Sub::every timers every iteration (the C++ invariant:
        // exactly one armed timer per interval at all times).
        current_sub = get_sub();
        {
            auto now = std::chrono::steady_clock::now();
            std::vector<std::pair<std::chrono::milliseconds, Msg>> specs;
            detail::collect_timers(current_sub, specs);
            for (auto& [interval, msg] : specs) {
                if (interval.count() <= 0) continue;
                bool armed = false;
                for (auto& t : timers)
                    if (t.interval == interval) { armed = true; break; }
                if (!armed)
                    timers.push_back({detail::saturate_add(now, interval),
                                      std::move(msg), interval});
            }
        }

        if (needs_render) {
            current_sub = get_sub();
            bool skip_render = false;
            if (rt.has_pending_writes()) skip_render = false;
            if (detail::animation_requested_) skip_render = false;
            if (!skip_render) detail::animation_requested_ = false;

            if (!skip_render) {
                py::object r = view_fn(model);
                if (!py::isinstance<Element>(r))
                    throw py::type_error(
                        "Program.view must return a maya Element, got "
                        + std::string(py::str(r.get_type().attr("__name__"))));
                Element view_root = r.cast<Element>();
                auto status = rt.render(view_root);
                if (!status) break;
            }
            needs_render = false;

            if (!skip_render) {
                next_frame_at = detail::animation_requested_
                    ? std::chrono::steady_clock::now() + detail::kAnimationFrameInterval
                    : std::chrono::steady_clock::time_point{};
            } else if (next_frame_at != std::chrono::steady_clock::time_point{}) {
                next_frame_at = std::chrono::steady_clock::now()
                              + detail::kAnimationFrameInterval;
            }
            if (detail::scroll_writeback_dirty) {
                detail::scroll_writeback_dirty = false;
                needs_render = true;
            }
            if (rt.has_pending_writes()) needs_render = true;
        }
    }

    (void)rt.cleanup();
}

void init_program(py::module_& m) {
    bind_cmd_sub(m);

    m.def("run_program", &run_program,
          py::arg("init"), py::arg("update"), py::arg("view"),
          py::arg("subscribe") = py::none(),
          py::arg("title") = "", py::arg("inline_mode") = false,
          py::arg("mouse") = false, py::arg("fps") = 0,
          "Run a maya Program: pure init/update/view/subscribe over Model+Msg.\n"
          "  init()              -> model | (model, Cmd)\n"
          "  update(model, msg)  -> model | (model, Cmd)\n"
          "  view(model)         -> Element\n"
          "  subscribe(model)    -> Sub      (optional)\n"
          "This is maya's full MVU runtime — same loop as C++ run<P>.");
}
