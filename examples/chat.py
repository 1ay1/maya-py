"""chat.py — AI Agent Session Demo (inline mode).

A faithful port of maya's `examples/chat.cpp`. A timeline-driven, auto-playing
agent session that streams an AI response character-by-character and showcases
every tool widget: user/assistant messages, a thinking block, read/search/
edit/write/bash/agent/fetch tool calls, a permission prompt, a plan checklist,
a diff view, streaming markdown, callouts, and toasts — all native maya
widgets. Just watch; press q/Esc to quit.

    PYTHONPATH=src python examples/chat.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from maya_py import (  # noqa: E402
    App, T, col, spacer,
    user_message, assistant_message, thinking, tool_call, plan_view,
    diff_view, markdown, callout, toast, phase_chip,
)


class ChatApp:
    def __init__(self):
        self.clock = 0.0
        self.next_event = 0
        self.frozen = []  # committed conversation Elements (builders, lazily built)
        self.toasts = []  # [message, level, ttl]
        # streaming
        self.md_target = ""
        self.md_cursor = 0
        self.streaming = False
        self.stream_rate = 120.0
        self.stream_accum = 0.0
        # live widget state
        self.thinking_content = ""
        self.thinking_active = False
        self.show_thinking = False
        self.show_permission = False
        self.show_streaming = False
        self.frame = 0
        # activity
        self.tokens_in = 0
        self.tokens_out = 0
        self.context_pct = 5
        self.status = ""
        self.build_timeline()

    def build_timeline(self):
        self.timeline = []
        t = 0.5
        seq = [
            (1,), (0.8, 2), (1.5, 3), (0.8, 4), (0.8, 5), (0.3, 6), (1.0, 7),
            (0.6, 8), (0.6, 9), (0.8, 10), (2.0, 11), (0.3, 12), (0.8, 13),
            (0.5, 14), (6.0, 15),
            (1.5, 20), (0.8, 21), (1.2, 22), (1.5, 23), (0.3, 24), (5.0, 99),
        ]
        # first entry fires at 0.5 with id 1
        self.timeline.append((t, 1))
        for entry in seq[1:]:
            t += entry[0]
            self.timeline.append((t, entry[1]))


APP = ChatApp()


def add_toast(msg, level):
    APP.toasts.append([msg, level, 3.0])


def freeze(el):
    APP.frozen.append(el)


def fire_event(eid):
    a = APP
    if eid == 1:
        freeze(user_message(
            "Add dark mode support to the settings page. Make sure the "
            "toggle persists across sessions and all components respect the theme."))
        a.tokens_in, a.tokens_out = 156, 0
        a.context_pct = 8
        add_toast("Message sent", "info")
    elif eid == 2:
        a.show_thinking = True
        a.thinking_active = True
        a.thinking_content = (
            "The user wants dark mode for the settings page.\n"
            "I need to understand the current theme system first.\n"
            "Let me read the theme config and find color references.")
        a.status = "Thinking..."
    elif eid == 3:
        freeze(tool_call("src/theme/config.ts", kind="read", status="completed",
                         elapsed=0.2, expanded=True, content=markdown(
            "```ts\nexport interface ThemeConfig {\n"
            "  primary: string;\n  background: string;\n  surface: string;\n"
            "  text: string;\n  textSecondary: string;\n}\n\n"
            "export const lightTheme: ThemeConfig = {\n"
            "  primary: '#6366f1',\n  background: '#ffffff',\n"
            "  surface: '#f8fafc',\n  text: '#0f172a',\n"
            "  textSecondary: '#64748b',\n};\n```")))
        a.tokens_out = 240
        a.context_pct = 12
        add_toast("Read src/theme/config.ts", "success")
    elif eid == 4:
        freeze(tool_call("backgroundColor|surface|primary", kind="search",
                         status="completed", elapsed=0.4, expanded=True,
                         content=markdown(
            "**src/components/Settings.tsx**\n"
            "- `12:` backgroundColor: theme.background,\n"
            "- `28:` color: theme.primary,\n"
            "- `45:` backgroundColor: theme.surface,\n\n"
            "**src/components/Sidebar.tsx**\n"
            "- `8:` backgroundColor: theme.surface,\n"
            "- `19:` borderColor: theme.primary,\n\n"
            "**src/App.tsx**\n"
            "- `34:` <ThemeProvider value={lightTheme}>")))
        a.tokens_out = 380
        a.context_pct = 15
    elif eid == 5:
        a.thinking_active = False
        a.show_thinking = False
        freeze(thinking(a.thinking_content, active=False, expanded=True))
        a.status = ""
    elif eid == 6:
        freeze(plan_view([
            ("Read current theme configuration", "completed"),
            ("Search for color references across components", "completed"),
            ("Create dark theme configuration", "in_progress"),
            ("Add theme toggle to Settings page", "pending"),
            ("Persist preference in localStorage", "pending"),
            ("Run tests to verify", "pending"),
        ]))
        add_toast("Plan created", "info")
    elif eid == 7:
        freeze(tool_call("src/**/*.css", kind="search", status="completed",
                         elapsed=0.1, expanded=True, content=markdown(
            "4 files matched\n"
            "- src/styles/global.css\n- src/styles/settings.css\n"
            "- src/styles/components.css\n- src/styles/animations.css")))
    elif eid == 8:
        freeze(diff_view("src/theme/config.ts",
            "@@ -1,4 +1,12 @@\n"
            " export const lightTheme: ThemeConfig = {\n"
            "   primary: '#6366f1',\n"
            "   background: '#ffffff',\n"
            " };\n"
            "+\n"
            "+export const darkTheme: ThemeConfig = {\n"
            "+  primary: '#818cf8',\n"
            "+  background: '#0f172a',\n"
            "+  surface: '#1e293b',\n"
            "+  text: '#f1f5f9',\n"
            "+  textSecondary: '#94a3b8',\n"
            "+};\n"))
        a.tokens_out = 520
        a.context_pct = 22
        add_toast("Edited src/theme/config.ts", "success")
    elif eid == 9:
        freeze(tool_call("src/hooks/useTheme.ts", kind="edit", status="completed",
                         elapsed=0.1, expanded=True, content=markdown(
            "```ts\nimport { useState, useEffect } from 'react';\n"
            "import { lightTheme, darkTheme } from '../theme/config';\n\n"
            "export function useTheme() {\n"
            "  const [mode, setMode] = useState(() =>\n"
            "    localStorage.getItem('theme') || 'light'\n  );\n\n"
            "  useEffect(() => localStorage.setItem('theme', mode), [mode]);\n\n"
            "  const theme = mode === 'dark' ? darkTheme : lightTheme;\n"
            "  const toggle = () => setMode(m => m === 'dark' ? 'light' : 'dark');\n"
            "  return { theme, mode, toggle };\n}\n```")))
        a.tokens_out = 680
        a.context_pct = 26
        add_toast("Created src/hooks/useTheme.ts", "success")
    elif eid == 10:
        a.show_permission = True
        a.status = "Awaiting permission..."
    elif eid == 11:
        a.show_permission = False
        a.status = ""
        add_toast("Permission granted", "success")
    elif eid == 12:
        freeze(tool_call("npm test -- --run src/hooks/useTheme.test.ts",
                         kind="execute", status="completed", elapsed=3.8,
                         expanded=True, content=markdown(
            "```\n PASS  src/hooks/useTheme.test.ts\n  useTheme\n"
            "    ✓ defaults to light theme (3ms)\n"
            "    ✓ toggles to dark theme (1ms)\n"
            "    ✓ persists preference in localStorage (2ms)\n"
            "    ✓ loads saved preference on mount (1ms)\n\n"
            "Test Suites: 1 passed, 1 total\n"
            "Tests:       4 passed, 4 total\nTime:        1.24s\n```")))
        a.tokens_out = 820
        a.context_pct = 30
    elif eid == 13:
        freeze(diff_view("src/components/Settings.tsx",
            "@@ -1,6 +1,8 @@\n"
            " import React from 'react';\n"
            "-import { lightTheme } from '../theme/config';\n"
            "+import { useTheme } from '../hooks/useTheme';\n"
            " \n"
            " export function Settings() {\n"
            "-  const theme = lightTheme;\n"
            "+  const { theme, mode, toggle } = useTheme();\n"
            "+\n"
            "+  // Dark mode toggle persists via localStorage\n"
            "   return (\n"))
    elif eid == 14:
        a.streaming = True
        a.md_cursor = 0
        a.stream_accum = 0.0
        a.stream_rate = 140.0
        a.show_streaming = True
        a.md_target = (
            "I've added dark mode support to the settings page. Here's what I did:\n\n"
            "## Changes\n\n"
            "1. **Created `darkTheme`** in `src/theme/config.ts` with accessible dark colors\n"
            "2. **Created `useTheme` hook** in `src/hooks/useTheme.ts` that:\n"
            "   - Persists the user's preference in `localStorage`\n"
            "   - Provides `theme`, `mode`, and `toggle` to components\n"
            "3. **Updated `Settings.tsx`** to use the new hook instead of hardcoded `lightTheme`\n\n"
            "All **4 tests pass** for the new `useTheme` hook.\n\n"
            "```tsx\nconst { theme, mode, toggle } = useTheme();\n```\n\n"
            "> To add the toggle UI, create a switch component that calls `toggle()` on click.\n")
        a.status = "Generating..."
    elif eid == 15:
        freeze(callout("All changes applied",
                       "3 files modified, 4 tests passing", kind="success"))
        a.tokens_out = 1050
        a.context_pct = 38
    elif eid == 20:
        freeze(user_message(
            "Can you check the accessibility contrast ratios for the dark "
            "mode colors? I want to meet WCAG AA."))
        a.tokens_in, a.tokens_out = 1240, 890
        a.context_pct = 42
        add_toast("Message sent", "info")
    elif eid == 21:
        a.show_thinking = True
        a.thinking_active = True
        a.thinking_content = (
            "User wants WCAG AA contrast verification.\n"
            "I should check the contrast ratios programmatically.\n"
            "Let me spawn a sub-agent to research the requirements.")
        a.status = "Thinking..."
    elif eid == 22:
        freeze(tool_call("Researching WCAG AA contrast requirements", kind="agent",
                         status="completed", elapsed=4.1, expanded=True,
                         content=col(
            tool_call("docs/wcag-guidelines.md", kind="read", status="completed",
                      elapsed=0.3),
            tool_call("https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum",
                      kind="fetch", status="completed", elapsed=1.2),
            gap=0)))
        a.tokens_in, a.tokens_out = 1240, 1320
        a.context_pct = 48
        a.status = "Thinking..."
    elif eid == 23:
        a.thinking_active = False
        a.show_thinking = False
        freeze(thinking(a.thinking_content, active=False, expanded=True))
        a.status = ""
    elif eid == 24:
        a.streaming = True
        a.md_cursor = 0
        a.stream_accum = 0.0
        a.stream_rate = 120.0
        a.show_streaming = True
        a.md_target = (
            "I checked the contrast ratios for the dark mode palette against "
            "WCAG AA (minimum 4.5:1 for normal text, 3:1 for large text):\n\n"
            "| Color Pair | Ratio | Status |\n|---|---|---|\n"
            "| `text` on `background` | **15.4:1** | Pass |\n"
            "| `textSecondary` on `background` | **7.2:1** | Pass |\n"
            "| `primary` on `background` | **5.8:1** | Pass |\n"
            "| `text` on `surface` | **11.3:1** | Pass |\n\n"
            "All color combinations **meet WCAG AA** standards. The dark "
            "theme is comfortable for extended reading.\n")
        a.status = "Generating..."
    elif eid == 99:
        a.tokens_in, a.tokens_out = 1240, 1580
        a.context_pct = 55
        add_toast("Session complete — press q to exit", "success")


def tick(dt):
    a = APP
    a.frame += 1
    a.clock += dt
    while (a.next_event < len(a.timeline)
           and a.clock >= a.timeline[a.next_event][0]):
        fire_event(a.timeline[a.next_event][1])
        a.next_event += 1

    if a.streaming and a.md_cursor < len(a.md_target):
        a.stream_accum += dt * a.stream_rate
        chars = int(a.stream_accum)
        if chars > 0:
            a.stream_accum -= chars
            a.md_cursor = min(a.md_cursor + chars, len(a.md_target))
    elif a.streaming and a.md_cursor >= len(a.md_target):
        a.streaming = False
        freeze(assistant_message(markdown(a.md_target)))
        a.show_streaming = False
        a.status = ""
        add_toast("Response complete", "success")

    for t in a.toasts:
        t[2] -= dt
    a.toasts[:] = [t for t in a.toasts if t[2] > 0]


# ── App ──────────────────────────────────────────────────────────────────────

app = App.inline("agent session", fps=30)
app.state(_t=0.0)


@app.on("q", "esc")
def _quit(s):
    app.stop()


@app.on_frame
def _frame(s, dt):
    tick(1.0 / 30.0)


@app.view
def view(s):
    a = APP
    parts = list(a.frozen)
    if a.show_thinking:
        parts.append(thinking(a.thinking_content, active=a.thinking_active, expanded=True))
    if a.show_permission:
        parts.append(tool_call("npm test -- --run src/hooks/useTheme.test.ts",
                               kind="execute", status="confirmation",
                               description="bash"))
    if a.show_streaming:
        shown = a.md_target[:a.md_cursor]
        parts.append(assistant_message(markdown(shown)))
    if a.toasts:
        parts.append(toast([(m, lvl) for m, lvl, _ in a.toasts]))
    # activity bar
    verb = a.status or "Idle"
    parts.append(phase_chip(verb.rstrip("."), glyph="✷", breathing=a.thinking_active,
                            frame=a.frame, elapsed=a.clock))
    return col(*parts, gap=0)


if __name__ == "__main__":
    app.run()
