"""The FormBondhu harness: read -> match -> audit -> (double-check || explain) -> result.

Gemma 4 does the seeing and the Bangla writing; plain code does the deciding. run() is an async
generator of trace events so the UI can show every step, its model or tool, and its timing as it happens.
"""
import asyncio
import time

from pydantic import BaseModel, ValidationError

from app.gemma import GemmaError, generate_json
from app.rules import apply_verification, audit, match_card, merge_explanations


class FieldRead(BaseModel):
    label_en: str = ""
    label_bn: str = ""
    value: str = ""
    is_empty: bool = False


class SignatureRead(BaseModel):
    label: str = ""
    has_ink: bool


class PhotoRead(BaseModel):
    present: bool = False
    filled: bool = False


class Extraction(BaseModel):
    form_title: str
    fields: list[FieldRead]
    signature_boxes: list[SignatureRead] = []
    photo_box: PhotoRead | None = None


class Check(BaseModel):
    rule_id: str
    confirmed: bool
    seen: str = ""


class Checks(BaseModel):
    checks: list[Check]


class Fix(BaseModel):
    rule_id: str
    bn: str
    en: str = ""


class Fixes(BaseModel):
    items: list[Fix]


READ_PROMPT = """You are the perception step of FormBondhu, a tool that checks university paper forms before students submit them.
Look at the image of the form and report ONLY what is visibly there. Do not judge whether anything is correct.
- Copy every handwritten or typed value EXACTLY as written, character for character. Keep dates exactly as written (12/3/26 stays 12/3/26).
- For every field row give the printed English label and the printed Bangla label if there is one.
- If a field has nothing written in it, use value "" and is_empty true.
- signature_boxes: every place meant for a signature, labelled with its printed caption. has_ink is true only if pen strokes or a drawn signature are visible there.
- photo_box: present is true if the form has a box for a photo. filled is true if a photo or any picture is pasted or drawn inside it; false if it is blank or only shows placeholder text.
Return JSON exactly in this shape:
{"form_title": "main printed title", "fields": [{"label_en": "", "label_bn": "", "value": "", "is_empty": false}], "signature_boxes": [{"label": "", "has_ink": false}], "photo_box": {"present": false, "filled": false}}"""

VERIFY_PROMPT = """You are the double-check step of FormBondhu. A rule engine flagged the possible problems below on this form.
Look at the image again carefully for each one. Confirm a problem only if you can actually see it in the image.
If the image shows it is not a real problem (for example the signature is there, or the value is written correctly), set confirmed to false.
In "seen", say in a few words exactly what you see at that spot, quoting any text exactly.
Problems:
{problems}
Return JSON: {{"checks": [{{"rule_id": "", "confirmed": true, "seen": ""}}]}} with one entry per problem."""

EXPLAIN_PROMPT = """You write fix-it instructions for FormBondhu, for a university student in Bangladesh about to submit the paper form "{title_en}" ({title_bn}).
For each problem below write ONE short, friendly instruction in simple standard Bangla saying exactly what to write or do to fix it,
using what was read from their form where helpful. Anything the student must write on the form (dates, IDs, course codes, sessions)
must appear exactly as it should be written on the form, in English digits and letters (write 12/03/2026, never ১২/০৩/২০২৬). Also give a short English version.
Use ONLY the rule text given. Never add new requirements, fees, offices or deadlines.
Problems:
{problems}
Return JSON: {{"items": [{{"rule_id": "", "bn": "", "en": ""}}]}}"""

STEP_TITLES = {
    "read": ("Read the form", "ফর্ম পড়া"),
    "match": ("Match the rule card", "নিয়মের কার্ড মেলানো"),
    "audit": ("Check every rule", "প্রতিটি নিয়ম যাচাই"),
    "verify": ("Double-check each problem", "প্রতিটি সমস্যা আবার দেখা"),
    "explain": ("Write fixes in Bangla", "বাংলায় সমাধান লেখা"),
}


