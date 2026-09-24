"""Provider contract and navigation stack tests."""

from __future__ import annotations

import httpx
import pytest

from tui.app import BitCraftApp
from tui.api_client import ApiClient
from tui.helpers.drivers import primary_driver
from tui.helpers.severity import severity_for_score
from tui.providers.api_provider import ApiProvider
from tui.providers.demo_provider import (
    ALERT_COUNT,
    ANOMALY_WEIGHT,
    COMMUNITY_WEIGHT,
    FULL_STACK_COVERAGE_PCT,
    LABELED_COVERAGE_PCT,
    NETWORK_COVERAGE_PCT,
    NETWORK_WEIGHT,
    TOTAL_TRANSACTIONS,
    DemoProvider,
)
from tui.providers.factory import create_provider, resolve_source
from tui.providers.models import AlertQuery, ProviderError
from tui.screens.alert_detail import AlertDetailScreen
from tui.screens.boot import BootScreen
from tui.screens.dashboard import DashboardScreen
from tui.screens.graph_explorer import GraphExplorerScreen
from tui.screens.splash import SplashScreen
from tui.screens.threat_detection import CAVEAT, ThreatDetectionScreen
from tui.store import Store
from textual.widgets import Static


def _store() -> Store:
    return Store(
        provider=DemoProvider(simulate_latency=False),
        is_demo=True,
        fast_boot=True,
        boot_log=["test"],
    )


async def _boot_to_dashboard(app: BitCraftApp, pilot) -> None:
    await pilot.press("enter")
    for _ in range(200):
        if isinstance(app.screen, DashboardScreen) and app.store.boot_complete:
            return
        await pilot.pause(0.05)
    raise AssertionError("boot did not reach dashboard")


def test_demo_provider_deterministic() -> None:
    """Two DemoProvider instances with the same seed match exactly."""
    a = DemoProvider(seed=42, simulate_latency=False)
    b = DemoProvider(seed=42, simulate_latency=False)
    page_a = a.alerts(AlertQuery(limit=20))
    page_b = b.alerts(AlertQuery(limit=20))
    assert [r.elliptic_tx_id for r in page_a.items] == [
        r.elliptic_tx_id for r in page_b.items
    ]
    assert [r.composite_score for r in page_a.items] == [
        r.composite_score for r in page_b.items
    ]


def test_demo_ranks_monotonic_and_composite_weights() -> None:
    """Ranks strictly increase with descending composite; weights hold."""
    provider = DemoProvider(seed=42, simulate_latency=False)
    page = provider.alerts(AlertQuery(limit=ALERT_COUNT, offset=0))
    assert page.total == ALERT_COUNT
    scores = [r.composite_score for r in page.items]
    assert scores == sorted(scores, reverse=True)
    ranks = [r.rank for r in page.items]
    assert ranks == list(range(1, ALERT_COUNT + 1))
    for row in page.items[:50]:
        expected = (
            ANOMALY_WEIGHT * row.anomaly_score
            + COMMUNITY_WEIGHT * row.community_risk
            + NETWORK_WEIGHT * row.network_signal
        )
        assert abs(row.composite_score - expected) < 1e-9
        if not row.has_network_layer:
            assert row.network_signal == 0.0
        if row.has_network_layer:
            assert row.has_synthetic_layer


def test_demo_coverage_figures() -> None:
    """Coverage KPIs match plans/plan.md."""
    stats = DemoProvider(seed=42, simulate_latency=False).stats_summary()
    assert stats.total_transactions == TOTAL_TRANSACTIONS
    assert stats.total_alerts == ALERT_COUNT
    assert stats.labeled_coverage_pct == LABELED_COVERAGE_PCT
    assert stats.network_coverage_pct == NETWORK_COVERAGE_PCT
    assert stats.full_stack_coverage_pct == FULL_STACK_COVERAGE_PCT


def test_severity_thresholds() -> None:
    """Display-only severity tiers."""
    assert severity_for_score(0.80) == "critical"
    assert severity_for_score(0.60) == "high"
    assert severity_for_score(0.40) == "medium"
    assert severity_for_score(0.39) == "low"


def test_primary_driver_hand_built() -> None:
    """Driver tag follows the largest weighted contribution."""
    assert primary_driver(1.0, 0.0, 0.0) == "ANOMALY"
    assert primary_driver(0.0, 1.0, 0.0) == "COMMUNITY"
    assert primary_driver(0.0, 0.0, 1.0) == "NETWORK"
    # 0.60*0.5=0.30 vs 0.25*0.9=0.225 vs 0.15*1.0=0.15
    assert primary_driver(0.5, 0.9, 1.0) == "ANOMALY"


def test_community_unlabeled_ratio_is_none() -> None:
    """Communities with no labeled members use None, not 0.0."""
    provider = DemoProvider(seed=42, simulate_latency=False)
    unlabeled = [c for c in provider.top_communities(40) if c.illicit_ratio is None]
    assert unlabeled


