# Handwritten test sheets

Write these by hand on paper. Each letter has its expected result decided in advance, so you can tell whether the app got it right. All names and IDs are made up.

**How to photograph:**
- Use dark blue or black pen on white paper, and write a little larger than usual.
- Shoot straight from above, in daylight or bright room light, with no shadow from your phone.
- Get the whole page in frame. In the app, use the **ফর্মের ছবি দিন / Photo of a form** tab.

## Letter 1: transcript letter, English, 3 planted mistakes

```
5/11/26

To
The Principal
IIUC

Subject: Application for academic transcript

Sir,
I am a student of the Department of EEE, 8th semester. I need my
academic transcript for a higher study application. I will attach
the fee payment slip. I therefore pray that you would kindly issue it.

Yours obediently,
(sign here with your pen)
Name: Rafiya Akter
Department: EEE, Semester: 8th
```

**Expected:**
- Red stamp, with **TL-1** (addressed to the Principal, not the Controller of Examinations), **TL-2** (date `5/11/26`) and **TL-5** (no student ID line).
- A corrected letter addressed to the Controller of Examinations, with `[your student ID]` as a placeholder.

## Letter 2: leave letter, Bangla, 3 planted mistakes

```
তারিখ: ২৬-১০-২৬

বরাবর
প্রক্টর
আন্তর্জাতিক ইসলামী বিশ্ববিদ্যালয় চট্টগ্রাম

বিষয়: ছুটির জন্য আবেদন

জনাব,
বিনীত নিবেদন এই যে, আমি সিএসই বিভাগের ৫ম সেমিস্টারের একজন ছাত্র।
আমার বোনের বিয়ের কারণে আমি ক্লাসে উপস্থিত থাকতে পারব না।
অতএব, আমাকে ছুটি মঞ্জুর করার জন্য বিনীত অনুরোধ করছি।

বিনীত নিবেদক
(এখানে স্বাক্ষর করুন)
নাম: তানভীর হাসান
আইডি: C221187
বিভাগ: সিএসই, সেমিস্টার: ৫ম
```

**Expected:**
- Red stamp, with **LV-1** (addressed to the Proctor, not the Chairman or a course teacher), **LV-2** (two-digit year `২৬-১০-২৬`) and **LV-3** (doesn't say which days).
- A corrected letter **in Bangla**, with a placeholder for the leave dates.

## Letter 3: the same transcript letter, correct

Same as Letter 1, with three changes:
- Date `05/11/2026`.
- Addressed to `The Controller of Examinations, IIUC`.
- Add a line `ID: C231045`.

Sign it.

**Expected:** green stamp **জমা দেওয়ার জন্য প্রস্তুত**.

## If something comes out wrong

Open the **raw output** of step 1 (ফর্ম পড়া). It shows exactly what Gemma read from your handwriting.
- If a value was misread, the handwriting or photo is the problem: retake it flatter and brighter.
- If Gemma read it correctly but the verdict is wrong, it's a rule bug. Tell Claude the step and the raw output.
