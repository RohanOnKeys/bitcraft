"""Dashboard screen: KPIs, filters, and the ranked alert list."""

from textual.screen import Screen
from textual.widgets import Footer, Header

from tui.widgets.alert_list import AlertList
from tui.widgets.filter_panel import FilterPanel
from tui.widgets.kpi_summary import KpiSummary


class DashboardScreen(Screen):
    """Landing screen: KPI summary, filter panel, ranked alert list."""

    def compose(self):
        yield Header()
        yield KpiSummary(id="kpi-summary")
        yield FilterPanel(id="filter-panel")
        yield AlertList(id="alert-list")
        yield Footer()
