"""Deterministic half of the harness: rule cards, form matching, field mapping and the audit.

Nothing in this module calls a model. Gemma 4 reports what it sees; this code decides what is wrong,
so every flag can be traced to a rule id in a rule card that a human wrote.
"""
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent.parent / "rules"
MATCH_THRESHOLD = 0.6
BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def load_cards(rules_dir=RULES_DIR):
    return {c["id"]: c for c in (json.loads(p.read_text()) for p in sorted(rules_dir.glob("*.json")))}


def _norm(text):
    """Lowercase, drop bracketed hints like '(DD/MM/YYYY)' and punctuation, squeeze spaces."""
    text = re.sub(r"\(.*?\)", " ", (text or "").lower())
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def _similarity(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long_ = sorted((a, b), key=len)
    if short in long_:
        # Containment counts, but less than an exact match, so "Date" never beats "Missed Exam Date"
        # for the missed-exam field while a long printed title still matches its shorter alias.
        return 0.75 + 0.25 * len(short) / len(long_)
    return SequenceMatcher(None, a, b).ratio()


def _signature_owner(label):
    """'Course Teacher's Signature' -> 'course teacher', so the shared word 'signature' cannot drive a match."""
    return re.sub(r"\b(signature|sign|s)\b|স্বাক্ষর", " ", _norm(label)).strip()


def match_card(title, cards, kind=None):
    """Return (card, score) for the rule card whose title or alias best matches, or (None, score).

    kind ("form" or "letter") narrows the search when given, so a transcript *letter* never
    matches the transcript *form* card just because both mention transcripts.
    """
    pool = [c for c in cards.values() if kind is None or c.get("kind", "form") == kind] or list(cards.values())
    best, best_score = None, 0.0
    for card in pool:
        for name in [card["title_en"], card["title_bn"], *card.get("aliases", [])]:
            score = _similarity(title, name)
            if score > best_score:
                best, best_score = card, score
    return (best, best_score) if best_score >= MATCH_THRESHOLD else (None, best_score)


def map_fields(card, extracted_fields):
    """Map each card field key to the value the model read, matching on English or Bangla label.

    Returns {key: value or None}; None means the label was not found on the form at all.
    """
    mapped = {}
    for field in card["fields"]:
        best, best_score = None, 0.0
        for got in extracted_fields:
            score = max(_similarity(got.get("label_en", ""), field["label_en"]),
                        _similarity(got.get("label_bn", ""), field["label_bn"]))
            if score > best_score:
                best, best_score = got, score
        if best is None or best_score < MATCH_THRESHOLD:
            mapped[field["key"]] = None
        else:
            # Students often write numbers in Bangla digits (২৬/১০/২০২৬); rules compare the digits, not the script.
            value = "" if best.get("is_empty") else (best.get("value") or "").strip()
            mapped[field["key"]] = value.translate(BANGLA_DIGITS)
    return mapped


def _signature_inked(card, sig_key, boxes):
    """True/False if the matching signature box was found, None if no such box was seen."""
    sig = next(s for s in card["signatures"] if s["key"] == sig_key)
    best, best_score = None, 0.0
    for box in boxes:
        owner = _signature_owner(box.get("label", ""))
        score = max(_similarity(owner, _signature_owner(sig["label_en"])),
                    _similarity(owner, _signature_owner(sig["label_bn"])))
        if score > best_score:
            best, best_score = box, score
    if best is None or best_score < MATCH_THRESHOLD:
        # A form with a single signature line often gets a generic label; accept it for a single-signature card.
        if len(card["signatures"]) == 1 and len(boxes) == 1:
            return bool(boxes[0].get("has_ink"))
        return None
    return bool(best.get("has_ink"))


def _valid_date(value):
    """DD/MM/YYYY with "/", "." or "-" as the separator; a two-digit year or a one-digit day or month is not accepted."""
    match = re.fullmatch(r"(\d{2})[/.-](\d{2})[/.-](\d{4})", value)
    if not match:
        return False
    try:
        datetime.strptime("/".join(match.groups()), "%d/%m/%Y")
        return True
    except ValueError:
        return False


def _label(card, rule):
    if "field" in rule:
        f = next(f for f in card["fields"] if f["key"] == rule["field"])
        return f["label_en"], f["label_bn"]
    if "signature" in rule:
        s = next(s for s in card["signatures"] if s["key"] == rule["signature"])
        return s["label_en"], s["label_bn"]
    return "Photo", "ছবি"


def audit(card, extraction):
    """Apply every rule in the card to the model's extraction.

    Returns (flags, passed). Each flag carries the rule id, the human-written message and what was read.
    """
    values = map_fields(card, extraction.get("fields", []))
    boxes = extraction.get("signature_boxes", [])
    photo = extraction.get("photo_box") or {}
    flags, passed = [], []
    for rule in card["rules"]:
        kind, read, problem = rule["type"], None, False
        if kind in ("required", "pattern", "date", "contains_any"):
            read = values.get(rule["field"])
            if read is None or read == "":
                problem = True
            elif kind == "pattern":
                problem = not re.fullmatch(rule["pattern"], read)
            elif kind == "date":
                problem = not _valid_date(read)
            elif kind == "contains_any":
                problem = not any(word.lower() in read.lower() for word in rule["any"])
        elif kind == "signature":
            inked = _signature_inked(card, rule["signature"], boxes)
            read = {True: "ink seen", False: "empty", None: "box not found"}[inked]
            problem = inked is not True
        elif kind == "photo":
            read = "photo attached" if photo.get("filled") else "no photo"
            problem = card.get("photo_required", False) and not photo.get("filled")
        label_en, label_bn = _label(card, rule)
        entry = {"rule_id": rule["id"], "type": kind, "label_en": label_en, "label_bn": label_bn,
                 "read": read, "en": rule["en"], "bn": rule["bn"]}
        (flags if problem else passed).append(entry)
    return flags, passed


def apply_verification(flags, checks):
    """Split flags into (confirmed, needs_manual_check) using the second-look model call.

    A flag survives only if the second look explicitly confirms it; anything unconfirmed or missing
    from the model's answer goes to the manual list instead of being shown as a certain problem.
    """
    by_id = {c.get("rule_id"): c for c in checks}
    confirmed, manual = [], []
    for flag in flags:
        check = by_id.get(flag["rule_id"])
        flag = {**flag, "seen": (check or {}).get("seen", "")}
        (confirmed if check and check.get("confirmed") else manual).append(flag)
    return confirmed, manual


def merge_explanations(flags, items):
    """Attach model-written Bangla fixes to flags, ignoring any item whose rule id was not flagged.

    Falls back to the rule card's own text when the model skipped a flag, so output never depends on it.
    """
    by_id = {i.get("rule_id"): i for i in items if i.get("rule_id")}
    return [{**f, "fix_bn": (by_id.get(f["rule_id"]) or {}).get("bn") or f["bn"],
             "fix_en": (by_id.get(f["rule_id"]) or {}).get("en") or f["en"]} for f in flags]
