"""Both Gemma engines, tested offline: request shape, response parsing and availability reporting."""
import asyncio
import base64
import json

import httpx
import pytest

from app import gemma


@pytest.fixture
def mock_http(monkeypatch):
    """Route every client request to a handler the test provides."""
    def install(handler):
        monkeypatch.setattr(gemma, "_transport", httpx.MockTransport(handler))
    return install


def test_aistudio_body_has_image_json_mode_and_minimal_thinking():
    body = gemma.build_aistudio_body("read this", b"img", "image/png")
    parts = body["contents"][0]["parts"]
    assert parts[0]["inline_data"] == {"mime_type": "image/png", "data": base64.b64encode(b"img").decode()}
    assert parts[1]["text"] == "read this"
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "minimal"}


def test_aistudio_parse_skips_thought_parts():
    payload = {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": '{"ok": 1}'}]}}]}
    assert gemma.parse_aistudio(payload) == {"ok": 1}


def test_ollama_body_and_parse():
    body = gemma.build_ollama_body("read this", "gemma4:e4b", b"img")
    assert body["model"] == "gemma4:e4b" and body["format"] == "json" and body["stream"] is False
    assert body["messages"][0]["images"] == [base64.b64encode(b"img").decode()]
    assert gemma.parse_ollama({"message": {"content": '{"ok": 2}'}}) == {"ok": 2}


def test_generate_json_aistudio(mock_http, monkeypatch):
    monkeypatch.setenv("GEMMA_API_KEY", "test-key")
    seen = {}

    def handler(request):
        seen["key"], seen["url"] = request.headers["x-goog-api-key"], str(request.url)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"form_title": "X"}'}]}}]})

    mock_http(handler)
    data, meta = asyncio.run(gemma.generate_json("p", backend="aistudio", model="gemma-4-26b-a4b-it"))
    assert data == {"form_title": "X"}
    assert meta["backend"] == "aistudio" and meta["model"] == "gemma-4-26b-a4b-it"
    assert seen["key"] == "test-key" and "gemma-4-26b-a4b-it:generateContent" in seen["url"]


def test_generate_json_ollama(mock_http, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://ollama.test:11434")

    def handler(request):
        assert str(request.url) == "http://ollama.test:11434/api/chat"
        assert json.loads(request.content)["model"] == "gemma4:e4b"
        return httpx.Response(200, json={"message": {"content": '{"checks": []}'}})

    mock_http(handler)
    data, meta = asyncio.run(gemma.generate_json("p", image=b"x", backend="ollama", model="gemma4:e4b"))
    assert data == {"checks": []} and meta["backend"] == "ollama"


def test_ollama_unreachable_is_a_clear_error(mock_http):
    def handler(request):
        raise httpx.ConnectError("refused")

    mock_http(handler)
    with pytest.raises(gemma.GemmaError, match="Cannot reach Ollama"):
        asyncio.run(gemma.generate_json("p", backend="ollama", model="gemma4:e4b"))


def test_engines_status_when_ollama_is_down(mock_http, monkeypatch):
    monkeypatch.setenv("GEMMA_API_KEY", "k")

    def handler(request):
        raise httpx.ConnectError("refused")

    mock_http(handler)
    status = asyncio.run(gemma.engines_status())
    aistudio, ollama = status["engines"]
    assert aistudio["available"] and not ollama["available"]
    assert "not running" in ollama["reason"] and "ollama pull" in ollama["reason"]


def test_engines_status_lists_only_gemma_models(mock_http, monkeypatch):
    monkeypatch.delenv("GEMMA_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    mock_http(lambda r: httpx.Response(200, json={"models": [{"name": "llama3:8b"}, {"name": "gemma4:e4b"}]}))
    aistudio, ollama = asyncio.run(gemma.engines_status())["engines"]
    assert not aistudio["available"] and "GEMMA_API_KEY" in aistudio["reason"]
    assert ollama["available"] and ollama["models"] == ["gemma4:e4b"] and ollama["default_model"] == "gemma4:e4b"


def test_engines_status_running_ollama_without_gemma(mock_http):
    mock_http(lambda r: httpx.Response(200, json={"models": [{"name": "llama3:8b"}]}))
    ollama = asyncio.run(gemma.engines_status())["engines"][1]
    assert not ollama["available"] and "no Gemma model" in ollama["reason"]


def test_aistudio_retries_once_on_rate_limit(mock_http, monkeypatch):
    monkeypatch.setenv("GEMMA_API_KEY", "k")
    monkeypatch.setattr(gemma, "RETRY_DELAY", 0)
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]})

    mock_http(handler)
    data, _ = asyncio.run(gemma.generate_json("p", backend="aistudio"))
    assert data == {"ok": True} and len(calls) == 2


def test_aistudio_gives_a_clear_message_when_still_rate_limited(mock_http, monkeypatch):
    monkeypatch.setenv("GEMMA_API_KEY", "k")
    monkeypatch.setattr(gemma, "RETRY_DELAY", 0)
    mock_http(lambda r: httpx.Response(429, json={"error": "rate limited"}))
    with pytest.raises(gemma.GemmaError, match="rate limit"):
        asyncio.run(gemma.generate_json("p", backend="aistudio"))


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    body = TestClient(app).get("/api/health").json()
    assert body["ok"] is True and body["cards"] == 5
