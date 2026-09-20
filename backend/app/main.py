"""FastAPI application entry point.

Wires the alert, graph, community, stats, and pipeline routers. The API
only ever reads pre-computed results from PostgreSQL and Redis; no ML
code runs at request time.
"""

from fastapi import FastAPI

from app.api import alerts, communities, graph, pipeline, stats

app = FastAPI(title="BitCraft API")

app.include_router(alerts.router)
app.include_router(graph.router)
app.include_router(communities.router)
app.include_router(stats.router)
app.include_router(pipeline.router)


@app.get("/health")
def health_check() -> dict:
    """Liveness check used by Docker Compose and the frontend."""
    return {"status": "ok"}
