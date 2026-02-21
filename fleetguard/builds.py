"""Build registry.

A build is a JSON file under builds/ that lists only what it changes relative to
its parent (or to the stack defaults when it has no parent). The registry resolves
the parent chain into the overrides fgsim needs and into the full effective
parameter set used for diffs and reports.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import get_settings

SECTIONS = ("perception", "planner", "control")


class BuildError(ValueError):
    pass


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def flatten(params: dict) -> dict[str, Any]:
    """{"planner": {"headway_s": 1.5}} -> {"planner.headway_s": 1.5}"""
    flat = {}
    for section in SECTIONS:
        for key, value in params.get(section, {}).items():
            flat[f"{section}.{key}"] = value
    return flat


@dataclass(frozen=True)
class ParamChange:
    key: str
    baseline: Any
    candidate: Any

    def as_dict(self) -> dict:
        return {"key": self.key, "baseline": self.baseline, "candidate": self.candidate}


def diff(baseline_effective: dict, candidate_effective: dict) -> list[ParamChange]:
    a, b = flatten(baseline_effective), flatten(candidate_effective)
    return [ParamChange(k, a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]


@dataclass
class Build:
    name: str
    description: str
    parent: str | None
    changes: dict  # this build's own overrides

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "parent": self.parent, **self.changes}


class Registry:
    def __init__(self, builds_dir: str | Path | None = None, defaults: dict | None = None):
        self.dir = Path(builds_dir or get_settings().builds_dir)
        self.defaults = defaults
        self._builds: dict[str, Build] = {}
        if self.dir.is_dir():
            for path in sorted(self.dir.glob("*.json")):
                self.add(self._load(path))

    @staticmethod
    def _load(path: Path) -> Build:
        doc = json.loads(path.read_text())
        if "name" not in doc:
            raise BuildError(f"{path.name}: missing name")
        unknown = set(doc) - {"name", "description", "parent", *SECTIONS}
        if unknown:
            raise BuildError(f"{path.name}: unknown keys {sorted(unknown)}")
        changes = {s: doc[s] for s in SECTIONS if s in doc}
        return Build(doc["name"], doc.get("description", ""), doc.get("parent"), changes)

    def add(self, build: Build) -> None:
        if build.name in self._builds:
            raise BuildError(f"duplicate build {build.name}")
        self._builds[build.name] = build

    def names(self) -> list[str]:
        return list(self._builds)

    def get(self, name: str) -> Build:
        try:
            return self._builds[name]
        except KeyError:
            raise BuildError(f"unknown build {name}") from None

    def overrides(self, name: str) -> dict:
        """Everything this build changes relative to the stack defaults, parent chain included."""
        chain, seen = [], set()
        cur: str | None = name
        while cur is not None:
            if cur in seen:
                raise BuildError(f"parent cycle at {cur}")
            seen.add(cur)
            b = self.get(cur)
            chain.append(b)
            cur = b.parent
        merged: dict = {}
        for b in reversed(chain):
            merged = deep_merge(merged, b.changes)
        return {"name": name, **merged}

    def effective(self, name: str) -> dict:
        if self.defaults is None:
            raise BuildError("effective parameters need the stack defaults (fgsim defaults)")
        eff = deep_merge(self.defaults, self.overrides(name))
        eff["name"] = name
        return eff

    def diff(self, baseline: str, candidate: str) -> list[ParamChange]:
        return diff(self.effective(baseline), self.effective(candidate))
