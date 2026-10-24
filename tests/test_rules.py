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
    ("bus_requisition", lambda e, c: set_field(e, "mobile_number", c, "0171234567"), "BR-9"),
    ("bus_requisition", lambda e, c: set_field(e, "required_bus_date", c, "next Sunday"), "BR-4"),
    ("bus_requisition", lambda e, c: set_field(e, "total_passengers", c, ""), "BR-7"),
    ("bus_requisition", lambda e, c: set_field(e, "required_time", c, "8 o'clock"), "BR-5"),
    ("transcript_letter", lambda e, c: set_field(e, "addressee", c, "The Principal, IIUC"), "TL-1"),
    ("transcript_letter", lambda e, c: set_field(e, "student_id", c, ""), "TL-5"),
    ("transcript_letter", lambda e, c: set_field(e, "addressee", c, "পরীক্ষা নিয়ন্ত্রক বরাবর"), None),
    ("leave_letter", lambda e, c: set_field(e, "addressee", c, "The Proctor, IIUC"), "LV-1"),
    ("leave_letter", lambda e, c: set_field(e, "leave_dates", c, ""), "LV-3"),
    ("duplicate_id_card", lambda e, c: set_field(e, "gd_number", c, ""), "ID-4"),
    ("duplicate_id_card", lambda e, c: set_field(e, "session", c, "2020"), "ID-3"),
]


@pytest.mark.parametrize("card_id,mutate,rule_id", MUTATIONS)
def test_each_mistake_raises_exactly_one_rule(card_id, mutate, rule_id):
    card = CARDS[card_id]
    flags, _ = audit(card, mutate(copy.deepcopy(clean_extraction(card)), card))
    assert [f["rule_id"] for f in flags] == ([rule_id] if rule_id else [])


@pytest.mark.parametrize("card_id", sorted(CARDS))
def test_demo_mistakes_button_plants_exactly_three_problems(card_id):
    """The UI's "Add 3 mistakes" button applies demo_mistakes; each must trip a different rule."""
    card = CARDS[card_id]
    e = copy.deepcopy(clean_extraction(card))
    demo = card["demo_mistakes"]
    for key, value in demo.get("set", {}).items():
        set_field(e, key, card, value)
    if demo.get("clear_signature"):
        label = next(s["label_en"] for s in card["signatures"] if s["key"] == demo["clear_signature"])
        next(b for b in e["signature_boxes"] if b["label"] == label)["has_ink"] = False
    if demo.get("photo_off"):
        e["photo_box"]["filled"] = False
    flags, _ = audit(card, e)
    assert len({f["rule_id"] for f in flags}) == 3


def test_photo_not_required_is_never_flagged():
    card = CARDS["bus_requisition"]
    e = clean_extraction(card)
    e["photo_box"] = {"present": False, "filled": False}
    assert audit(card, e)[0] == []


def test_missing_signature_box_is_a_flag_not_a_pass():
    card = CARDS["transcript_letter"]
    e = clean_extraction(card)
    e["signature_boxes"] = []
    flags, _ = audit(card, e)
    assert [(f["rule_id"], f["read"]) for f in flags] == [("TL-7", "box not found")]


@pytest.mark.parametrize("title,kind,expected", [
    ("APPLICATION FOR ACADEMIC TRANSCRIPT", "form", "transcript_application"),
    ("SAMPLE UNIVERSITY (IIUC-style sample form) APPLICATION FOR ACADEMIC TRANSCRIPT", "form", "transcript_application"),
    ("একাডেমিক ট্রান্সক্রিপ্টের জন্য আবেদন ফরম", "form", "transcript_application"),
    ("Bus Requisition", "form", "bus_requisition"),
    ("APPLICATION FOR DUPLICATE ID CARD", "form", "duplicate_id_card"),
    ("Application for transcript", "letter", "transcript_letter"),
    ("ছুটির জন্য আবেদন", "letter", "leave_letter"),
    ("Prayer for leave of absence", "letter", "leave_letter"),
])
def test_match_card(title, kind, expected):
    card, _ = match_card(title, CARDS, kind)
    assert card["id"] == expected


def test_unknown_form_is_refused():
    card, _ = match_card("Library Membership Form", CARDS, "form")
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


@pytest.mark.parametrize("written,ok", [
    ("২৬/১০/২০২৬", True), ("26.10.2026", True), ("26-10-2026", True), ("২৬-১০-২৬", False),
    ("5/11/26", False), ("31/02/2026", False),
])
def test_dates_accept_bangla_digits_and_common_separators(written, ok):
    card = CARDS["leave_letter"]
    flags, _ = audit(card, set_field(copy.deepcopy(clean_extraction(card)), "date", card, written))
    assert ("LV-2" in [f["rule_id"] for f in flags]) is not ok


def test_bangla_digit_student_id_is_read_as_digits():
    card = CARDS["transcript_letter"]
    flags, _ = audit(card, set_field(copy.deepcopy(clean_extraction(card)), "student_id", card, "C২৩১০৪৫"))
    assert flags == []
