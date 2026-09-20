"""Filter panel: alert list filtering controls."""

from textual.widget import Widget


class FilterPanel(Widget):
    """Filter controls for the ranked alert list."""

    def render(self) -> str:
        return "Filters: not yet wired to the API."
