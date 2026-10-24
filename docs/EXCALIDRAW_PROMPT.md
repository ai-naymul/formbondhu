Draw a clean, high-level system architecture diagram for "FormBondhu", in Excalidraw's hand-drawn style, flowing left to right. Use rounded rectangles for components, labelled arrows for data flow, and group related boxes inside large dashed zones with a title at the top of each zone.

Colour code (show it in a small legend in the bottom-right corner):
- Blue boxes = Gemma 4 AI steps (open-weights model)
- Green boxes = deterministic code (no AI)
- Grey boxes = clients, infrastructure and data
- Dashed arrow = optional path

ZONE 1, far left, titled "Students":
- Grey box "Student on phone (web browser)"
- Grey box "Student on Telegram"

ZONE 2, titled "Interfaces":
- Grey box "Web app: Bangla/English UI, Form maker (canvas), live step trace (SSE)"
- Grey box "Telegram bot: polling or webhook"
Arrows: "Student on phone" → "Web app" labelled "photo of form or letter". "Student on Telegram" → "Telegram bot" labelled "photo".

ZONE 3, the largest zone in the middle, titled "Vercel Fluid compute: FastAPI (Python 3.12)":
- At the top of the zone, a grey box "API: POST /api/check (Server-Sent Events) · GET /api/engines · GET /api/health".
- Below it, a horizontal pipeline titled "6-step harness" with six numbered boxes connected left to right:
  1. Blue "1 Read: Gemma 4 vision → strict JSON (Pydantic)"
  2. Green "2 Match: pick rule card (form or letter); unknown → refuse"
  3. Green "3 Rules: rule engine (required, pattern, date, contains_any, signature, photo)"
  After box 3 the pipeline splits into three PARALLEL branches, stacked vertically and drawn side by side, with a small note "run in parallel":
  4. Blue "4 Re-check: second vision pass confirms each problem"
  5. Blue "5 Fix: Bangla + English fixes from rule text only"
  6. Blue "6 Draft: corrected letter + code ID check"
  The three branches merge into one grey box "Result: verdict stamp, fixes, corrected letter, documents, office route".
- Below the pipeline, a grey cylinder (database shape) "Rule cards (5 JSON files)". Arrows from the cylinder go up to box 2 "Match" and box 3 "Rules", labelled "facts only from here".
Arrows: "Web app" → "API" labelled "multipart image"; "Telegram bot" → "API" labelled "image". "API" → box 1 "Read". "Result" → back to "Web app" with an arrow labelled "live stream, one event per step".

ZONE 4, far right, titled "Gemma 4 engines (open weights only)":
- Blue box "Gemma 4 31B IT via Google AI Studio API (JSON mode, retry + backoff)"
- Blue box "Gemma 4 e2b / e4b via Ollama on your own laptop" (draw this one with a dashed border to show it is optional/local)
Arrows: from boxes 1, 4, 5 and 6 to "Gemma 4 31B IT" labelled "model calls". A dashed arrow from the harness to the Ollama box labelled "optional local mode".

ZONE 5, along the bottom, titled "Quality":
- Green box "67 pytest tests (mutation tests, mocked engines)"
- Green box "Evaluation: 40/40 cases exact, 0 false alarms (incl. live site)"

At the very top, a title "FormBondhu: Gemma sees, code decides" and, underneath in smaller text, "Photo of a campus form or application letter → what will get it returned → fix in Bangla".

Keep the layout uncluttered: large spacing between zones, short labels, and arrows that do not cross. Number the main flow arrows 1 to 5 so the request path reads clearly from left to right.
