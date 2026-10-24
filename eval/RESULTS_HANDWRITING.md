# FormBondhu evaluation: handwriting

Application letters converted to handwriting: English with an online text-to-handwriting tool
(codeshack.io, three handwriting styles from neat to cursive), Bangla in the Galada handwriting-style font,
all on lined paper. Expected problems are written in `eval/handwriting/expected.json` before the run.

Run: 2026-10-24 13:20, engine: server default

## Summary

- Cases: 10 (10 completed, 0 errors)
- Exact result (right card and exactly the expected problems): 10/10
- Right rule card matched: 10/10
- Planted problems caught (recall): 18/18 = 100%
- Flags that were real problems (precision): 18/18 = 100%
- Time per check: median 25s, max 31s

## Every case

| Case | Exact | Flagged | Notes | Time |
|---|---|---|---|---|
| transcript_letter / mistakes / shadows_into_light | yes | TL-1, TL-2, TL-5, TL-7 | draft ok, passed | 27s |
| transcript_letter / mistakes / indie_flower | yes | TL-1, TL-2, TL-5, TL-7 | draft ok, passed | 27s |
| transcript_letter / mistakes / homemade_apple | yes | TL-1, TL-2, TL-5, TL-7 | draft ok, passed | 27s |
| transcript_letter / clean / shadows_into_light | yes | none |  | 17s |
| transcript_letter / clean / indie_flower | yes | none |  | 17s |
| transcript_letter / clean / homemade_apple | yes | none |  | 17s |
| leave_letter / mistakes / galada_wavyline | yes | LV-1, LV-2, LV-3 | draft ok, passed | 26s |
| leave_letter / mistakes / galada_cursivename | yes | LV-1, LV-2, LV-3 | draft ok, passed | 31s |
| leave_letter / clean / galada_wavyline | yes | none |  | 18s |
| leave_letter / clean / galada_cursivename | yes | none |  | 24s |
