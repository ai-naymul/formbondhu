"""The FormBondhu harness: read -> match -> audit -> (double-check || explain) -> result.

Gemma 4 does the seeing and the Bangla writing; plain code does the deciding. run() is an async
generator of trace events so the UI can show every step, its model or tool, and its timing as it happens.
"""
import asyncio
import json
import re
import time

from pydantic import BaseModel, ValidationError

from app.gemma import GemmaError, generate_json
from app.rules import apply_verification, audit, map_fields, match_card, merge_explanations


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
    doc_type: str = "form"
    language: str = "en"
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


class Draft(BaseModel):
    language: str = "bn"
    letter: str
    placeholders: list[str] = []


LETTER_SLOTS = ["Addressee", "Date", "Subject", "Request", "Leave Dates", "Reason",
                "Student Name", "Student ID", "Department", "Semester"]

READ_PROMPT = """You are the perception step of FormBondhu, a tool that checks university paperwork before students submit it.
First decide what the document is:
- "form": a printed form with labelled boxes or rows to fill in.
- "letter": a written application letter (দরখাস্ত) addressed to an official, in Bangla, English or Banglish, handwritten or typed.
Report ONLY what is visibly there. Do not judge whether anything is correct.
- Copy written values EXACTLY as written, character for character. Keep dates exactly as written (12/3/26 stays 12/3/26).
- If something is not written, use value "" and is_empty true.
For a form: form_title is the main printed title; give one entry per field row with its printed English label and the printed Bangla label if any.
For a letter: form_title is the subject line exactly as written (or the main request if there is no subject line). Give exactly one entry for each of
these label_en values, in this order: {slots}. Addressee is the "To"/"বরাবর" lines (designation and office). Request is one short phrase saying what is asked for.
Copy each value from the letter in its original language; leave it "" if the letter does not contain it.
- signature_boxes: every place meant for a signature, labelled with its printed caption (for a letter, use "Student's Signature" for the sender's signature). has_ink is true only if pen strokes or a drawn signature are visible there.
- photo_box: present is true if there is a box for a photo; filled is true if a photo or any picture is inside it.
- language: "bn", "en" or "mixed", the main language the student wrote in.
Return JSON exactly in this shape:
{{"doc_type": "form", "language": "en", "form_title": "", "fields": [{{"label_en": "", "label_bn": "", "value": "", "is_empty": false}}], "signature_boxes": [{{"label": "", "has_ink": false}}], "photo_box": {{"present": false, "filled": false}}}}""".format(slots=", ".join(LETTER_SLOTS))

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

DRAFT_PROMPT = """You help a student at International Islamic University Chittagong rewrite an application letter so the office accepts it.
Write the complete corrected letter in {language}, in the usual Bangladeshi university application format:
date, then "To"/"বরাবর" and the addressee lines, subject line, salutation, body, closing, signature line, then name, ID, department and semester.
Address it to: {addressee}
Fix these problems:
{problems}
Keep every detail the student gave (purpose, dates, reasons). Use ONLY facts from the student's letter below. Where something required is missing, write a placeholder in square brackets,
e.g. [your student ID] or [আপনার আইডি নম্বর]. Never invent names, IDs, dates, reasons or fees. Write numbers and IDs in English digits.
Student's letter as read: {facts}
Return JSON: {{"language": "bn or en", "letter": "the full letter with \\n line breaks", "placeholders": ["each placeholder you used"]}}"""

