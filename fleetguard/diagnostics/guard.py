"""Check an LLM narrative against the facts before it goes into a report.

A narrative is rejected (and the deterministic text used instead) when it:
  * is missing fields or has the wrong shape,
  * blames a parameter that did not change between the two builds,
  * states a number that cannot be traced to the facts (directly, as a
    percentage of a 0-1 fraction, or as a difference, ratio or percent change
    between a baseline and candidate value).
Unknown entries in suspect_parameters are dropped with a note rather than
failing the whole narrative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .context import FailureContext

PARAM_RE = re.compile(r"\b(?:perception|planner|control)\.[a-z_]+\b")
NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
CONFIDENCE = {"low", "medium", "high"}


@dataclass
class GuardResult:
    ok: bool
    narrative: dict[str, Any] | None
    issues: list[str] = field(default_factory=list)


def _numbers(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in NUM_RE.findall(obj):
            out.add(float(m))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers(v, out)


def grounded_numbers(ctx: FailureContext) -> set[float]:
    """Numbers a narrative may legitimately state."""
    nums: set[float] = set()
    _numbers(ctx.facts(), nums)
    pairs: list[tuple[float, float]] = []
    for m in ctx.metrics:
        if isinstance(m["baseline"], (int, float)) and isinstance(m["candidate"], (int, float)):
            pairs.append((float(m["baseline"]), float(m["candidate"])))
    for v in ctx.evidence.values():
        if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
            pairs.append((float(v[0]), float(v[1])))
    for d in ctx.build_diff:
        if isinstance(d["baseline"], (int, float)) and isinstance(d["candidate"], (int, float)):
            pairs.append((float(d["baseline"]), float(d["candidate"])))
    for b, c in pairs:
        nums.add(abs(c - b))
        if b:
            ratio = c / b
            nums.update({ratio, abs(ratio - 1) * 100})
    # a 0-1 fraction (route completion, recall) may be written as a percentage
    nums.update({100 * n for n in nums if 0 < n <= 1})
    return nums


def _is_grounded(x: float, facts: set[float]) -> bool:
    if float(x).is_integer() and abs(x) <= 10:
        return True  # "2 steps", "3 episodes": small counts are not worth policing
    for f in facts:
        tol = max(0.051, 0.02 * abs(f))
        if abs(abs(x) - abs(f)) <= tol:
            return True
    return False


def check(raw: dict[str, Any], ctx: FailureContext) -> GuardResult:
    issues: list[str] = []
    hard = False

    def fail(msg: str) -> None:
        nonlocal hard
        hard = True
        issues.append(msg)

    summary, cause, steps = raw.get("summary"), raw.get("likely_cause"), raw.get("next_steps")
    if not isinstance(summary, str) or not summary.strip():
        fail("missing summary")
    if not isinstance(cause, str) or not cause.strip():
        fail("missing likely_cause")
    if not isinstance(steps, list) or not steps or not all(isinstance(s, str) and s.strip() for s in steps):
        fail("next_steps must be a non-empty list of strings")
    if hard:
        return GuardResult(False, None, issues)
    if len(summary) > 1200 or len(cause) > 800:
        fail("narrative too long")
    steps = [s.strip() for s in steps][:6]

    changed = {d["key"] for d in ctx.build_diff}
    suspects = raw.get("suspect_parameters") or []
    if not isinstance(suspects, list):
        suspects = []
    kept = [p for p in suspects if p in changed]
    for p in suspects:
        if p not in changed:
            issues.append(f"dropped suspect parameter that did not change: {p}")

    text = f"{summary}\n{cause}"
    for p in sorted(set(PARAM_RE.findall(text))):
        if p not in changed:
            fail(f"mentions a parameter that did not change: {p}")

    facts = grounded_numbers(ctx)
    for tok in NUM_RE.findall(text):
        if not _is_grounded(float(tok), facts):
            fail(f"number not found in the facts: {tok}")

    confidence = raw.get("confidence")
    if confidence not in CONFIDENCE:
        confidence = None
    if hard:
        return GuardResult(False, None, issues)
    return GuardResult(True, {"summary": summary.strip(), "likely_cause": cause.strip(), "next_steps": steps,
                              "suspect_parameters": kept, "confidence": confidence}, issues)
