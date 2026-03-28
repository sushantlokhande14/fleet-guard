from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Request

from ..sim import Fgsim


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    """A pooled connection for one request; committed on success, rolled back on error."""
    with request.app.state.pool.connection() as conn:
        yield conn


def get_sim(request: Request) -> Fgsim:
    return request.app.state.sim


Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Sim = Annotated[Fgsim, Depends(get_sim)]
