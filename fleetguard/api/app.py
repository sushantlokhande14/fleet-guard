from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .. import __version__
from .. import db as fgdb
from ..config import get_settings
from ..sim import Fgsim
from .routes import builds, campaigns, failures, meta


def create_app(database_url: str | None = None, sim: Fgsim | None = None, migrate: bool = True) -> FastAPI:
    url = database_url or get_settings().database_url

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if migrate:
            with fgdb.session(url) as conn:
                fgdb.migrate(conn)
        app.state.pool = ConnectionPool(url, min_size=1, max_size=8, kwargs={"row_factory": dict_row}, open=True)
        app.state.sim = sim or Fgsim()
        try:
            yield
        finally:
            app.state.pool.close()

    app = FastAPI(title="Fleet Guard", version=__version__, lifespan=lifespan,
                  description="Replay driving scenarios across software builds and triage what regressed.")
    # the Vite dev server runs on another port; in compose the UI is served same-origin behind nginx
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"],
                       allow_headers=["*"])
    app.include_router(meta.router)
    app.include_router(builds.router)
    app.include_router(campaigns.router)
    app.include_router(failures.router)
    return app
