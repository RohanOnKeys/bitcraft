# BitCraft TUI Design

Status: draft. Scaffolded only, not implemented.

## Why a Terminal Interface

BitCraft is an offline, air-gapped system (`plans/plan.md` section 1). A
terminal interface needs no browser, no web server, and no client-side
build step, so it drops cleanly into the same offline Linux container as
the rest of the pipeline. This replaces the React/Vite web dashboard the
plan originally described.

## Framework

[Textual](https://textual.textualize.io/), a Python TUI framework. It
fits the existing Python/FastAPI stack directly, and its widget and
screen model maps onto the dashboard/alert-detail/graph-explorer split
already defined in `plans/plan.md` section 11.

## Visual Theme: Pitch Black

Dark Knight vibes: near-black everywhere, no gradients, no soft grays
pretending to be a "light dark mode." One accent color carries all
signal.

| Role | Color | Use |
|---|---|---|
| Background | `#000000` | Screen, header, footer |
| Panel background | `#050505` | Panel bodies, just barely lifted off black |
| Border | `#1a1a1a` | Panel outlines, barely visible until focused |
| Primary text | `#e6e6e6` | Body text |
| Accent (bat-signal) | `#d4af37` | Headers, medium-severity alerts, focus state |
| High severity | `#b3261e` | High-severity alerts only, bold |
| Muted | `#7a7a7a` | Footer, low-severity alerts |
| Modeled badge | `#6a6a6a`, italic | Synthetic-layer values |

The full stylesheet is `tui/theme.tcss`. The rule that matters most:
color is reserved for meaning (severity, focus, provenance), not
decoration. A screen with no alerts should look almost entirely black.

## Screens

- **Dashboard** (`tui/screens/dashboard.py`) - KPI summary, filter panel,
  ranked alert list. Default screen on launch.
- **Alert Detail** (`tui/screens/alert_detail.py`) - scores, SHAP
  reasons, evidence text, and an embedded mini graph view for one
  transaction.
- **Graph Explorer** (`tui/screens/graph_explorer.py`) - full-screen
  link-analysis view, keyboard pan/navigate, colored by score or
  community.

## Widgets

- `KpiSummary` - GET `/stats/summary`
- `FilterPanel` - drives the query params for `AlertList`
- `AlertList` - a Textual `DataTable`, GET `/alerts`
- `AlertDetailPanel` - GET `/alerts/{tx_id}`
- `GraphView` - GET `/graph/{tx_id}`, or the full graph with no ID

## Data Flow

The TUI only reads pre-computed results through `tui/api_client.py`,
which calls the FastAPI backend. No ML code runs in the TUI process
(`plans/plan.md` section 10.3).

## Provenance

Synthetic-layer values must never render as if they were observed facts
about a real transaction (`plans/plan.md` section 2.3). The `.modeled-
badge` style in `tui/theme.tcss` (dim, italic) is the one place that
distinction shows up on screen; every evidence field that came from the
synthetic layer gets it.

## Current State

Scaffolded: app entry point, three screen stubs, five widget stubs, the
theme stylesheet, and an unimplemented `api_client.py`. Nothing is wired
to a running backend and the app has not been run.
