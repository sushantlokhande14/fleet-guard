import json

import httpx
import pytest

from fleetguard.diagnostics.llm import LLMClient, LLMError


def client_returning(content=None, status=200, raw=None, seen=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if raw is not None:
            return httpx.Response(status, json=raw)
        return httpx.Response(status, json={
            "model": "test-model",
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 40},
        })

    return LLMClient(base_url="http://llm.test/v1", model="m", api_key="", transport=httpx.MockTransport(handler))


def test_json_round_trip_and_request_shape():
    seen = []
    c = client_returning(json.dumps({"summary": "ok"}), seen=seen)
    r = c.chat_json("sys", "user")
    assert r.content == {"summary": "ok"}
    assert (r.model, r.prompt_tokens, r.completion_tokens) == ("test-model", 120, 40)
    body = json.loads(seen[0].content)
    assert seen[0].url.path == "/v1/chat/completions"
    assert body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert "authorization" not in seen[0].headers  # local Ollama needs no key


def test_api_key_is_sent_when_configured():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    LLMClient(base_url="http://x/v1", api_key="sk-test", transport=httpx.MockTransport(handler)).chat_json("s", "u")
    assert seen[0].headers["authorization"] == "Bearer sk-test"


def test_fenced_json_is_accepted():
    c = client_returning('```json\n{"a": 1}\n```')
    assert c.chat_json("s", "u").content == {"a": 1}


@pytest.mark.parametrize("content,match", [("not json at all", "did not return JSON"),
                                           ("[1, 2]", "not an object")])
def test_bad_content(content, match):
    with pytest.raises(LLMError, match=match):
        client_returning(content).chat_json("s", "u")


def test_http_errors():
    with pytest.raises(LLMError, match="returned 500"):
        client_returning("{}", status=500).chat_json("s", "u")
    with pytest.raises(LLMError, match="unexpected response shape"):
        client_returning(raw={"nope": True}).chat_json("s", "u")

    def boom(request):
        raise httpx.ConnectError("refused")

    c = LLMClient(base_url="http://down/v1", transport=httpx.MockTransport(boom))
    with pytest.raises(LLMError, match="unreachable"):
        c.chat_json("s", "u")


def test_env_defaults(monkeypatch):
    monkeypatch.setenv("FG_LLM_BASE_URL", "http://example:1234/v1/")
    monkeypatch.setenv("FG_LLM_MODEL", "llama3.1:8b")
    c = LLMClient()
    assert (c.base_url, c.model) == ("http://example:1234/v1", "llama3.1:8b")
