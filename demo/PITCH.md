# Two-minute pitch

**Hook (0:00–0:15)**
"At IIUC a missing signature doesn't cost you five minutes. It costs you another 90-minute bus ride to Kumira and another queue. FormBondhu checks your form before you leave home."

**Problem (0:15–0:35)**
"Rafiya is a first-year EEE student. She needs her transcript. She copies a senior's photo of the form, writes the date as 12/3/26, forgets the photo, and gets handed the form back at the third office. The problem statement for this event says it directly: simple paperwork means visiting three offices."

**Live demo (0:35–1:30)**
1. Open the Form maker and press **Add 3 mistakes**, then **Check this form**. Talk the judges through the steps panel as it fills in:
   - "Gemma 4 reads the form."
   - "Code matches it to the transcript rule card and checks every rule."
   - "Gemma looks again to confirm each problem, and writes the fix in Bangla."
2. The red stamp lands. Read one fix aloud.
3. Hand the laptop or phone to a judge: "Sign it, fix the date." Re-run, and the stamp turns green. That's proof nothing is cached.
4. Open one "raw output" panel: "This is the model's actual JSON."

**Why open AI matters (1:30–1:50)**
"It runs only on open-weights Gemma 4: hosted through Google AI Studio for this demo, or fully on your own machine through Ollama, chosen right here in the engine bar. Gemma sees, code decides: every problem maps to a human-written rule, and the model can't invent a fee or an office."

**What's next (1:50–2:00)**
"Offices publish their own rule cards as one JSON file each, and the same harness can check notices and routines next."

## The three hardest questions

**"Are these real IIUC rules?"**
No, and the app says so on screen. They're sample rule cards built for the demo. The point is the harness: an office can drop in its real rules as a JSON file without touching code.

**"How do you know it isn't hardcoded?"**
Change anything in the Form maker, or photograph any paper form, and the result changes. The raw model output is shown for every step. Unknown forms are refused instead of guessed. And 34 tests show that each planted mistake triggers exactly one rule.

**"What if Gemma misreads the form?"**
A second Gemma pass must confirm each problem by looking at the image again. Anything it can't confirm moves to "check these yourself" instead of being stated as fact. Because code makes the decisions, every flag points to a specific rule id.
