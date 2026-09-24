# BitCraft TUI Design

Status: demo-backed shell through threat detection. Graph canvas and
analyst tooling still pending.

## Why a Terminal Interface

BitCraft is an offline, air-gapped system (`plans/plan.md` section 1). A
terminal interface needs no browser, no web server, and no client-side
build step, so it drops cleanly into the same offline Linux container as
the rest of the pipeline.

## Framework

Textual (Python). Floor: `textual>=5.0` for `App.MODES` / `switch_mode`.

## Visual Theme: Pitch Black

| Role | Color | Use |
|---|---|---|
| Background | `#000000` | Screen, header, footer |
| Panel background | `#050505` | Panel bodies |
| Border | `#1a1a1a` | Panel outlines |
| Primary text | `#e6e6e6` | Body text |
| Accent | `#d4af37` | Headers, medium severity, focus |
| High severity | `#b3261e` | High/critical alerts only |
| Muted | `#7a7a7a` | Footer, low severity |
| Modeled badge | `#6a6a6a`, italic | Synthetic-layer values |

## Provider layer

Screens read only from `tui/store.py`. The store holds a `DataProvider`:

- `DemoProvider` - deterministic seed 42, plan-aligned coverage numbers
- `ApiProvider` - FastAPI via `tui/api_client.py`
- Selection: `BITCRAFT_DATA_SOURCE=auto|demo|api`, or `--demo` / `--api`

`auto` probes `/health` (1.5s) and falls back to demo on failure.

## Provenance glyphs

- `~` prefix and `.modeled-badge` = modeled / synthetic-layer value
- `n/a` = no network coverage (never show `0` / `0.00` as risk)
- `DEMO DATA` badge in the header whenever the demo provider is active

## Severity (display-only)

| Tier | Composite score |
|---|---|
| critical | >= 0.80 |
| high | >= 0.60 |
| medium | >= 0.40 |
| low | < 0.40 |

## Screens

| Screen | Key | Role |
|---|---|---|
| Splash | launch | ASCII logo |
| Boot | after Enter | Real provider stages, then dashboard |
| Dashboard | `d` | KPIs, filters, alerts, preview |
| Threats | `t` | Posture, queue, drivers, communities |
| Graph | `g` | Placeholder explorer (canvas later) |
| Alert detail | Enter on row | Scores, evidence, SHAP |

## Key map

| Key | Action |
|---|---|
| Enter | Splash: boot; table: detail |
| d | Dashboard |
| t | Threats |
| g | Graph |
| Esc | Home (splash) |
| q | Quit |
| n / p | Next / previous alert page |
| s | Cycle sort |
| f / x | Focus filters / reset |
| r | Refresh |
| a / c / n | Threat driver filters |
| w | Threat network-evidence toggle |

## Run

```text
pip install -r tui/requirements.txt
python -m tui.app --demo
python -m tui.app --api
python -m tui.app
```

Minimum terminal size: 100x30. Below that a guard panel is shown.
`BITCRAFT_ASCII=1` forces plain ASCII glyphs.
