"""FastAPI application entry point.

Wires the alert, graph, community, stats, and pipeline routers. The API
only ever reads pre-computed results from the database and Redis; no ML
code runs at request time.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models as _models  # noqa: F401  (registers models on Base.metadata)
from app.api import alerts, communities, graph, pipeline, stats
from app.core.database import Base, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Empty tables (not a 500) until app/loader.py fills them.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="BitCraft API", lifespan=lifespan)

app.include_router(alerts.router)
app.include_router(graph.router)
app.include_router(communities.router)
app.include_router(stats.router)
app.include_router(pipeline.router)


@app.get("/health")
def health_check() -> dict:
    """Liveness check used by Docker Compose and the TUI."""
    return {"status": "ok"}
