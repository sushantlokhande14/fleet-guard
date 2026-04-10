"""Minimal OpenAI-compatible chat client.

Defaults to a local Ollama server (no API key, nothing leaves the machine); any
OpenAI-compatible endpoint works by setting FG_LLM_BASE_URL / FG_LLM_MODEL /
FG_LLM_API_KEY.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b"


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    content: dict[str, Any]
    raw: str
    model: str
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model did not return JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise LLMError("model returned JSON that is not an object")
    return obj


class LLMClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None,
                 timeout_s: float | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or os.environ.get("FG_LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("FG_LLM_MODEL") or DEFAULT_MODEL
        key = api_key if api_key is not None else os.environ.get("FG_LLM_API_KEY", "")
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        timeout = timeout_s or float(os.environ.get("FG_LLM_TIMEOUT", "180"))
        self._http = httpx.Client(base_url=self.base_url, headers=headers, timeout=timeout, transport=transport)

    def chat_json(self, system: str, user: str, temperature: float = 0.1) -> LLMResult:
        body = {
            "model": self.model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        t0 = time.monotonic()
        try:
            r = self._http.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM endpoint unreachable at {self.base_url}: {exc}") from exc
        if r.status_code != 200:
            raise LLMError(f"LLM endpoint returned {r.status_code}: {r.text[:200]}")
        data = r.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected response shape from LLM endpoint") from exc
        usage = data.get("usage") or {}
        return LLMResult(content=_parse_json(text), raw=text, model=data.get("model", self.model),
                         latency_s=round(time.monotonic() - t0, 2), prompt_tokens=usage.get("prompt_tokens"),
                         completion_tokens=usage.get("completion_tokens"))

    def close(self) -> None:
        self._http.close()
