# FormBondhu evaluation: handwriting

Application letters converted to handwriting: English with an online text-to-handwriting tool
(codeshack.io, three handwriting styles from neat to cursive), Bangla in the Galada handwriting-style font,
all on lined paper. Expected problems are written in `eval/handwriting/expected.json` before the run.

Run: 2026-10-24 13:07, engine: server default

## Summary

- Cases: 8 (8 completed, 0 errors)
- Exact result (right card and exactly the expected problems): 8/8
- Right rule card matched: 8/8
- Planted problems caught (recall): 15/15 = 100%
- Flags that were real problems (precision): 15/15 = 100%
- Time per check: median 27s, max 32s

## Every case

| Case | Exact | Flagged | Notes | Time |
|---|---|---|---|---|
| transcript_letter / mistakes / shadows_into_light | yes | TL-1, TL-2, TL-5, TL-7 | draft ok, passed | 27s |
| transcript_letter / mistakes / indie_flower | yes | TL-1, TL-2, TL-5, TL-7 | draft ok, passed | 28s |
| transcript_letter / mistakes / homemade_apple | yes | TL-1, TL-2, TL-5, TL-7 | draft ok, passed | 27s |
| transcript_letter / clean / shadows_into_light | yes | none |  | 17s |
| transcript_letter / clean / indie_flower | yes | none |  | 27s |
| transcript_letter / clean / homemade_apple | yes | none |  | 17s |
| leave_letter / mistakes / galada | yes | LV-1, LV-2, LV-3 | draft ok, passed | 32s |
| leave_letter / clean / galada | yes | none |  | 23s |
