# FormBondhu evaluation

Every rule card, filled correctly and with its three demo mistakes, sent through the live `/api/check`.
Each image is tested twice: a crisp render, and a simulated phone photo (3.5° tilt, blur, shrunk, JPEG quality 55).
Expected problems come from applying the card's rules to a perfect read, so they are fixed in advance.

Run: 2026-10-24 12:49, engine: server default

## Summary

- Cases: 20 (20 completed, 0 errors)
- Exact result (right card and exactly the expected problems): 20/20
- Right rule card matched: 20/20
- Planted problems caught (recall): 30/30 = 100%
- Flags that were real problems (precision): 30/30 = 100%
- Time per check: median 23s, max 30s

## Every case

| Case | Exact | Flagged | Notes | Time |
|---|---|---|---|---|
| bus_requisition / clean / crisp | yes | none |  | 23s |
| bus_requisition / clean / phone | yes | none |  | 23s |
| bus_requisition / mistakes / crisp | yes | BR-4, BR-7, BR-9 |  | 28s |
| bus_requisition / mistakes / phone | yes | BR-4, BR-7, BR-9 |  | 30s |
| duplicate_id_card / clean / crisp | yes | none |  | 21s |
| duplicate_id_card / clean / phone | yes | none |  | 23s |
| duplicate_id_card / mistakes / crisp | yes | ID-3, ID-4, ID-5 |  | 27s |
| duplicate_id_card / mistakes / phone | yes | ID-3, ID-4, ID-5 |  | 26s |
| leave_letter / clean / crisp | yes | none |  | 22s |
| leave_letter / clean / phone | yes | none |  | 21s |
| leave_letter / mistakes / crisp | yes | LV-1, LV-2, LV-3 | draft ok, passed | 30s |
| leave_letter / mistakes / phone | yes | LV-1, LV-2, LV-3 | draft ok, passed | 28s |
| transcript_application / clean / crisp | yes | none |  | 18s |
| transcript_application / clean / phone | yes | none |  | 17s |
| transcript_application / mistakes / crisp | yes | TR-5, TR-6, TR-7 |  | 21s |
| transcript_application / mistakes / phone | yes | TR-5, TR-6, TR-7 |  | 23s |
| transcript_letter / clean / crisp | yes | none |  | 20s |
| transcript_letter / clean / phone | yes | none |  | 20s |
| transcript_letter / mistakes / crisp | yes | TL-1, TL-2, TL-5 | draft ok, passed | 25s |
| transcript_letter / mistakes / phone | yes | TL-1, TL-2, TL-5 | draft ok, passed | 29s |
