"""Gemma 4 client with two engines: Google AI Studio (hosted) and Ollama (on your own machine).

Both engines run the same open-weights Gemma 4 family and return (parsed_json, meta) with
meta = {"backend", "model", "ms"}, so the harness never needs to know which one answered.
"""
import base64
import json
import os
import time

import httpx

AISTUDIO_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
BACKENDS = ("aistudio", "ollama")
OLLAMA_PULL_HINT = "ollama pull gemma4   (tags: https://ollama.com/library/gemma4)"
_transport = None  # tests replace this with an httpx.MockTransport


class GemmaError(RuntimeError):
    pass


def default_backend():
    backend = os.environ.get("DEFAULT_BACKEND", "aistudio")
    return backend if backend in BACKENDS else "aistudio"


def aistudio_model():
    return os.environ.get("GEMMA_MODEL", "gemma-4-31b-it")


def ollama_url():
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _client(timeout):
    return httpx.AsyncClient(timeout=timeout, transport=_transport)


def build_aistudio_body(prompt, image=None, mime="image/jpeg"):
    """Thinking is set to minimal: on form reading it gave the same answers as the default
    at roughly a quarter of the latency (8-11 s instead of 40-48 s per call)."""
    parts = []
    if image is not None:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(image).decode()}})
    parts.append({"text": prompt})
    return {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "thinkingConfig": {"thinkingLevel": "minimal"}}}


def parse_aistudio(payload):
    parts = payload["candidates"][0]["content"]["parts"]
    return json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))


def build_ollama_body(prompt, model, image=None):
    message = {"role": "user", "content": prompt}
    if image is not None:
        message["images"] = [base64.b64encode(image).decode()]
    return {"model": model, "messages": [message], "format": "json", "stream": False,
            "options": {"temperature": 0}}


def parse_ollama(payload):
    return json.loads(payload["message"]["content"])


async def generate_json(prompt, *, image=None, mime="image/jpeg", backend=None, model=None):
    """Send one prompt (optionally with an image) to the chosen engine and return (parsed_json, meta)."""
    backend = backend or default_backend()
    started = time.perf_counter()
    if backend == "aistudio":
        key = os.environ.get("GEMMA_API_KEY")
        if not key:
            raise GemmaError("GEMMA_API_KEY is not set")
        model = model or aistudio_model()
        async with _client(90) as client:
            resp = await client.post(AISTUDIO_URL.format(model=model), json=build_aistudio_body(prompt, image, mime),
                                     headers={"x-goog-api-key": key})
        parse = parse_aistudio
    elif backend == "ollama":
        if not model:
            raise GemmaError("No local Gemma model selected")
        try:
            # Vision on a laptop is slow, so the local engine gets a generous timeout.
            async with _client(180) as client:
                resp = await client.post(f"{ollama_url()}/api/chat", json=build_ollama_body(prompt, model, image))
        except httpx.ConnectError as exc:
            raise GemmaError(f"Cannot reach Ollama at {ollama_url()}; is it running?") from exc
        parse = parse_ollama
    else:
        raise GemmaError(f"Unknown backend {backend!r}")
    ms = round((time.perf_counter() - started) * 1000)
    if resp.status_code != 200:
        raise GemmaError(f"{backend} returned {resp.status_code}: {resp.text[:300]}")
    try:
        return parse(resp.json()), {"backend": backend, "model": model, "ms": ms}
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise GemmaError(f"Unreadable {backend} response: {exc}") from exc


async def engines_status():
    """Report which engines this machine can actually use, and why not when it can't."""
    key_set = bool(os.environ.get("GEMMA_API_KEY"))
    aistudio = {"id": "aistudio", "label": "Google AI Studio", "available": key_set,
                "models": [aistudio_model()], "default_model": aistudio_model(),
                "reason": None if key_set else "GEMMA_API_KEY is not set on this server"}
    ollama = {"id": "ollama", "label": "Local Ollama", "available": False, "models": [],
              "default_model": None, "url": ollama_url(), "reason": None}
    try:
        async with _client(2) as client:
            resp = await client.get(f"{ollama_url()}/api/tags")
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        gemmas = [n for n in names if "gemma" in n.lower()]
        if gemmas:
            preferred = os.environ.get("OLLAMA_MODEL")
            ollama.update(available=True, models=gemmas,
                          default_model=preferred if preferred in gemmas else gemmas[0])
        else:
            ollama["reason"] = f"Ollama is running but has no Gemma model. Run: {OLLAMA_PULL_HINT}"
    except (httpx.HTTPError, ValueError):
        ollama["reason"] = (f"Ollama is not running at {ollama_url()}. To use your own Gemma, clone the repo, "
                            f"install Ollama, then: {OLLAMA_PULL_HINT}")
    return {"default": default_backend(), "engines": [aistudio, ollama]}