def test_api_provider_health_and_missing_fields() -> None:
    """ApiProvider maps JSON and tolerates missing optional fields."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/alerts/1":
            return httpx.Response(
                200,
                json={
                    "elliptic_tx_id": 1,
                    "composite_score": 0.9,
                    "anomaly_score": 0.9,
                    "community_risk": 0.5,
                    "network_signal": 0.0,
                    "rank": 1,
                    "has_synthetic_layer": False,
                    "has_network_layer": False,
                    "evidence_text": "demo",
                },
            )
        if request.url.path == "/alerts":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "elliptic_tx_id": 1,
                            "composite_score": 0.9,
                            "anomaly_score": 0.9,
                            "community_risk": 0.5,
                            "network_signal": 0.0,
                            "rank": 1,
                            "has_synthetic_layer": False,
                            "has_network_layer": False,
                        }
                    ],
                    "total": 1,
                    "offset": 0,
                    "limit": 100,
                },
            )
        return httpx.Response(404, json={"detail": "missing"})

    client = ApiClient(transport=httpx.MockTransport(handler))
    provider = ApiProvider(client)
    assert provider.health().status == "ok"
    page = provider.alerts(AlertQuery())
    assert page.total == 1
    assert page.items[0].timestep is None
    detail = provider.alert_detail(1)
    assert detail.shap_reasons is None
    assert detail.evidence_items is None
    client.close()


def test_api_provider_timeout() -> None:
    """Timeouts become ProviderError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = ApiClient(transport=httpx.MockTransport(handler), timeout_s=0.01)
    provider = ApiProvider(client)
    with pytest.raises(ProviderError):
        provider.health()
    client.close()


def test_factory_auto_falls_back_to_demo() -> None:
    """auto falls back to demo when nothing listens."""
    choice = create_provider(
        source="auto", api_url="http://127.0.0.1:9", health_timeout_s=0.2
    )
    assert choice.provider.source_label == "DEMO DATA"
    assert any("falling back" in line or "fallback" in line for line in choice.boot_log)


def test_resolve_source_flags() -> None:
    """CLI flags beat the environment default."""
    assert resolve_source(cli_demo=True) == "demo"
    assert resolve_source(cli_api=True) == "api"
    assert resolve_source(env_value="demo") == "demo"
    with pytest.raises(ValueError):
        resolve_source(cli_demo=True, cli_api=True)


def test_network_filter_and_n_a_cells() -> None:
    """Missing network coverage is n/a semantics at the data layer."""
    from tui.helpers.format import network_cell

    provider = DemoProvider(seed=42, simulate_latency=False)
    page = provider.alerts(AlertQuery(limit=ALERT_COUNT))
    missing = [r for r in page.items if not r.has_network_layer]
    assert missing
    for row in missing[:20]:
        assert row.network_signal == 0.0
        assert network_cell(row.has_network_layer, row.network_signal) == "n/a"
    critical = provider.alerts(AlertQuery(min_score=0.8, limit=500))
    assert critical.total > 0
    assert all(r.composite_score >= 0.8 for r in critical.items)


@pytest.mark.asyncio
async def test_splash_hint_brackets_async() -> None:
    """Splash key hints keep their brackets."""
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(100, 30)) as pilot:
        hint = app.screen.query_one("#splash-hint")
        # Static with markup=False keeps the literal string in render output.
        rendered = str(hint.render())
        assert "[ Enter ]" in rendered
        assert "[ Q ]" in rendered
        await pilot.pause(0)


@pytest.mark.asyncio
async def test_navigation_stack_stays_clean() -> None:
    """No duplicate screens after detail, d, g, t, esc."""
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(120, 40)) as pilot:
        assert isinstance(app.screen, SplashScreen)
        await _boot_to_dashboard(app, pilot)

        app.push_screen(AlertDetailScreen(elliptic_tx_id=10_000_000))
        assert isinstance(app.screen, AlertDetailScreen)
        await pilot.press("d")
        assert isinstance(app.screen, DashboardScreen)
        dashboards = [s for s in app.screen_stack if isinstance(s, DashboardScreen)]
        assert len(dashboards) == 1

        await pilot.press("g")
        assert isinstance(app.screen, GraphExplorerScreen)
        await pilot.press("t")
        assert isinstance(app.screen, ThreatDetectionScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, SplashScreen)


@pytest.mark.asyncio
async def test_boot_populates_store() -> None:
    """Boot runs all stages and leaves the store populated."""
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(120, 40)) as pilot:
        await _boot_to_dashboard(app, pilot)
        assert app.store.stats is not None
        assert app.store.alert_page is not None
        assert app.store.threat_overview is not None
        assert app.store.communities
        assert app.store.pipeline is not None


@pytest.mark.asyncio
async def test_dashboard_filter_min_score() -> None:
    """Filtering by min score 0.8 returns only critical-range rows."""
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(140, 45)) as pilot:
        await _boot_to_dashboard(app, pilot)
        dash = app.screen
        assert isinstance(dash, DashboardScreen)
        dash.query_one("#filter-min-score").value = "0.8"
        dash._apply_filters()
        page = app.store.alert_page
        assert page is not None
        assert page.total > 0
        assert all(r.composite_score >= 0.8 for r in page.items)
        dash.action_reset_filters()
        assert app.store.alert_page is not None
        assert app.store.alert_page.total == ALERT_COUNT


@pytest.mark.asyncio
async def test_dashboard_alert_rows_at_100x30() -> None:
    """At 100x30 the alert table shows a usable number of data rows."""
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(100, 30)) as pilot:
        await _boot_to_dashboard(app, pilot)
        table = app.screen.query_one("#alert-list")
        # DataTable row count equals page size (up to 100).
        assert table.row_count >= 15


@pytest.mark.asyncio
async def test_threat_queue_order_and_caveat() -> None:
    """Threat queue follows rank order; caveat present when needed."""
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(140, 45)) as pilot:
        await _boot_to_dashboard(app, pilot)
        await pilot.press("t")
        assert isinstance(app.screen, ThreatDetectionScreen)
        screen = app.screen
        ranks = [r.rank for r in screen._queue]
        assert ranks == sorted(ranks)
        # Re-render coverage into a known string via the helper path.
        screen._render_coverage()
        widget = screen.query_one("#threat-coverage", Static)
        plain = str(widget.render())
        assert "coverage blind spots" in plain
        if any(not r.has_network_layer for r in screen._queue):
            assert CAVEAT in plain
