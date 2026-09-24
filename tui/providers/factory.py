"""Provider factory: auto | demo | api selection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Optional

import httpx

from tui.api_client import DEFAULT_BASE_URL, ApiClient
from tui.providers.api_provider import ApiProvider
from tui.providers.demo_provider import DemoProvider
from tui.providers.provider import DataProvider

DataSource = Literal["auto", "demo", "api"]


@dataclass
class ProviderChoice:
    """Result of factory selection, including human-readable reason."""

    provider: DataProvider
    source: DataSource
    reason: str
    boot_log: list[str] = field(default_factory=list)


def resolve_source(
    cli_demo: bool = False,
    cli_api: bool = False,
    env_value: Optional[str] = None,
) -> DataSource:
    """Resolve data source from CLI flags and BITCRAFT_DATA_SOURCE."""
    if cli_demo and cli_api:
        raise ValueError("use only one of --demo or --api")
    if cli_demo:
        return "demo"
    if cli_api:
        return "api"
    raw = (env_value if env_value is not None else os.environ.get("BITCRAFT_DATA_SOURCE", "auto"))
    raw = (raw or "auto").strip().lower()
    if raw not in {"auto", "demo", "api"}:
        raise ValueError(f"unknown BITCRAFT_DATA_SOURCE={raw!r}")
    return raw  # type: ignore[return-value]


def create_provider(
    source: DataSource = "auto",
    api_url: str = DEFAULT_BASE_URL,
    health_timeout_s: float = 1.5,
) -> ProviderChoice:
    """Build the DataProvider for the requested source.

    auto calls /health with a short timeout and falls back to demo on
    failure, recording why in boot_log.
    """
    log: list[str] = []
    if source == "demo":
        log.append("data source: demo (explicit)")
        return ProviderChoice(
            DemoProvider(simulate_latency=True), "demo", "explicit --demo", log
        )

    if source == "api":
        client = ApiClient(base_url=api_url, timeout_s=health_timeout_s)
        log.append(f"data source: api ({api_url})")
        return ProviderChoice(ApiProvider(client), "api", "explicit --api", log)

    # auto
    log.append(f"data source: auto, probing {api_url}/health")
    try:
        client = ApiClient(base_url=api_url, timeout_s=health_timeout_s)
        payload = client.health()
        if payload.get("status") == "ok":
            log.append("health ok; using api provider")
            return ProviderChoice(
                ApiProvider(client), "api", "auto: health ok", log
            )
        log.append(f"health returned {payload!r}; falling back to demo")
        client.close()
    except httpx.HTTPError as exc:
        log.append(f"health failed ({exc}); falling back to demo")
    except Exception as exc:  # noqa: BLE001 - boot must never crash here
        log.append(f"health failed ({exc}); falling back to demo")

    return ProviderChoice(
        DemoProvider(simulate_latency=True),
        "demo",
        "auto: fallback to demo",
        log,
    )
