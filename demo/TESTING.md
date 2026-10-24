# Manual test guide (about 10 minutes)

Start the app:

```bash
cd ~/Workspace/formbondhu && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 on the laptop. To use your phone on the same Wi-Fi, open `http://<laptop-ip>:8000`; `ipconfig getifaddr en0` prints the laptop's IP.

| # | Do this | You should see |
|---|---|---|
| 1 | Load the page | The engine bar shows **Google AI Studio: gemma-4-31b-it**. Under it, Local Ollama is greyed out with install steps. |
| 2 | Form maker tab → press **Check this form** without changing anything | Green stamp **জমা দেওয়ার জন্য প্রস্তুত**. Steps 1–3 ✓, steps 4–5 "দরকার হয়নি". All 7 rules pass. |
| 3 | Press **৩টি ভুল বসান** (Add 3 mistakes) → Check | Red stamp **ফেরত আসবে**. Exactly TR-5 (date), TR-6 (signature), TR-7 (photo), each with a Bangla fix, an English fix and "Gemma যা দেখেছে". |
| 4 | Sign the pad with the mouse or a finger, tick **Photo attached**, type `24/10/2026` in the date → Check | Green again. This is the "a judge can change it" proof. |
| 5 | Pick **মেকআপ পরীক্ষা** → Add 3 mistakes → Check | MU-3 (course code), MU-6 (date), MU-8 (course teacher's signature). |
| 6 | Photo tab → upload `samples/transcript_3_mistakes.png` | TR-5, TR-6, TR-7. |
| 7 | Photo tab → photograph a hand-drawn form with your phone. Write the title "Application for Academic Transcript", the fields, a date like 12/3/26, and leave the signature empty. | It matches the transcript card and flags what's wrong. Clear, flat light gives the best results. |
| 8 | Photo tab → photograph anything that isn't one of the 3 forms | Grey stamp **অচেনা ফর্ম**, plus the list of forms it knows. No guessing. |
| 9 | On any step, open **raw output** | The real JSON from Gemma 4, or from the code step. |
| 10 | Optional, local Gemma: install Ollama, run `ollama pull gemma4:e2b`, reload the page | The engine bar lists **Local Ollama: gemma4:e2b**. Choose it and run test 3; the steps show "on local Ollama". Expect it to be slower on an 8 GB M1. |

Tell Claude anything that looks wrong, along with the step number.
