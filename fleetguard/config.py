"""Runtime settings, read from the environment once."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    fgsim: str = field(default_factory=lambda: _env("FG_FGSIM", ""))
    runs_dir: Path = field(default_factory=lambda: Path(_env("FG_RUNS_DIR", str(REPO_ROOT / "runs"))))
    builds_dir: Path = field(default_factory=lambda: Path(_env("FG_BUILDS_DIR", str(REPO_ROOT / "builds"))))
    sim_threads: int = field(default_factory=lambda: int(_env("FG_SIM_THREADS", "0")))
    database_url: str = field(default_factory=lambda: _env(
        "FG_DATABASE_URL", "postgresql://fleetguard:fleetguard@localhost:5432/fleetguard"))
    migrations_dir: Path = field(default_factory=lambda: Path(
        _env("FG_MIGRATIONS_DIR", str(REPO_ROOT / "db" / "migrations"))))


def get_settings() -> Settings:
    return Settings()
