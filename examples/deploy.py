"""deploy.py — CI/CD Deployment Pipeline Dashboard.

A faithful port of maya's ``examples/deploy.cpp``. A real-time animated
deployment pipeline dashboard showing multiple microservices being built,
tested, and deployed across three environments. Multiple services advance
through five pipeline stages (Build → Test → Security Scan → Deploy →
Health Check) in parallel deploy waves; stages can fail, be force-deployed
past failures, or be rolled back. A live build log, sparkline metrics, and a
pipeline-health bar round it out — all rendered with maya's native widgets.

  Controls:
    space   trigger new deployment wave
    r       rollback last deployment
    f       force-deploy (skip failed stages)
    1       switch to dev environment
    2       switch to staging environment
    3       switch to prod environment
    q/Esc   quit

    PYTHONPATH=src python examples/deploy.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, row, card, spacer, grow, sparkline, clamp, randf, randi, spin, bar, keyhints,
)


# -- Helpers -----------------------------------------------------------------

# -- Pipeline stage status ---------------------------------------------------

PENDING = 0
RUNNING = 1
SUCCESS = 2
FAILED = 3
SKIPPED = 4
ROLLING_BACK = 5


class Stage:
    __slots__ = ("name", "status", "progress", "elapsed", "duration", "fail_chance")

    def __init__(self, name, duration, fail_chance):
        self.name = name
        self.status = PENDING
        self.progress = 0.0
        self.elapsed = 0.0
        self.duration = duration
        self.fail_chance = fail_chance


class Service:
    __slots__ = ("name", "icon", "stages", "current_stage", "deploying",
                 "rollback", "deploy_count", "total_time", "version")

    def __init__(self, name, icon, version):
        self.name = name
        self.icon = icon
        self.stages = []
        self.current_stage = -1
        self.deploying = False
        self.rollback = False
        self.deploy_count = 0
        self.total_time = 0.0
        self.version = version


# -- Environment -------------------------------------------------------------

DEV = 0
STAGING = 1
PROD = 2
ENV_NAMES = ["DEV", "STAGING", "PROD"]
ENV_COLORS = [
    (100, 200, 255),  # dev: blue
    (255, 200, 60),   # staging: yellow
    (255, 80, 80),    # prod: red
]


# -- Global state ------------------------------------------------------------

MAX_LOGS = 10
SPARK_SIZE = 24


class World:
    def __init__(self):
        self.services = []
        self.logs = []                 # [timestamp, msg, level]
        self.current_env = STAGING
        self.uptime = 0.0
        self.frame_count = 0
        self.total_deploys = 0
        self.total_failures = 0
        self.total_rollbacks = 0
        self.force_mode = False
        self.deploy_freq_history = []
        self.test_pass_history = []
        self.build_time_history = []


W = World()


def add_log(level, msg):
    W.logs.append([W.uptime, msg, level])
    if len(W.logs) > MAX_LOGS:
        W.logs.pop(0)


def fmt_time(secs):
    if secs < 0.1:
        return "0.0s"
    if secs < 60.0:
        return f"{secs:.1f}s"
    mins = int(secs) // 60
    s = int(secs) % 60
    return f"{mins}m{s:02d}s"


def make_version():
    return f"v{randi(1, 5)}.{randi(0, 12)}.{randi(0, 99)}"


# -- Stage templates per environment -----------------------------------------

def make_stages():
    mult = 1.5 if W.current_env == PROD else (1.0 if W.current_env == STAGING else 0.6)
    fail_mult = 0.5 if W.current_env == PROD else (1.5 if W.current_env == DEV else 1.0)
    return [
        Stage("Build",         randf(3.0, 8.0) * mult,  0.05 * fail_mult),
        Stage("Test",          randf(5.0, 15.0) * mult, 0.12 * fail_mult),
        Stage("Security Scan", randf(2.0, 6.0) * mult,  0.03 * fail_mult),
        Stage("Deploy",        randf(4.0, 10.0) * mult, 0.08 * fail_mult),
        Stage("Health Check",  randf(2.0, 5.0) * mult,  0.04 * fail_mult),
    ]


# -- Init --------------------------------------------------------------------

def init_services():
    W.services = [
        Service("api-gateway",   "🌐", "v2.4.1"),
        Service("auth-service",  "🔐", "v1.8.3"),
        Service("data-pipeline", "📊", "v3.1.0"),
        Service("web-frontend",  "🖥 ", "v4.2.7"),
        Service("ml-model",      "🤖", "v1.0.5"),
    ]
    W.deploy_freq_history = [0.0] * SPARK_SIZE
    W.test_pass_history = [0.85] * SPARK_SIZE
    W.build_time_history = [5.0] * SPARK_SIZE


# -- Deployment triggers -----------------------------------------------------

def start_deploy(svc):
    svc.stages = make_stages()
    svc.current_stage = 0
    svc.deploying = True
    svc.rollback = False
    svc.total_time = 0.0
    svc.version = make_version()
    svc.stages[0].status = RUNNING
    add_log(0, f"{svc.name} {svc.version}: deployment started [{ENV_NAMES[W.current_env]}]")


def trigger_deploy_wave():
    for svc in W.services:
        if not svc.deploying:
            start_deploy(svc)
    W.total_deploys += 1
    W.deploy_freq_history.pop(0)
    W.deploy_freq_history.append(float(W.total_deploys))


def trigger_rollback():
    for svc in W.services:
        if svc.deploying:
            svc.rollback = True
            for stage in svc.stages:
                if stage.status == RUNNING:
                    stage.status = ROLLING_BACK
            add_log(1, f"{svc.name}: rollback initiated")
    W.total_rollbacks += 1


# -- Tick (simulation) -------------------------------------------------------

LOG_MESSAGES = [
    "compiling 247 source files...",
    "linking shared libraries...",
    "running unit tests: 184/184 passed",
    "running integration tests: 42/45 passed",
    "scanning dependencies for vulnerabilities...",
    "CVE check: 0 critical, 2 low severity",
    "building Docker image sha256:a3f2...",
    "pushing to container registry...",
    "updating Kubernetes deployment...",
    "rolling update: 3/3 pods ready",
    "health endpoint /api/health: 200 OK",
    "latency p99: 42ms (threshold: 100ms)",
    "error rate: 0.02% (threshold: 1%)",
    "memory usage: 256MB / 512MB",
    "connection pool: 45/100 active",
    "cache hit ratio: 94.2%",
    "TLS certificate valid: 89 days remaining",
    "load balancer draining old instances...",
    "database migration: 3 pending changes applied",
    "static asset upload: 1.2MB compressed",
]


def tick(dt):
    W.uptime += dt
    W.frame_count += 1

    for svc in W.services:
        if not svc.deploying:
            continue
        if svc.current_stage < 0 or svc.current_stage >= len(svc.stages):
            continue

        stage = svc.stages[svc.current_stage]
        svc.total_time += dt

        if stage.status == ROLLING_BACK:
            stage.progress -= dt / (stage.duration * 0.5)
            if stage.progress <= 0.0:
                stage.progress = 0.0
                stage.status = SKIPPED
                svc.deploying = False
                svc.rollback = False
                add_log(1, f"{svc.name}: rollback complete")
            continue

        if stage.status == RUNNING:
            stage.elapsed += dt
            stage.progress = clamp(stage.elapsed / stage.duration, 0.0, 1.0)

            if randi(0, 40) == 0:
                add_log(0, f"{svc.name}/{stage.name}: {LOG_MESSAGES[randi(0, 19)]}")

            if stage.elapsed >= stage.duration:
                failed = randf(0.0, 1.0) < stage.fail_chance and not W.force_mode
                if failed:
                    stage.status = FAILED
                    stage.progress = stage.elapsed / stage.duration
                    svc.deploying = False
                    W.total_failures += 1
                    reason = (
                        "3 tests failed" if stage.name == "Test" else
                        "critical vulnerability detected" if stage.name == "Security Scan" else
                        "pod crash loop detected" if stage.name == "Deploy" else
                        "endpoint returned 503" if stage.name == "Health Check" else
                        "build error in module"
                    )
                    add_log(2, f"{svc.name}/{stage.name}: FAILED - {reason}")
                    W.test_pass_history.pop(0)
                    W.test_pass_history.append(randf(0.5, 0.8))
                else:
                    stage.status = SUCCESS
                    stage.progress = 1.0
                    add_log(3, f"{svc.name}/{stage.name}: completed in {fmt_time(stage.elapsed)}")
                    nxt = svc.current_stage + 1
                    if nxt < len(svc.stages):
                        svc.current_stage = nxt
                        svc.stages[nxt].status = RUNNING
                    else:
                        svc.deploying = False
                        svc.deploy_count += 1
                        add_log(3, f"{svc.name} {svc.version}: deployment successful! "
                                   f"({fmt_time(svc.total_time)})")
                        W.test_pass_history.pop(0)
                        W.test_pass_history.append(randf(0.85, 1.0))
                        W.build_time_history.pop(0)
                        W.build_time_history.append(svc.total_time)

    if W.force_mode and W.frame_count % 150 == 0:
        W.force_mode = False


# -- UI builders -------------------------------------------------------------

def status_color(s):
    return {
        PENDING:      (80, 80, 100),
        RUNNING:      (255, 200, 60),
        SUCCESS:      (0, 230, 118),
        FAILED:       (255, 60, 80),
        SKIPPED:      (120, 120, 140),
        ROLLING_BACK: (255, 140, 50),
    }.get(s, (80, 80, 100))


def status_icon(s, frame):
    return {
        PENDING:      "○",
        RUNNING:      spin(frame),
        SUCCESS:      "✓",
        FAILED:       "✗",
        SKIPPED:      "⊘",
        ROLLING_BACK: "↺",
    }.get(s, "?")


def build_header():
    glyph = spin(W.frame_count)
    ec = ENV_COLORS[W.current_env]

    phase = W.frame_count % 12
    blocks = ["░", "▒", "▓", "█", "▓", "▒"]
    grad = "".join(blocks[(i + phase) % 6] for i in range(6))

    parts = [
        T(glyph).fg((0, 200, 255)),
        T(" DEPLOY CONTROL").bold.fg((0, 200, 255)),
        T(" " + grad).fg((0, 150, 200)),
        spacer(),
        T("ENV:").dim,
        T(" " + ENV_NAMES[W.current_env]).fg(ec).bold,
    ]
    if W.force_mode:
        parts.append(T("  FORCE").bold.fg((255, 100, 50)))
    parts += [
        spacer(),
        T("deploys:").dim,
        T(str(W.total_deploys)).fg((100, 200, 255)),
        T("  failures:").dim,
        T(str(W.total_failures)).fg((255, 60, 80)),
        T("  rollbacks:").dim,
        T(str(W.total_rollbacks)).fg((255, 200, 60)),
    ]
    return row(*parts, gap=0, pad=(0, 1))


def build_stage_cell(stage, frame):
    col_sty = status_color(stage.status)
    icon = status_icon(stage.status, frame)

    time_str = ""
    if stage.status in (RUNNING, SUCCESS, FAILED, ROLLING_BACK):
        time_str = " " + fmt_time(stage.elapsed)

    pbar = ""
    if stage.status in (RUNNING, ROLLING_BACK):
        pbar = bar(stage.progress, 10, fill="█", track="─")
    elif stage.status == SUCCESS:
        pbar = bar(1.0, 10, fill="█", track="─")
    elif stage.status == FAILED:
        pbar = bar(stage.progress, 10, fill="█", track="─")

    parts = [row(T(icon).fg(col_sty), T(" " + stage.name).fg(col_sty).bold, gap=0)]

    if pbar:
        bar_col = ((255, 60, 80) if stage.status == FAILED else
                   (255, 140, 50) if stage.status == ROLLING_BACK else
                   (0, 230, 118) if stage.status == SUCCESS else
                   (255, 200, 60))
        parts.append(T(pbar).fg(bar_col))

    if time_str:
        parts.append(T(time_str).dim)

    return col(*parts, gap=0, pad=(0, 1, 0, 0))


def build_pipeline_panel():
    rows = []
    last = W.services[-1] if W.services else None

    for svc in W.services:
        svc_label = row(
            T(svc.icon),
            T(" " + svc.name).bold.fg((180, 190, 220)),
            T(" " + svc.version).dim,
            gap=0,
        )

        # Status badge
        any_running = any(s.status == RUNNING for s in svc.stages)
        any_failed = any(s.status == FAILED for s in svc.stages)
        any_rollback = any(s.status == ROLLING_BACK for s in svc.stages)
        all_success = bool(svc.stages) and all(s.status == SUCCESS for s in svc.stages)

        if any_rollback:
            badge_text, badge_col = "ROLLING BACK", (255, 140, 50)
        elif any_failed:
            badge_text, badge_col = "FAILED", (255, 60, 80)
        elif any_running:
            badge_text, badge_col = "DEPLOYING", (255, 200, 60)
        elif all_success:
            badge_text, badge_col = "LIVE", (0, 230, 118)
        else:
            badge_text, badge_col = "IDLE", (80, 80, 100)

        status_badge = T(f" [{badge_text}]").fg(badge_col).bold
        deploy_info = T(f" #{svc.deploy_count}").dim

        svc_row = row(svc_label, status_badge, deploy_info, gap=0)

        # Stage chain
        chain = []
        for i, st in enumerate(svc.stages):
            chain.append(build_stage_cell(st, W.frame_count))
            if i + 1 < len(svc.stages):
                arrow_col = (0, 230, 118) if st.status == SUCCESS else (60, 60, 80)
                chain.append(T(" → ").fg(arrow_col))
        chain_elem = row(*chain, gap=0) if chain else T("")

        rows.append(svc_row)
        rows.append(chain_elem)

        if svc is not last:
            rows.append(T("").dim)

    return card(*rows, title=" PIPELINE ", border_color=(0, 100, 140), pad=(0, 1))


def build_log_panel():
    rows = []
    for ts, msg, level in W.logs:
        mins = int(ts) // 60
        secs = int(ts) % 60
        if level == 1:
            tag, tag_sty = "WARN", T("WARN").fg((255, 200, 60)).bold
        elif level == 2:
            tag, tag_sty = "ERR ", T("ERR ").fg((255, 60, 80)).bold
        elif level == 3:
            tag, tag_sty = " OK ", T(" OK ").fg((0, 230, 118)).bold
        else:
            tag, tag_sty = "INFO", T("INFO").fg((80, 80, 100))
        rows.append(row(
            T(f"{mins:02d}:{secs:02d}").dim,
            tag_sty,
            T(msg).dim,
            gap=1,
        ))
    while len(rows) < MAX_LOGS:
        rows.append(T("").dim)

    return card(*rows, title=" BUILD LOG ", border_color=(40, 50, 65), pad=(0, 1))


def build_metrics_panel():
    deploy_spark = sparkline(W.deploy_freq_history, label="Deploy Freq",
                             color=(0, 200, 255), show_last=True)
    test_spark = sparkline(W.test_pass_history, label="Test Pass %",
                           color=(0, 230, 118), range_min=0.0, range_max=1.0,
                           show_last=True)
    build_spark = sparkline(W.build_time_history, label="Build Time ",
                            color=(255, 200, 60), show_last=True)

    active = succeeded = failed = 0
    for svc in W.services:
        for stage in svc.stages:
            if stage.status == RUNNING:
                active += 1
            if stage.status == SUCCESS:
                succeeded += 1
            if stage.status == FAILED:
                failed += 1
    denom = succeeded + failed + active
    health = (succeeded / denom) if denom > 0 else 1.0

    health_bar = bar(health, 16, fill="█", track="─")
    health_pct = int(health * 100)
    health_col = ((0, 230, 118) if health > 0.8 else
                  (255, 200, 60) if health > 0.5 else
                  (255, 60, 80))

    return card(
        deploy_spark,
        test_spark,
        build_spark,
        row(
            T("Health     ").fg((200, 204, 212)),
            T(health_bar).fg(health_col),
            T(f"  {health_pct}%").fg(health_col).bold,
            gap=0,
        ),
        title=" METRICS ", border_color=(40, 50, 65), pad=(0, 1),
    )


def build_status_bar():
    mins = int(W.uptime) // 60
    secs = int(W.uptime) % 60

    active = sum(1 for svc in W.services if svc.deploying)

    total_stages = 0
    completed = 0
    for svc in W.services:
        total_stages += len(svc.stages)
        for stage in svc.stages:
            if stage.status == SUCCESS:
                completed += 1
    overall = (completed / total_stages) if total_stages > 0 else 0.0
    overall_pct = int(overall * 100)

    return row(
        T(f" ⏱ {mins:02d}:{secs:02d}").fg((100, 180, 255)),
        T("  active:").fg((140, 140, 160)),
        T(str(active)).fg((255, 200, 60) if active > 0 else (80, 80, 100)),
        T("  progress:").fg((140, 140, 160)),
        T(f"{overall_pct}%").bold.fg((0, 200, 255)),
        spacer(),
        keyhints(("␣", "deploy"), ("r", "rollback"), ("f", "force"),
                 ("1-3", "env"), ("q", "quit ")),
        gap=0, pad=(0, 1), bg=(30, 30, 42),
    )


# -- App ---------------------------------------------------------------------

init_services()
trigger_deploy_wave()

app = App.fullscreen("deploy", fps=15)
app.state(_t=0.0)


@app.on("space")
def _deploy(s):
    trigger_deploy_wave()


@app.on("r")
def _rollback(s):
    trigger_rollback()


@app.on("f")
def _force(s):
    W.force_mode = not W.force_mode
    if W.force_mode:
        add_log(1, "FORCE MODE enabled - skipping failure checks")
    else:
        add_log(0, "FORCE MODE disabled")


@app.on("1")
def _dev(s):
    W.current_env = DEV
    add_log(0, "Switched to DEV environment")


@app.on("2")
def _staging(s):
    W.current_env = STAGING
    add_log(0, "Switched to STAGING environment")


@app.on("3")
def _prod(s):
    W.current_env = PROD
    add_log(1, "Switched to PROD environment - caution!")


app.quit_on("q", "esc")


app.simulate(tick)


@app.view
def view(s):
    return col(
        build_header(),
        build_pipeline_panel(),
        build_log_panel(),
        build_metrics_panel(),
        build_status_bar(),
        gap=0,
    )


if __name__ == "__main__":
    app.run()
