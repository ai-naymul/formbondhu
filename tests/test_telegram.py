"""Telegram front end, offline: Telegram's API is mocked and the harness is replaced with a canned result."""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import telegram_bot
from app.rules import load_cards

CARDS = load_cards()
RESULT = {
    "type": "result", "status": "problems", "ms": 25000,
    "card": {"id": "transcript_letter", "kind": "letter", "title_en": "Application letter for academic transcript",
             "title_bn": "ট্রান্সক্রিপ্টের জন্য দরখাস্ত"},
    "problems": [{"rule_id": "TL-5", "label_bn": "আইডি", "fix_bn": "আইডি লিখুন <C231045>"}],
    "manual": [], "attachments": [{"bn": "রসিদ", "en": "slip"}],
    "route": [{"office_bn": "হিসাব শাখা", "task_bn": "ফি দিন"}],
    "engine": {"backend": "aistudio", "model": "gemma-4-31b-it"},
    "draft": {"letter": "To\nThe Controller of Examinations\nID: [your student ID]"},
}


@pytest.fixture
def telegram(monkeypatch):
    """Record every Telegram API call and serve a fake photo download."""
    calls = []

    def handler(request):
        if "/file/bot" in str(request.url):
            return httpx.Response(200, content=b"jpeg-bytes")
        method = str(request.url).rsplit("/", 1)[1]
        body = json.loads(request.content or b"{}")
        calls.append((method, body))
        if method == "getFile":
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "photos/1.jpg"}})
        return httpx.Response(200, json={"ok": True, "result": {}})

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test")
    monkeypatch.setattr(telegram_bot, "_transport", httpx.MockTransport(handler))
    return calls


def test_start_message_lists_known_documents(telegram):
    asyncio.run(telegram_bot.handle_update({"message": {"chat": {"id": 7}, "text": "/start"}}, CARDS, {}))
    method, body = telegram[-1]
    assert method == "sendMessage" and body["chat_id"] == 7
    assert all(c["title_bn"] in body["text"] for c in CARDS.values())


def test_photo_runs_the_harness_and_sends_verdict_and_letter(telegram, monkeypatch):
    seen = {}

    async def fake_run(image, mime, cards, engine):
        seen["image"], seen["engine"] = image, engine
        yield {"type": "step", "id": "read", "status": "done"}
        yield RESULT

    monkeypatch.setattr(telegram_bot, "run", fake_run)
    update = {"message": {"chat": {"id": 9}, "photo": [{"file_id": "small"}, {"file_id": "large"}]}}
    asyncio.run(telegram_bot.handle_update(update, CARDS, {"backend": "aistudio", "model": "m"}))
    assert seen["image"] == b"jpeg-bytes"
    assert ("getFile", {"file_id": "large"}) in telegram  # the biggest photo size is used
    texts = [body["text"] for method, body in telegram if method == "sendMessage"]
    assert "১টি কারণে ফেরত আসবে" in texts[-2] and "&lt;C231045&gt;" in texts[-2]  # escaped for HTML mode
    assert "[your student ID]" in texts[-1]


def test_unknown_form_message_is_honest():
    messages = telegram_bot.format_result({"type": "result", "status": "unknown_form", "form_title": "Library card",
                                           "known": [{"title_bn": "বাস রিকুইজিশন ফরম"}], "ms": 9000})
    assert "আন্দাজ করছি না" in messages[0] and "Library card" in messages[0]


def test_webhook_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "right")
    from app.main import app
    client = TestClient(app)
    assert client.post("/api/telegram/wrong", json={}).status_code == 404
