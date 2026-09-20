"""KPI summary panel: top-line dashboard stats."""

from textual.widget import Widget


class KpiSummary(Widget):
    """Displays total transactions, total alerts, and coverage stats.

    Backed by GET /stats/summary.
    """

    def render(self) -> str:
        return "KPI summary: not yet wired to the API."
