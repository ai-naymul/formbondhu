"""Code-side guards inside the harness that do not need a model."""
from app.harness import LETTER_SLOTS, READ_PROMPT, ground_draft


def test_draft_keeps_the_real_id_and_removes_invented_ones():
    letter, replaced = ground_draft("Name: Rafiya\nID: C231045\nRef: C999999", "C231045")
    assert "C231045" in letter and "C999999" not in letter and replaced == ["C999999"]


def test_draft_with_missing_id_cannot_smuggle_one_in():
    letter, replaced = ground_draft("ID: C123456", "")
    assert "C123456" not in letter and replaced == ["C123456"]


def test_read_prompt_lists_every_letter_slot():
    assert all(slot in READ_PROMPT for slot in LETTER_SLOTS)
