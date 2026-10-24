"""Telegram front end: send a photo of a form or application letter, get the verdict back in Bangla.

It runs the same harness as the web app. Two ways to run it:
- Polling, from a laptop with no public URL: TELEGRAM_BOT_TOKEN=... python -m app.telegram_bot
- Webhook, when deployed: Telegram posts updates to /api/telegram/<TELEGRAM_WEBHOOK_SECRET> (see README).
"""
import asyncio
import html
import os

import httpx

from app.harness import run

API = "https://api.telegram.org/bot{token}/{method}"
FILE_URL = "https://api.telegram.org/file/bot{token}/{path}"
MAX_MESSAGE = 4000  # Telegram's limit is 4096 characters
_transport = None  # tests replace this with an httpx.MockTransport

VERDICT = {
    "problems": "🔴 {n}টি কারণে ফেরত আসবে",
    "check_manually": "🟡 নিজে একবার দেখে নিন",
    "ready": "🟢 জমা দেওয়ার জন্য প্রস্তুত",
    "unknown_form": "⚪ অচেনা ফর্ম",
}


def _token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return token


async def tg(client, method, **params):
    resp = await client.post(API.format(token=_token(), method=method), json=params)
    return resp.json()


async def download_photo(client, file_id):
    info = await tg(client, "getFile", file_id=file_id)
    resp = await client.get(FILE_URL.format(token=_token(), path=info["result"]["file_path"]))
    return resp.content


def welcome(cards):
    known = "\n".join(f"• {html.escape(c['title_bn'])} ({html.escape(c['title_en'])})" for c in cards.values())
    return ("<b>ফর্মবন্ধু</b>: অফিসে যাওয়ার আগে ফর্ম বা দরখাস্ত মিলিয়ে নিন।\n"
            "একটি পরিষ্কার ছবি পাঠান। Gemma 4 দেখে বলবে কোথায় ভুল আর কীভাবে ঠিক করবেন।\n"
            "Send a clear photo of a filled form or your application letter.\n\n"
            f"যা চেনে / What it knows:\n{known}\n\n<i>নমুনা নিয়ম, IIUC-এর অফিসিয়াল নিয়ম নয়। Sample rules.</i>")


def format_result(result):
    """Turn the harness's final event into one or two Telegram HTML messages."""
    esc = html.escape
    if result["status"] == "unknown_form":
        known = ", ".join(esc(k["title_bn"]) for k in result["known"])
        return [f"{VERDICT['unknown_form']}\nএই নথির নিয়ম আমার কাছে নেই, তাই আন্দাজ করছি না।\n"
                f"It read the title as \"{esc(result['form_title'])}\".\n\nযা চেনে: {known}"]
    count = len(result.get("problems", []))
    bn_count = str(count).translate(str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯"))
    lines = [f"<b>{VERDICT[result['status']].format(n=bn_count)}</b>",
             f"{esc(result['card']['title_bn'])} ({esc(result['card']['title_en'])})", ""]
    for p in result.get("problems", []):
        lines.append(f"• <b>{esc(p['label_bn'])}</b>: {esc(p['fix_bn'])}")
    if result.get("manual"):
        lines += ["", "নিজে একবার দেখুন (second look could not confirm):"]
        lines += [f"• {esc(p['label_bn'])}: {esc(p['fix_bn'])}" for p in result["manual"]]
    if result.get("attachments"):
        lines += ["", "<b>সাথে যা নিতে হবে</b>"] + [f"☐ {esc(a['bn'])}" for a in result["attachments"]]
    if result.get("route"):
        lines += ["", "<b>কোন অফিসে, কোন ক্রমে</b>"]
        lines += [f"{i}. {esc(s['office_bn'])}: {esc(s['task_bn'])}" for i, s in enumerate(result["route"], 1)]
    engine = result.get("engine", {})
    lines += ["", f"<i>Gemma 4 ({esc(engine.get('model', ''))}), {result['ms'] / 1000:.0f} s. নমুনা নিয়ম / sample rules.</i>"]
    messages = ["\n".join(lines)[:MAX_MESSAGE]]
    if result.get("draft"):
        messages.append(f"<b>সংশোধিত দরখাস্ত / Corrected letter</b>\n<pre>{esc(result['draft']['letter'])[:MAX_MESSAGE - 80]}</pre>")
    return messages


async def handle_update(update, cards, engine):
    """Answer one Telegram update. Photos run the full harness; anything else gets the instructions."""
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        return
    async with httpx.AsyncClient(timeout=60, transport=_transport) as client:
        file_id, mime = None, "image/jpeg"
        if message.get("photo"):
            file_id = message["photo"][-1]["file_id"]  # Telegram lists sizes small to large
        elif (message.get("document") or {}).get("mime_type", "").startswith("image/"):
            file_id, mime = message["document"]["file_id"], message["document"]["mime_type"]
        if file_id is None:
            await tg(client, "sendMessage", chat_id=chat_id, text=welcome(cards), parse_mode="HTML")
            return
        await tg(client, "sendMessage", chat_id=chat_id, text="যাচাই চলছে, ২০-৩০ সেকেন্ড লাগবে… Checking, about 20-30 seconds.")
        await tg(client, "sendChatAction", chat_id=chat_id, action="typing")
        image = await download_photo(client, file_id)
        final = None
        async for event in run(image, mime, cards, engine):
            if event["type"] in ("result", "error"):
                final = event
        if final is None or final["type"] == "error":
            detail = html.escape((final or {}).get("message", "no result"))
            await tg(client, "sendMessage", chat_id=chat_id, parse_mode="HTML",
                     text=f"যাচাই শেষ করা যায়নি। The check could not finish.\n<code>{detail}</code>")
            return
        for text in format_result(final):
            await tg(client, "sendMessage", chat_id=chat_id, text=text, parse_mode="HTML")


async def poll():
    """Long-poll Telegram from a laptop; each update is handled concurrently."""
    from app.main import CARDS, _pick_engine  # imported here: main also imports this module for the webhook

    offset = None
    async with httpx.AsyncClient(timeout=70) as client:
        me = await tg(client, "getMe")
        print(f"FormBondhu bot running as @{me['result']['username']}", flush=True)
        while True:
            updates = await tg(client, "getUpdates", timeout=50, offset=offset)
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                asyncio.create_task(handle_update(update, CARDS, await _pick_engine(None, None)))


if __name__ == "__main__":
    asyncio.run(poll())
