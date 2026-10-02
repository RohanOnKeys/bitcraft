"""Boot screen: real provider stages, then auto-advance to dashboard."""

from __future__ import annotations

import time
from datetime import datetime

import textual
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, ProgressBar, RichLog, Static

from bitcraft.providers.factory import create_provider
from bitcraft.providers.models import ProviderError
from bitcraft.widgets.chart import ramp
from bitcraft.widgets.logo import Logo
from bitcraft.widgets.mini_frog import MiniFrog
from bitcraft.widgets.mascot import NATIVE_WIDTH, Mascot

SHIMMER_WIDTH = 48
SHIMMER_TAIL = 14

BOOT_STAGES = (
    "Environment",
    "Data source",
    "Pipeline status",
    "Summary statistics",
    "Alert index",
    "Communities",
    "Threat overview",
)


class BootScreen(Screen):
    """Staged loading over real provider calls. Never fakes ML training."""

    BINDINGS = [
        ("r", "retry", "Retry"),
        ("m", "demo_fallback", "Demo"),
        ("q", "app.quit", "Quit"),
    ]

    shimmer_offset: reactive[int] = reactive(0)
    _failed: bool = False
    _finished: bool = False
    _started_at: float = 0.0
    _stage_results: list[str]

    def compose(self) -> ComposeResult:
        with Vertical(id="boot"):
            with Horizontal(id="boot-brand"):
                yield Mascot("thinking", art_width=NATIVE_WIDTH, id="boot-mascot")
                yield Logo(show_tagline=False, id="boot-logo")
            yield Static("", id="boot-shimmer")
            yield ProgressBar(total=len(BOOT_STAGES), id="boot-progress", show_eta=False)
            with Horizontal(id="boot-log-row"):
                yield MiniFrog(seed=10, classes="mini-frog")
                yield RichLog(id="boot-log", markup=True, highlight=False)
                yield MiniFrog(seed=11, classes="mini-frog")
            yield Static("", id="boot-hint")
        yield Footer()

    def on_mount(self) -> None:
        self._stage_results = []
        self._started_at = time.monotonic()
        self.set_interval(1 / 12, self._tick_shimmer)
        self.run_worker(self._run_stages, exclusive=True, thread=True)

    def _tick_shimmer(self) -> None:
        self.shimmer_offset = (self.shimmer_offset + 1) % SHIMMER_WIDTH
        text = Text(no_wrap=True, end="")
        for i in range(SHIMMER_WIDTH):
            # Distance behind the moving head, wrapping around the track.
            d = (self.shimmer_offset - i) % SHIMMER_WIDTH
            if d < SHIMMER_TAIL:
                text.append("━", Style(color=ramp(1 - d / SHIMMER_TAIL), bold=d == 0))
            else:
                text.append("━", Style(color="#1c1814"))
        self.query_one("#boot-shimmer", Static).update(text)

    def _log(self, line: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.app.call_from_thread(
            self.query_one("#boot-log", RichLog).write, f"{stamp}  {line}"
        )

    def _set_progress(self, value: float) -> None:
        self.app.call_from_thread(
            setattr, self.query_one("#boot-progress", ProgressBar), "progress", value
        )

    def _set_mood(self, mood: str) -> None:
        self.app.call_from_thread(
            self.query_one("#boot-mascot", Mascot).set_base, mood
        )

    def _set_hint(self, text: str) -> None:
        self.app.call_from_thread(
            self.query_one("#boot-hint", Static).update, text
        )

    def _run_stages(self) -> None:
        store = self.app.store
        provider = store.provider
        ok_count = 0
        try:
            # 1 Environment
            self._log("[..] Environment")
            t0 = time.monotonic()
            size = self.app.size
            self._log(
                f"[ok] Environment  textual {textual.__version__}  "
                f"size {size.width}x{size.height}  offline  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            # 2 Data source
            self._log("[..] Data source")
            t0 = time.monotonic()
            health = provider.health()
            for line in store.boot_log:
                if "demo" not in line.lower():
                    self._log(line)
            source = provider.source_label
            if source == "DEMO DATA":
                source = "local snapshot"
            self._log(
                f"[ok] Data source  {source}  "
                f"health={health.status}  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            # 3 Pipeline
            self._log("[..] Pipeline status")
            t0 = time.monotonic()
            store.pipeline = provider.pipeline_status()
            self._log(
                f"[ok] Pipeline status  {store.pipeline.status}  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            # 4 Stats
            self._log("[..] Summary statistics")
            t0 = time.monotonic()
            store.stats = provider.stats_summary()
            self._log(
                f"[ok] Summary statistics  "
                f"tx={store.stats.total_transactions:,}  "
                f"alerts={store.stats.total_alerts:,}  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            # 5 Alerts
            self._log("[..] Alert index")
            t0 = time.monotonic()
            store.alert_page = provider.alerts(store.filters.to_query())
            self._log(
                f"[ok] Alert index  page={len(store.alert_page.items)}  "
                f"total={store.alert_page.total:,}  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            # 6 Communities
            self._log("[..] Communities")
            t0 = time.monotonic()
            store.communities = provider.top_communities(25)
            self._log(
                f"[ok] Communities  n={len(store.communities)}  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            # 7 Threat overview
            self._log("[..] Threat overview")
            t0 = time.monotonic()
            store.threat_overview = provider.threat_overview()
            self._log(
                f"[ok] Threat overview  "
                f"critical={store.threat_overview.critical_count}  "
                f"{int((time.monotonic() - t0) * 1000)}ms"
            )
            ok_count += 1
            self._set_progress(ok_count)

            store.boot_complete = True
            self._finished = True
            self._set_mood("happy")
            min_s = 0.0 if store.fast_boot else 1.2
            elapsed = time.monotonic() - self._started_at
            if elapsed < min_s:
                time.sleep(min_s - elapsed)
            self._set_hint("ready  (any key to continue)")
            self.app.call_from_thread(self._advance)

        except ProviderError as exc:
            self._failed = True
            store.last_error = str(exc)
            self._log(f"[!!] {exc}")
            self._set_mood("confused")
            self._set_hint("[r] retry    [m] continue in demo    [q] quit")
        except Exception as exc:  # noqa: BLE001
            self._failed = True
            store.last_error = str(exc)
            self._log(f"[!!] {exc}")
            self._set_mood("confused")
            self._set_hint("[r] retry    [m] continue in demo    [q] quit")

    def _advance(self) -> None:
        """Leave boot and show the populated dashboard mode."""
        store = self.app.store
        if not store.boot_complete:
            return
        if isinstance(self.app.screen, BootScreen):
            self.app.pop_screen()
        self.app.switch_mode("dashboard")

    def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
        """Any key skips ahead once stages finished."""
        if self._finished and not self._failed:
            event.stop()
            self._advance()

    def action_retry(self) -> None:
        """Retry boot stages after a failure."""
        if not self._failed:
            return
        self._failed = False
        self.query_one("#boot-log", RichLog).clear()
        self.query_one("#boot-progress", ProgressBar).progress = 0
        self._set_hint("")
        self.query_one("#boot-mascot", Mascot).set_base("thinking")
        self.run_worker(self._run_stages, exclusive=True, thread=True)

    def action_demo_fallback(self) -> None:
        """Switch store to demo provider and retry."""
        if not self._failed:
            return
        choice = create_provider(source="demo")
        store = self.app.store
        store.provider = choice.provider
        store.boot_log = list(choice.boot_log)
        store.is_demo = True
        self.action_retry()
