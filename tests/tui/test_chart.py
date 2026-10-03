"""Chart data: provider series, KPI sparklines, graph panels and triage."""

from __future__ import annotations

import httpx
import pytest

from bitcraft.api_client import ApiClient
from bitcraft.app import BitCraftApp
from bitcraft.providers.api_provider import ApiProvider
from bitcraft.providers.demo_provider import DemoProvider
from bitcraft.providers.models import StatsCharts
from bitcraft.screens.dashboard import DashboardScreen
from bitcraft.screens.graph_explorer import GraphExplorerScreen
from bitcraft.store import Store
from bitcraft.widgets.chart_panel import DegreeChart, FlowChart, HeatmapChart
from bitcraft.widgets.kpi_summary import SPARK_POINTS, bucket_means, spark_series


def _store() -> Store:
    return Store(provider=DemoProvider(simulate_latency=False), is_demo=True, fast_boot=True)


async def _boot(app: BitCraftApp, pilot) -> None:
    await pilot.press("enter")
    for _ in range(200):
        if isinstance(app.screen, DashboardScreen) and app.store.boot_complete:
            return
        await pilot.pause(0.05)
    raise AssertionError("boot did not reach dashboard")


def test_bucket_means_keeps_shape() -> None:
    assert bucket_means([1, 2, 3]) == [1.0, 2.0, 3.0]
    series = bucket_means(range(49))
    assert len(series) == SPARK_POINTS
    assert series == sorted(series)
    assert spark_series(None) == {}


def test_driver_weights_match_pipeline_config() -> None:
    """The TUI splits scores with the same weights the pipeline fuses with."""
    from pathlib import Path

    import yaml

    from bitcraft.helpers import drivers

    config = Path(__file__).resolve().parents[2] / "ml" / "config.yaml"
    fusion = yaml.safe_load(config.read_text(encoding="utf-8"))["score_fusion"]
    assert drivers.MODEL_WEIGHT == fusion["risk_model_weight"]
    assert drivers.ANOMALY_WEIGHT == fusion["anomaly_score_weight"]
    assert drivers.COMMUNITY_WEIGHT == fusion["community_illicit_ratio_weight"]
    assert drivers.NETWORK_WEIGHT == fusion["network_ip_signal_weight"]


def test_demo_charts_align_with_timesteps() -> None:
    provider = DemoProvider(simulate_latency=False)
    charts = provider.stats_charts()
    n = len(charts.timesteps)
    for name in ("transactions", "alerts", "critical", "labeled", "network",
                 "flow_all_btc", "flow_alerted_btc"):
        assert len(getattr(charts, name)) == n, name
    assert all(len(row) == n for row in charts.country_matrix)
    assert len(charts.country_rows) == len(charts.country_matrix)
    assert len(charts.degree_buckets) == len(charts.degree_counts)
    per_ts = provider.threat_overview().alerts_per_timestep or {}
    assert sum(charts.alerts) == sum(per_ts.values())


def test_api_charts_parse_and_fall_back() -> None:
    payload = {
        "timesteps": [1, 2], "transactions": [10, 20], "alerts": [1, 2], "critical": [0, 1],
        "labeled": [3, 4], "network": [5, 6], "stage_seconds": {"load": 1.5},
        "degree_buckets": ["1", "2+"], "degree_counts": [7, 3],
        "flow_all_btc": [1.0, 2.0], "flow_alerted_btc": [0.1, 0.0],
        "country_rows": ["DE"], "country_matrix": [[1, 0]],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/stats/charts":
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "missing"})

    client = ApiClient(transport=httpx.MockTransport(handler))
    charts = ApiProvider(client).stats_charts()
    assert charts.alerts == [1, 2] and charts.stage_seconds == {"load": 1.5}
    assert charts.country_matrix == [[1, 0]]
    client.close()

    missing = ApiClient(transport=httpx.MockTransport(lambda r: httpx.Response(404, json={})))
    assert ApiProvider(missing).stats_charts() == StatsCharts()
    missing.close()


@pytest.mark.asyncio
async def test_graph_panels_show_loaded_series() -> None:
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(190, 52)) as pilot:
        await _boot(app, pilot)
        charts = app.store.charts
        assert charts is not None and charts.timesteps
        await pilot.press("g")
        await pilot.pause(0.2)
        screen = app.screen
        assert isinstance(screen, GraphExplorerScreen)
        assert screen.query_one(FlowChart).total == charts.flow_all_btc
        assert screen.query_one(HeatmapChart).rows == charts.country_rows
        assert screen.query_one(DegreeChart).counts == charts.degree_counts


@pytest.mark.asyncio
async def test_mark_cycles_triage() -> None:
    app = BitCraftApp(store=_store())
    async with app.run_test(size=(160, 46)) as pilot:
        await _boot(app, pilot)
        table = app.screen.query_one("#alert-list")
        table.focus()
        await pilot.pause(0.1)
        tx_id = app.store.selected_tx_id
        assert tx_id is not None
        seen = []
        for _ in range(4):
            await pilot.press("m")
            seen.append(app.store.triage[tx_id].status)
        assert seen == ["reviewed", "escalate", "dismiss", "unmarked"]
        await pilot.press("m")
        assert table.get_row(str(tx_id))[-1] == "R"