def _step(step_id, status, kind, **extra):
    title_en, title_bn = STEP_TITLES[step_id]
    return {"type": "step", "id": step_id, "status": status, "kind": kind,
            "title_en": title_en, "title_bn": title_bn, **extra}


async def call_validated(prompt, schema, engine, *, image=None, mime="image/jpeg"):
    """One Gemma call checked against a schema; a malformed answer gets one retry with the error fed back."""
    data, meta = await generate_json(prompt, image=image, mime=mime, **engine)
    try:
        return schema.model_validate(data), {**meta, "retried": False}
    except ValidationError as exc:
        repair = f"{prompt}\n\nYour previous JSON did not match the schema: {exc.errors()[:3]}. Return corrected JSON only."
        data, meta2 = await generate_json(repair, image=image, mime=mime, **engine)
        return schema.model_validate(data), {**meta2, "ms": meta["ms"] + meta2["ms"], "retried": True}


def _problem_lines(flags):
    return "\n".join(f'- rule_id: {f["rule_id"]} | where: {f["label_en"]} | what was read: "{f["read"]}" | rule: {f["en"]}'
                     for f in flags)


async def _named(name, coro):
    return name, await coro


async def run(image, mime, cards, engine):
    """engine = {"backend": "aistudio" | "ollama", "model": str}; it is used for every model call and echoed in every event."""
    started = time.perf_counter()
    try:
        yield _step("read", "start", "model", **engine)
        extraction, meta = await call_validated(READ_PROMPT, Extraction, engine, image=image, mime=mime)
        ext = extraction.model_dump()
        yield _step("read", "done", "model", **meta, output=ext)

        card, score = match_card(ext["form_title"], cards)
        yield _step("match", "done", "code", tool="match_card",
                    output={"form_title": ext["form_title"], "card": card and card["id"], "score": round(score, 2)})
        if card is None:
            yield {"type": "result", "status": "unknown_form", "form_title": ext["form_title"],
                   "known": [{"title_en": c["title_en"], "title_bn": c["title_bn"]} for c in cards.values()], "engine": engine,
                   "ms": round((time.perf_counter() - started) * 1000)}
            return

        flags, passed = audit(card, ext)
        yield _step("audit", "done", "code", tool="audit",
                    output={"flagged": [f["rule_id"] for f in flags], "passed": [p["rule_id"] for p in passed]})

        confirmed, manual = [], []
        if flags:
            problems = _problem_lines(flags)
            yield _step("verify", "start", "model", **engine)
            yield _step("explain", "start", "model", **engine)
            tasks = [_named("verify", call_validated(VERIFY_PROMPT.format(problems=problems), Checks, engine, image=image, mime=mime)),
                     _named("explain", call_validated(EXPLAIN_PROMPT.format(problems=problems, title_en=card["title_en"],
                                                                            title_bn=card["title_bn"]), Fixes, engine))]
            results = {}
            for next_done in asyncio.as_completed(tasks):
                name, (parsed, meta) = await next_done
                results[name] = parsed
                yield _step(name, "done", "model", **meta, output=parsed.model_dump())
            confirmed, manual = apply_verification(flags, [c.model_dump() for c in results["verify"].checks])
            fixes = [i.model_dump() for i in results["explain"].items]
            confirmed, manual = merge_explanations(confirmed, fixes), merge_explanations(manual, fixes)

        yield {"type": "result", "status": "problems" if confirmed else ("check_manually" if manual else "ready"),
               "card": {k: card[k] for k in ("id", "title_en", "title_bn", "office_en", "sample_data")},
               "problems": confirmed, "manual": manual, "passed": passed,
               "attachments": card["attachments"], "route": card["route"], "engine": engine,
               "ms": round((time.perf_counter() - started) * 1000)}
    except (GemmaError, ValidationError) as exc:
        yield {"type": "error", "message": str(exc)}
