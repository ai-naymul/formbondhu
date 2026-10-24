# Manual test guide (about 12 minutes)

Start the app:

```bash
cd ~/Workspace/formbondhu && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 on the laptop. To use your phone on the same Wi-Fi, open `http://<laptop-ip>:8000`; `ipconfig getifaddr en0` prints the laptop's IP.

| # | Do this | You should see |
|---|---|---|
| 1 | Load the page, then open **Gemma কীভাবে যাচাই করে** | The six steps of the harness. The engine chips show **Google AI Studio** selected and **Local Ollama** greyed out, with install steps. |
| 2 | Form maker → **একাডেমিক ট্রান্সক্রিপ্ট ফরম** → Check without changing anything | Green stamp **জমা দেওয়ার জন্য প্রস্তুত**. All 7 rules pass. |
| 3 | Same form → **৩টি ভুল বসান** (Add 3 mistakes) → Check | Red stamp. Exactly TR-5 (date), TR-6 (signature), TR-7 (photo). |
| 4 | Sign the pad, tick **Photo attached**, type `24/10/2026` in the date → Check | Green again. This is the "a judge can change it" proof. |
| 5 | **ট্রান্সক্রিপ্টের জন্য দরখাস্ত** (letter) → Add 3 mistakes → Check | TL-1 (wrong office: Principal), TL-2 (date), TL-5 (missing ID). Step 6 runs and a **corrected letter** appears, addressed to the Controller of Examinations, with `[your student ID]` as a placeholder rather than a made-up ID. |
| 6 | **ছুটির জন্য দরখাস্ত** → Add 3 mistakes → Check | LV-1 (Proctor instead of Chairman), LV-2 (date), LV-3 (no leave dates), plus a corrected letter. |
| 7 | **বাস রিকুইজিশন ফরম** → Add 3 mistakes → Check | BR-4 (bus date "next Sunday"), BR-7 (no passengers), BR-9 (10-digit mobile number). |
| 8 | Photo tab → photograph a **handwritten application letter** on paper: "To, The Principal…", Subject "Application for transcript", no ID, date like 5/11/26 | It reads it as a letter, flags the wrong office, the missing ID and the date, and drafts a corrected letter. Clear, flat light gives the best results. |
| 9 | Photo tab → photograph anything that isn't one of the 5 documents | Grey stamp **অচেনা ফর্ম**, plus the list of documents it knows. No guessing. |
| 10 | On any step, open **raw output** | The real JSON from Gemma 4. On the draft step, `grounding_check: passed`. |
| 11 | Optional, local Gemma: install Ollama, run `ollama pull gemma4:e2b`, reload the page | A **Local Ollama: gemma4:e2b** chip appears. Choose it and run test 3; the steps say "on local Ollama". Expect it to be slower on an 8 GB M1. |

Tell Claude anything that looks wrong, along with the step number.
