---
name: whatsapp-triage
description: Process an exported WhatsApp chat (folder/zip with _chat.txt and media) completely and in batches - look at EVERY photo / document, keep course material, place it with status unverified, never copy chat text or personal media into the archive. Use for any WhatsApp/Telegram group export. Text messages are handled by chat-exam-intel.
---

# WhatsApp export: media and documents

Group exports are mostly irrelevant (memes, people, screenshots, event posters), but **every file must be looked at**.
Search and ranking help you *order* the work; they never decide what you skip without looking.
Load `privacy-guard` and `classify-and-place` together with this skill.

## Step 0 — set up
- Export slug for `--source`, e.g. `whatsapp:gazi-bm-2021` (never people's names).
- Progress file (create it first, update after **every** batch): `local/progress/<slug>-<media|docs>.md`
  with a table `| batch | files (first..last) | looked at | kept | placed | issues | skipped |`.
  The final report must show that the batches cover all files of the export.

## Step 1 — index (context for every attachment)
```
python -X utf8 tools/archive.py whatsapp-index "<export folder or zip>" --out local/triage/<slug>.csv
```
Each row: score, date, sender pseudonym (P001…), file, ext, detected courses, keywords, masked context of the
surrounding messages. Use it as **context** (which message came with a file, which date). Process files in
chronological order (or score order), but process **all** of them.

## Step 2 — look at every file, in batches
- **Documents** (pdf, docx, pptx, xlsx, doc, ppt, zip): batches of ~10. Open each one: first 2–3 pages / slide titles,
  enough to know course, kind and year. Zips: extract with Python `zipfile` into `local/tmp/<slug>/`, then treat the
  contents as documents.
- **Photos**: batches of ~20. Look at every photo (a downscaled view is enough). Keep photos of exam papers, written
  exam questions, boards/slides with lecture content, handwritten notes, and anonymous course-wide letter-grade
  distributions. For a distribution, include the stated period; if none is stated, use the course heading
  `Geçmiş Harf Notu Dağılımları`. Never keep a list/table with identifiable students or individual grades. Several photos of the same
  exam sent together (same sender, minutes apart) belong to one resource: combine into one PDF in page order
  (Pillow `save_all=True`) or place them with the same title and sequence numbers.
- Skip without placing: people, selfies, events, memes, chat screenshots, ads, posters, receipts, schedules, one-off
  homework details, unrelated documents, and documents with private data. Never include names, IDs, contact details,
  or individual grades. Skipping is recorded in the progress table as a count — no descriptions of private content.

## Step 3 — place (decisively)
```
python -X utf8 tools/archive.py intake <kept files> --source whatsapp:<slug> --batch wa-<slug>-<n>
python -X utf8 tools/archive.py place <inbox file> --course <CODE> --kind <kind> [--year --term --exam-type --title] --status unverified
```
- The message date + text gives year/term/exam type (a message on 12.04.2024 "vize soruları" → `--year 2023 --term spring --exam-type midterm`).
  Academic year: Sep–Jan = fall of that year; Feb–Aug = spring of the previous year's start (Apr 2024 → 2023 spring).
- Exam papers vs. homework vs. slides: decide from the content (question numbering/points/"süre" → exam; "teslim tarihi" → homework).
- Be decisive: if the evidence is reasonable, place it. Only genuinely ambiguous items → `review-open`.
- Material that belongs to **no course** (schedules, general documents, internship/career material, unrelated books)
  → skip without opening a review item. Course-matched books may be archived without asking, but are omitted from the
  official Obsidian vault.

## Step 4 — finish
```
python -X utf8 tools/archive.py validate
python -X utf8 tools/archive.py index
python -X utf8 tools/archive.py review-publish --batch "<slug> <media|docs>"     # one GitHub issue with all open items
```
Report: coverage table (all batches), counts (looked at / placed / issues / skipped / duplicates), the issue link.
Never commit; the maintainer reviews `git status` and commits.

## Hard rules
- **Never** place `_chat.txt`, chat excerpts, contact cards (`.vcf`), profile photos, voice notes.
- **Never** place photos of people or personal screenshots.
- The owner's own chat ("You"): documents that are clearly course material may be placed; every photo goes to review or is skipped.
- For a private group archive, never publish unresolved filenames or details to GitHub; skip ambiguous items locally.
