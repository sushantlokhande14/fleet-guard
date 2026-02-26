import os

import pytest

from fleetguard.sim import Fgsim, FgsimError


@pytest.fixture(scope="session")
def fgsim() -> Fgsim:
    try:
        return Fgsim()
    except FgsimError:
        pytest.skip("fgsim binary not available")


@pytest.fixture
def db_url() -> str:
    url = os.environ.get("FG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("FG_TEST_DATABASE_URL not set")
    return url


@pytest.fixture
def db(db_url):
    """Fresh, fully migrated database for each test."""
    from fleetguard import db as fgdb

    conn = fgdb.connect(db_url)
    fgdb.reset(conn)
    fgdb.migrate(conn)
    yield conn
    conn.close()
