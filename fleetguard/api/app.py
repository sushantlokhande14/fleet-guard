from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, make_asgi_app
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .. import __version__
from .. import db as fgdb
from ..config import get_settings
from ..diagnostics.llm import LLMClient
from ..metrics import fleet_registry
from ..sim import Fgsim
from .routes import alerts, builds, campaigns, failures, meta, replay, reports


def create_app(database_url: str | None = None, sim: Fgsim | None = None, migrate: bool = True,
               llm_factory: Callable[[], LLMClient] | None = None) -> FastAPI:
    url = database_url or get_settings().database_url

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if migrate:
            with fgdb.session(url) as conn:
                fgdb.migrate(conn)
        app.state.pool = ConnectionPool(url, min_size=1, max_size=8, kwargs={"row_factory": dict_row}, open=True)
        app.state.sim = sim or Fgsim()
        app.state.llm_factory = llm_factory or LLMClient
        try:
            yield
        finally:
            app.state.pool.close()

    app = FastAPI(title="Fleet Guard", version=__version__, lifespan=lifespan,
                  description="Replay driving scenarios across software builds and triage what regressed.")
    # the Vite dev server runs on another port; in compose the UI is served same-origin behind nginx
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"],
                       allow_headers=["*"])
    # Prometheus: fleet KPIs read from Postgres at scrape time, plus request metrics
    registry = fleet_registry(url)
    requests = Counter("fleetguard_api_requests_total", "API requests", ["method", "route", "status"],
                       registry=registry)
    latency = Histogram("fleetguard_api_request_seconds", "API request latency", ["route"], registry=registry,
                        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))

    @app.middleware("http")
    async def observe(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")  # template, not the raw URL: bounded label cardinality
        if path != "/metrics":
            requests.labels(request.method, path, str(response.status_code)).inc()
            latency.labels(path).observe(time.perf_counter() - t0)
        return response

    app.mount("/metrics", make_asgi_app(registry=registry))
    app.include_router(meta.router)
    app.include_router(builds.router)
    app.include_router(campaigns.router)
    app.include_router(failures.router)
    app.include_router(replay.router)
    app.include_router(alerts.router)
    app.include_router(reports.router)
    return app
