"""Generate, store and fetch diagnostic reports."""

from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import guard, template
from .context import FailureContext, build_context
from .llm import LLMClient, LLMError

SYSTEM_PROMPT = """You are a validation engineer for an autonomous-driving software stack.
You write short triage notes for one failed scenario, for the engineer who owns the regression.

Use only the facts in the JSON you are given. Do not invent numbers, events, causes or parameters.
Every number you write must appear in the facts (or be the change between a baseline and a candidate value).
Only blame parameters listed in build_diff.

Reply with one JSON object and nothing else:
{
  "summary": "2-4 sentences: what the candidate did differently from the baseline, when, and how bad",
  "likely_cause": "1-3 sentences naming the changed parameter(s) most likely responsible and why",
  "suspect_parameters": ["keys from build_diff"],
  "next_steps": ["2-4 short imperative steps an engineer can take next"],
  "confidence": "low | medium | high"
}"""


def user_prompt(ctx: FailureContext) -> str:
    facts = ctx.facts()
    facts.pop("repro_command")  # long and adds nothing to the narrative
    return "Facts about the failure:\n```json\n" + json.dumps(facts, indent=1, default=str) + "\n```"


def generate(conn: psycopg.Connection, failure_id: int, llm: LLMClient | None = None) -> dict[str, Any]:
    ctx = build_context(conn, failure_id)
    meta: dict[str, Any] = {}
    narrative = None
    model = None
    if llm is not None:
        meta["model_requested"] = llm.model
        try:
            res = llm.chat_json(SYSTEM_PROMPT, user_prompt(ctx))
            meta.update(latency_s=res.latency_s, prompt_tokens=res.prompt_tokens,
                        completion_tokens=res.completion_tokens)
            g = guard.check(res.content, ctx)
            meta["guard_issues"] = g.issues
            if g.ok:
                narrative, model = g.narrative, res.model
            else:
                meta["llm_rejected"] = True
                meta["llm_raw"] = res.raw[:4000]
        except LLMError as exc:
            meta["llm_error"] = str(exc)
    generator = "llm" if narrative else "template"
    label = f"llm, {model}" if narrative else "template"
    markdown = template.render(ctx, narrative, generator=label)
    return conn.execute(
        """
        INSERT INTO reports (failure_id, generator, model, markdown, narrative, meta)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING *
        """,
        (failure_id, generator, model, markdown, Jsonb(narrative) if narrative else None, Jsonb(meta)),
    ).fetchone()


def latest(conn: psycopg.Connection, failure_id: int) -> dict[str, Any] | None:
    return conn.execute("SELECT * FROM reports WHERE failure_id = %s ORDER BY created_at DESC, id DESC LIMIT 1",
                        (failure_id,)).fetchone()
