"""FastAPI app: serves the phone UI, reports available Gemma engines, and streams each harness step."""
import json
import os
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.gemma import engines_status
from app.harness import run
from app.rules import load_cards
from app.telegram_bot import handle_update

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 4 * 1024 * 1024  # Vercel rejects request bodies over 4.5 MB; the browser shrinks photos well below this
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


def _load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


_load_env()
CARDS = load_cards()
app = FastAPI(title="FormBondhu")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/cards")
def cards():
    return list(CARDS.values())


@app.get("/api/engines")
async def engines():
    return await engines_status()


async def _pick_engine(backend, model):
    """Resolve the requested engine against what this machine can actually run."""
    status = await engines_status()
    backend = backend or status["default"]
    engine = next((e for e in status["engines"] if e["id"] == backend), None)
    if engine is None:
        raise HTTPException(400, f"Unknown engine {backend!r}")
    if not engine["available"]:
        raise HTTPException(503, engine["reason"])
    if model and model not in engine["models"]:
        raise HTTPException(400, f"Model {model!r} is not available on {engine['label']}")
    return {"backend": backend, "model": model or engine["default_model"]}


@app.post("/api/check")
async def check(image: UploadFile = File(...), backend: str | None = Form(None), model: str | None = Form(None)):
    data = await image.read()
    if not data:
        raise HTTPException(400, "Empty upload")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Image larger than 4 MB")
    mime = image.content_type if image.content_type in ALLOWED_MIME else "image/jpeg"
    engine = await _pick_engine(backend, model)

    async def events():
        async for event in run(data, mime, CARDS, engine):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/telegram/{secret}")
async def telegram_webhook(secret: str, update: dict = Body(...)):
    """Telegram webhook for the deployed bot; the secret path keeps strangers from posting fake updates."""
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if not expected or secret != expected:
        raise HTTPException(404, "Not found")
    await handle_update(update, CARDS, await _pick_engine(None, None))
    return {"ok": True}


# Mounted after the routes so API paths always reach the function (Vercel promotes this mount to its CDN).
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
