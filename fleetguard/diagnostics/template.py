"""Deterministic markdown report for one failure.

Every number in here comes from the context. When an LLM narrative is supplied
it replaces only the Summary, Likely cause and Next steps sections; evidence,
metrics, timeline and the repro command are always rendered from data.
"""

from __future__ import annotations

from typing import Any

from .context import FailureContext

CATEGORY_TITLE = {
    "disengagement": "Disengagement",
    "latency_spike": "Planner latency regression",
    "route_deviation": "Route deviation",
    "perception_error": "Perception regression",
    "control_instability": "Control instability",
}

# which build parameters plausibly drive each category (used to point at suspects)
CATEGORY_PARAMS = {
    "disengagement": ("planner.",),
    "latency_spike": ("planner.latency", "planner.spike", "planner.cycle", "planner.watchdog"),
    "route_deviation": ("planner.curve_offset", "planner.lateral_bias", "planner.use_live_lane",
                        "control.lookahead"),
    "perception_error": ("perception.",),
    "control_instability": ("control.",),
}

NEXT_STEPS = {
    "disengagement": [
        "Replay the pair and compare the candidate's speed and gap profile with the baseline before the takeover.",
        "Check planner changes that affect following distance, braking authority or prediction horizons.",
        "Run a campaign on just this scenario family to see whether the takeover rate scales with severity.",
    ],
    "latency_spike": [
        "Profile the planning cycle on this scenario: compare cycle time against the number of tracked objects.",
        "Check for new work on the planning thread (fusion, logging, cost terms) and for lock contention.",
        "Confirm whether deadline misses cluster in dense scenes (work zones, traffic).",
    ],
    "route_deviation": [
        "Overlay both trajectories on the lane and find where the candidate first leaves the baseline's path.",
        "Check map/lane inputs (curvature, lane-shift updates) and lateral calibration offsets.",
        "Re-run with only the lateral changes from the diff to isolate the cause.",
    ],
    "perception_error": [
        "Pull the frames around the first missed object and check range, weather and object class.",
        "Compare detector/tracker settings in the diff (miss rates, range scaling, confirmation frames).",
        "Run the perception-heavy families (ped_crossing, urban_cut_in) in fog and rain to bound the effect.",
    ],
    "control_instability": [
        "Plot steering (or acceleration) command vs actual: look for phase lag and growing overshoot.",
        "Check controller gains and actuator delay in the diff; delay plus gain is the usual culprit.",
        "Re-run the cluster with the previous gain or delay to confirm which change made the loop ring.",
    ],
}


def _fmt(v: Any) -> str:
    if v is None or v == "":
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:,.0f}"
    return str(v)


def _evidence_value(v: Any) -> str:
    # most evidence pairs are [baseline, candidate]
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v):
        return f"{_fmt(v[0])} -> {_fmt(v[1])}"
    if isinstance(v, list):
        return ", ".join(_fmt(x) for x in v) or "-"
    return _fmt(v)


def suspects(ctx: FailureContext) -> list[dict[str, Any]]:
    prefixes = CATEGORY_PARAMS[ctx.category]
    return [d for d in ctx.build_diff if d["key"].startswith(prefixes)]


def default_summary(ctx: FailureContext) -> str:
    ev, sc = ctx.evidence, ctx.scenario
    where = f"{sc['family']} scenario {sc['id']} ({sc['weather']})"
    when = f" from t={ctx.first_t:.1f} s" if ctx.first_t is not None else ""
    if ctx.category == "disengagement":
        what = f"the candidate ended the drive with {ev.get('outcome')} ({ev.get('reason') or 'no reason'})"
        what += f" at {ev.get('at_s')} s where the baseline completed it"
    elif ctx.category == "latency_spike":
        b, c = ev["deadline_misses"]
        pb, pc = ev["planner_p99_ms"]
        what = f"planner deadline misses went from {b} to {c} and p99 cycle time from {pb} to {pc} ms"
        if ev.get("watchdog"):
            what += ", tripping the watchdog"
    elif ctx.category == "route_deviation":
        b, c = ev["cte_max_m"]
        what = f"max cross-track error went from {b} m to {c} m"
        if ev.get("first_divergence_s") is not None:
            what += f", first diverging from the baseline path {ev['first_divergence_s']} m into the route"
    elif ctx.category == "perception_error":
        b, c = ev["recall"]
        what = f"perception recall went from {b} to {c}"
        misses = ev.get("new_misses") or []
        if misses:
            what += f" with {len(misses)} new missed object(s), first {misses[0]['object']} at {misses[0]['range_m']} m"
        if ev.get("new_phantoms"):
            what += f" and {ev['new_phantoms']} new phantom object(s)"
    else:
        sb, sc_ = ev["steer_reversals_per_s"]
        ab, ac = ev["accel_reversals_per_s"]
        what = f"steering reversals went from {sb}/s to {sc_}/s and accel reversals from {ab}/s to {ac}/s"
        if ev.get("oscillation_events"):
            what += f" with {ev['oscillation_events']} new oscillation episode(s)"
    also = f" Also seen: {', '.join(ctx.secondary)}." if ctx.secondary else ""
    return (f"On {where}, {ctx.candidate} regressed against {ctx.baseline}{when}: {what}.{also} "
            f"This failure is one of {ctx.cluster['size']} with signature `{ctx.signature}` in this campaign.")