STEP_TITLES = {
    "read": ("Read the form", "ফর্ম পড়া"),
    "match": ("Match the rule card", "নিয়মের কার্ড মেলানো"),
    "audit": ("Check every rule", "প্রতিটি নিয়ম যাচাই"),
    "verify": ("Double-check each problem", "প্রতিটি সমস্যা আবার দেখা"),
    "explain": ("Write fixes in Bangla", "বাংলায় সমাধান লেখা"),
    "draft": ("Draft the corrected letter", "সংশোধিত দরখাস্ত লেখা"),
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


STUDENT_ID = re.compile(r"\b[A-Z]\d{6}\b")


def ground_draft(draft, read_id):
    """Code-side check on the model's letter: any student ID it wrote must be the one read from the original.

    Returns (letter, replaced) where invented IDs are swapped for a visible placeholder.
    """
    replaced = [m for m in STUDENT_ID.findall(draft) if m != read_id]
    letter = STUDENT_ID.sub(lambda m: m.group(0) if m.group(0) == read_id else "[আইডি যাচাই করুন / check ID]", draft)
    return letter, replaced


def _addressee(card, values):
    lang_bn = card.get("addressee_bn", "")
    return (card.get("addressee_en", "") + " / " + lang_bn).replace("{department}", values.get("department") or "[department]")


async def run(image, mime, cards, engine):
    """engine = {"backend": "aistudio" | "ollama", "model": str}; it is used for every model call and echoed in every event."""
    started = time.perf_counter()
    try:
        yield _step("read", "start", "model", **engine)
        extraction, meta = await call_validated(READ_PROMPT, Extraction, engine, image=image, mime=mime)
        ext = extraction.model_dump()
        yield _step("read", "done", "model", **meta, output=ext)

        card, score = match_card(ext["form_title"], cards, ext["doc_type"])
        yield _step("match", "done", "code", tool="match_card",
                    output={"doc_type": ext["doc_type"], "form_title": ext["form_title"], "card": card and card["id"],
                            "score": round(score, 2)})
        if card is None:
            yield {"type": "result", "status": "unknown_form", "form_title": ext["form_title"],
                   "known": [{"title_en": c["title_en"], "title_bn": c["title_bn"]} for c in cards.values()], "engine": engine,
                   "ms": round((time.perf_counter() - started) * 1000)}
            return

        flags, passed = audit(card, ext)
        yield _step("audit", "done", "code", tool="audit",
                    output={"flagged": [f["rule_id"] for f in flags], "passed": [p["rule_id"] for p in passed]})

        confirmed, manual, draft = [], [], None
        if flags:
            problems = _problem_lines(flags)
            yield _step("verify", "start", "model", **engine)
            yield _step("explain", "start", "model", **engine)
            tasks = [_named("verify", call_validated(VERIFY_PROMPT.format(problems=problems), Checks, engine, image=image, mime=mime)),
                     _named("explain", call_validated(EXPLAIN_PROMPT.format(problems=problems, title_en=card["title_en"],
                                                                            title_bn=card["title_bn"]), Fixes, engine))]
            if card.get("kind") == "letter":
                values = map_fields(card, ext["fields"])
                language = "formal English" if ext["language"] == "en" else "formal standard Bangla (চলিত ভাষা)"
                facts = {f["label_en"]: values.get(f["key"]) or "" for f in card["fields"]}
                yield _step("draft", "start", "model", **engine)
                tasks.append(_named("draft", call_validated(
                    DRAFT_PROMPT.format(language=language, addressee=_addressee(card, values), problems=problems,
                                        facts=json.dumps(facts, ensure_ascii=False)), Draft, engine)))
            results = {}
            for next_done in asyncio.as_completed(tasks):
                name, (parsed, meta) = await next_done
                results[name] = parsed
                output = parsed.model_dump()
                if name == "draft":
                    letter, replaced = ground_draft(parsed.letter, values.get("student_id") or "")
                    draft = {**output, "letter": letter, "invented_ids_removed": replaced}
                    output = {**draft, "grounding_check": "passed" if not replaced else f"replaced {len(replaced)} invented ID(s)"}
                yield _step(name, "done", "model", **meta, output=output)
            confirmed, manual = apply_verification(flags, [c.model_dump() for c in results["verify"].checks])
            fixes = [i.model_dump() for i in results["explain"].items]
            confirmed, manual = merge_explanations(confirmed, fixes), merge_explanations(manual, fixes)

        yield {"type": "result", "status": "problems" if confirmed else ("check_manually" if manual else "ready"),
               "card": {k: card.get(k) for k in ("id", "kind", "title_en", "title_bn", "office_en", "sample_data", "source")},
               "problems": confirmed, "manual": manual, "passed": passed,
               "attachments": card["attachments"], "route": card["route"], "engine": engine, "draft": draft,
               "ms": round((time.perf_counter() - started) * 1000)}
    except (GemmaError, ValidationError) as exc:
        yield {"type": "error", "message": str(exc)}
