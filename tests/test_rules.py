"""Mutation tests for the deterministic audit: one planted mistake must raise exactly one rule."""
import copy

import pytest

from app.rules import apply_verification, audit, load_cards, map_fields, match_card, merge_explanations

CARDS = load_cards()


def clean_extraction(card):
    """What a perfect read of a correctly filled sample form looks like."""
    return {
        "form_title": card["title_en"].upper(),
        "fields": [{"label_en": f["label_en"], "label_bn": f["label_bn"], "value": f["sample"], "is_empty": False}
                   for f in card["fields"]],
        "signature_boxes": [{"label": s["label_en"], "has_ink": True} for s in card["signatures"]],
        "photo_box": {"present": card["photo_required"], "filled": card["photo_required"]},
    }


def set_field(extraction, key, card, value):
    label = next(f["label_en"] for f in card["fields"] if f["key"] == key)
    for f in extraction["fields"]:
        if f["label_en"] == label:
            f["value"], f["is_empty"] = value, value == ""
    return extraction


@pytest.mark.parametrize("card_id", sorted(CARDS))
def test_clean_form_has_no_flags(card_id):
    card = CARDS[card_id]
    flags, passed = audit(card, clean_extraction(card))
    assert flags == []
    assert len(passed) == len(card["rules"])


MUTATIONS = [
    ("transcript_application", lambda e, c: set_field(e, "date", c, "12/3/26"), "TR-5"),
    ("transcript_application", lambda e, c: set_field(e, "student_id", c, "231045"), "TR-2"),
    ("transcript_application", lambda e, c: set_field(e, "student_name", c, ""), "TR-1"),
    ("transcript_application", lambda e, c: e["signature_boxes"][0].update(has_ink=False) or e, "TR-6"),
    ("transcript_application", lambda e, c: e["photo_box"].update(filled=False) or e, "TR-7"),
    ("transcript_application", lambda e, c: set_field(e, "date", c, "31/02/2026"), "TR-5"),
    ("makeup_exam_application", lambda e, c: set_field(e, "course_code", c, "data structures"), "MU-3"),
    ("makeup_exam_application", lambda e, c: e["signature_boxes"][1].update(has_ink=False) or e, "MU-8"),
    ("makeup_exam_application", lambda e, c: set_field(e, "missed_exam_date", c, "15-10-2026"), "MU-4"),
    ("duplicate_id_card", lambda e, c: set_field(e, "gd_number", c, ""), "ID-4"),
    ("duplicate_id_card", lambda e, c: set_field(e, "session", c, "2020"), "ID-3"),
]


@pytest.mark.parametrize("card_id,mutate,rule_id", MUTATIONS)
def test_each_mistake_raises_exactly_one_rule(card_id, mutate, rule_id):
    card = CARDS[card_id]
    flags, _ = audit(card, mutate(copy.deepcopy(clean_extraction(card)), card))
    assert [f["rule_id"] for f in flags] == [rule_id]


def test_photo_not_required_is_never_flagged():
    card = CARDS["makeup_exam_application"]
    e = clean_extraction(card)
    e["photo_box"] = {"present": False, "filled": False}
    assert audit(card, e)[0] == []


def test_missing_signature_box_is_a_flag_not_a_pass():
    card = CARDS["makeup_exam_application"]
    e = clean_extraction(card)
    e["signature_boxes"] = [e["signature_boxes"][0]]
    flags, _ = audit(card, e)
    assert [(f["rule_id"], f["read"]) for f in flags] == [("MU-8", "box not found")]


@pytest.mark.parametrize("title,expected", [
    ("APPLICATION FOR ACADEMIC TRANSCRIPT", "transcript_application"),
    ("SAMPLE UNIVERSITY (IIUC-style sample form) APPLICATION FOR ACADEMIC TRANSCRIPT", "transcript_application"),
    ("একাডেমিক ট্রান্সক্রিপ্টের জন্য আবেদন ফরম", "transcript_application"),
    ("Application for Make-up Examination", "makeup_exam_application"),
    ("APPLICATION FOR DUPLICATE ID CARD", "duplicate_id_card"),
])
def test_match_card(title, expected):
    card, _ = match_card(title, CARDS)
    assert card["id"] == expected


def test_unknown_form_is_refused():
    card, _ = match_card("Library Membership Form", CARDS)
    assert card is None


def test_field_mapping_tolerates_label_variants():
    card = CARDS["transcript_application"]
    got = [{"label_en": "Date", "label_bn": "", "value": "24/10/2026", "is_empty": False},
           {"label_en": "", "label_bn": "আইডি নং", "value": "C231045", "is_empty": False}]
    mapped = map_fields(card, got)
    assert mapped["date"] == "24/10/2026" and mapped["student_id"] == "C231045" and mapped["student_name"] is None


def test_unconfirmed_flags_go_to_manual_check():
    flags = [{"rule_id": "TR-5"}, {"rule_id": "TR-6"}, {"rule_id": "TR-7"}]
    checks = [{"rule_id": "TR-5", "confirmed": True, "seen": "12/3/26"},
              {"rule_id": "TR-6", "confirmed": False, "seen": "a signature is present"}]
    confirmed, manual = apply_verification(flags, checks)
    assert [f["rule_id"] for f in confirmed] == ["TR-5"]
    assert [f["rule_id"] for f in manual] == ["TR-6", "TR-7"]


def test_explanations_cannot_invent_problems():
    flags = [{"rule_id": "TR-5", "bn": "card text", "en": "card en"}]
    items = [{"rule_id": "TR-5", "bn": "model fix", "en": "model fix en"},
             {"rule_id": "TR-99", "bn": "invented", "en": "invented"}]
    merged = merge_explanations(flags, items)
    assert [m["rule_id"] for m in merged] == ["TR-5"] and merged[0]["fix_bn"] == "model fix"
    assert merge_explanations(flags, [])[0]["fix_bn"] == "card text"
