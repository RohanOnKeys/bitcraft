"""Reusable loading / empty / error panel states."""

from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class PanelState(Widget):
    """Shows loading, empty, or error instead of blank space."""

    DEFAULT_CSS = """
    PanelState {
        width: 100%;
        height: auto;
        color: #7a7a7a;
        padding: 1;
    }
    PanelState.error {
        color: #b3261e;
    }
    """

    def __init__(
        self,
        *,
        state: str = "loading",
        message: str = "Loading...",
        hint: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._message = message
        self._hint = hint

    def compose(self) -> ComposeResult:
        yield Static(self._render_text(), id="panel-state-text")

    def _render_text(self) -> str:
        if self._state == "loading":
            return f"... {self._message}"
        if self._state == "empty":
            body = self._message
            if self._hint:
                body = f"{body}\n{self._hint}"
            return body
        # error
        body = f"[!!] {self._message}"
        if self._hint:
            body = f"{body}\n{self._hint}"
        return body

    def set_loading(self, message: str = "Loading...") -> None:
        """Switch to the loading state."""
        self._state = "loading"
        self._message = message
        self._hint = ""
        self.remove_class("error")
        self._refresh_text()

    def set_empty(self, message: str, hint: str = "") -> None:
        """Switch to the empty state."""
        self._state = "empty"
        self._message = message
        self._hint = hint
        self.remove_class("error")
        self._refresh_text()

    def set_error(self, message: str, hint: str = "Press r to retry.") -> None:
        """Switch to the error state."""
        self._state = "error"
        self._message = message
        self._hint = hint
        self.add_class("error")
        self._refresh_text()

    def _refresh_text(self) -> None:
        try:
            self.query_one("#panel-state-text", Static).update(self._render_text())
        except Exception:
            pass