def default_cause(ctx: FailureContext) -> str:
    sus = suspects(ctx)
    if not sus:
        return ("No changed parameter in the build diff maps directly to this category; look at interactions "
                "between the changes listed below.")
    names = ", ".join(f"`{d['key']}` ({_fmt(d['baseline'])} -> {_fmt(d['candidate'])})" for d in sus)
    return f"Changed parameters that plausibly drive a {CATEGORY_TITLE[ctx.category].lower()}: {names}."


def render(ctx: FailureContext, narrative: dict[str, Any] | None = None, generator: str = "template") -> str:
    sc = ctx.scenario
    title = CATEGORY_TITLE[ctx.category]
    summary = narrative["summary"] if narrative else default_summary(ctx)
    cause = narrative["likely_cause"] if narrative else default_cause(ctx)
    steps = narrative["next_steps"] if narrative else NEXT_STEPS[ctx.category]
    sev = {1: "low", 2: "medium", 3: "high"}[ctx.severity]

    out = [
        f"# {title}: {sc['id']}",
        "",
        f"**Campaign** #{ctx.campaign_id} ({ctx.candidate} vs {ctx.baseline}) · **severity** {sev} · "
        f"**signature** `{ctx.signature}` ({ctx.cluster['size']} in cluster, "
        f"{ctx.cluster['campaign_failures']} failures in campaign)",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Likely cause",
        "",
        cause,
        "",
        "## What changed",
        "",
    ]
    if ctx.build_diff:
        out += ["| parameter | baseline | candidate |", "|---|---|---|"]
        out += [f"| `{d['key']}` | {_fmt(d['baseline'])} | {_fmt(d['candidate'])} |" for d in ctx.build_diff]
    else:
        out.append("The two builds have identical parameters.")
    out += ["", "## Evidence", ""]
    out += [f"- **{k.replace('_', ' ')}**: {_evidence_value(v)}" for k, v in ctx.evidence.items()
            if k != "new_misses"]
    for m in (ctx.evidence.get("new_misses") or [])[:5]:
        out.append(f"- missed {m['object']} at {m['range_m']} m, t={m['t']} s")
    if ctx.secondary:
        sig = ", ".join(f"{k} (first at {_fmt(v['first_t'])} s)" for k, v in ctx.signals.items()
                        if k != ctx.category)
        out.append(f"- **other signals**: {sig}")
    out += ["", "## Metrics", "", "| metric | baseline | candidate |", "|---|---|---|"]
    for m in ctx.metrics:
        def cell(v: Any, m: dict = m) -> str:
            return _fmt(v) + (f" {m['unit']}" if m["unit"] and v is not None else "")

        cand = cell(m["candidate"])
        if m["baseline"] != m["candidate"]:
            cand = f"**{cand}**"
        out.append(f"| {m['name']} | {cell(m['baseline'])} | {cand} |")
    out += ["", "## Timeline", ""]
    if ctx.timeline:
        out += ["| t (s) | build | event | value | detail |", "|---|---|---|---|---|"]
        out += [f"| {e['t']} | {e['role']} | {e['kind']} | {_fmt(e['value'])} | {e['detail']} |" for e in ctx.timeline]
    else:
        out.append("No events recorded.")
    others = ctx.cluster.get("others") or []
    out += ["", "## Same signature", ""]
    if others:
        out.append(f"{ctx.cluster['size'] - 1} other failure(s) in this campaign share `{ctx.signature}`; "
                   "they are very likely the same bug. Strongest first:")
        out += ["", "| failure | scenario | weather | severity | score | first at (s) |", "|---|---|---|---|---|---|"]
        out += [f"| #{o['id']} | {o['scenario_id']} | {o['weather']} | {o['severity']} | {_fmt(o['score'])} "
                f"| {_fmt(o['first_t'])} |" for o in others]
        if ctx.cluster["size"] - 1 > len(others):
            out.append(f"| ... | {ctx.cluster['size'] - 1 - len(others)} more | | | | |")
    else:
        out.append("No other failure in this campaign has this signature.")
    verified = {True: "verified: replays identically", False: "replay did NOT match the stored run",
                None: "not yet verified"}[ctx.repro_verified]
    out += [
        "",
        "## Reproduce",
        "",
        f"Scenario `{sc['family']}` seed {sc['seed']}, {sc['route_length_m']} m route, {sc['weather']}. "
        f"Deterministic; {verified}.",
        "",
        "```bash",
        ctx.repro_command,
        "```",
        "",
        "## Next steps",
        "",
    ]
    out += [f"{i}. {s}" for i, s in enumerate(steps, 1)]
    out += ["", f"<sub>Generated by Fleet Guard ({generator}) from failure #{ctx.failure_id}.</sub>", ""]
    return "\n".join(out)
