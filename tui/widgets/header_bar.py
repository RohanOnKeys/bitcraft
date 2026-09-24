"""Compact one-line header: wordmark, source badge, pipeline, clock."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class HeaderBar(Widget):
    """Dashboard/threat header. Full ASCII logo stays on splash and boot only."""

    DEFAULT_CSS = """
    HeaderBar {
        width: 100%;
        height: 1;
        background: #000000;
        color: #e6e6e6;
        dock: top;
    }
    HeaderBar #header-row {
        width: 100%;
        height: 1;
    }
    HeaderBar .wordmark {
        color: #d4af37;
        text-style: bold;
        width: auto;
        padding: 0 1;
    }
    HeaderBar .demo-badge {
        /* Meaning: demo data, not live pipeline output */
        color: #b3261e;
        text-style: bold;
        width: auto;
        padding: 0 1;
    }
    HeaderBar .api-badge {
        color: #d4af37;
        width: auto;
        padding: 0 1;
    }
    HeaderBar .pipeline-pill {
        color: #7a7a7a;
        width: 1fr;
    }
    HeaderBar .clock {
        color: #7a7a7a;
        width: auto;
        padding: 0 1;
    }
    """

    clock_text: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        store = self.app.store
        badge_class = "demo-badge" if store.is_demo else "api-badge"
        badge = store.source_label
        pipeline = store.pipeline
        pipe_txt = "pipeline: --"
        if pipeline is not None:
            pipe_txt = f"pipeline: {pipeline.status}"
            if pipeline.finished_at:
                pipe_txt = f"pipeline: {pipeline.status} @ {pipeline.finished_at}"
        with Horizontal(id="header-row"):
            yield Static("BITCRAFT", classes="wordmark")
            yield Static(f"[{badge}]", classes=badge_class, id="source-badge")
            yield Static(pipe_txt, classes="pipeline-pill", id="pipeline-pill")
            yield Static("--:--:--", classes="clock", id="header-clock")

    def on_mount(self) -> None:
        """Start the one-second clock tick."""
        self._tick()
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        try:
            self.query_one("#header-clock", Static).update(now)
        except Exception:
            pass
