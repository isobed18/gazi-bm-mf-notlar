---
name: classify-and-place
description: Decide course, kind and metadata (year, term, exam type, week, topics) for a single file and place it with archive.py, or send it to review when uncertain. Use whenever a file must be filed into courses/ or general/.
---

# Classify and place one file

## Evidence, strongest first
1. Course code in the file name or the document header (`BM218`, `CENG205`, `MATH101` …).
2. Course name or alias from `catalog/curriculum.yaml` (`aliases` are lower-case, Turkish characters folded:
   `isletim sistemleri` → BM309).
3. The message that came with the file (WhatsApp caption, PR description).
4. Content: slide titles, exam header ("2023-2024 Bahar Yarıyılı … Vize Sınavı"), instructor name, typical topics.
Old curriculum codes are aliases too (e.g. `FIZ101` → `FIZ103`, `BM486` → `BM466`, `BM394` → `CENG394`).
If a course is missing from the catalog, **do not invent a code**: open a review item asking to add it.

## Kind (see `catalog/taxonomy.yaml`)
- Questions of a past exam → `exam`; its answer key → `exam-solution` (`--related <exam path>`).
- Instructor slides → `slides`; instructor handouts / course PDFs → `lecture-notes`.
- Anything written by a student (handwritten scans, typed notes, summaries of a lecture) → `student-notes`
  (+ `--handwritten` for scans). Cheat-sheets/study guides → `summary`.
- Assignment text → `homework`; a solved assignment → `homework-solution`.
- Syllabus/grading → `syllabus`; exam topics/dates announced by the instructor → `announcement` (as a .md or .txt).
- Photos of exam papers → `exam` (several photos of one exam: combine into one PDF if you can do it safely with
  Pillow: `Image.save(..., save_all=True)`; otherwise place each photo with the same title and `--week`-less metadata).

## Metadata
- `--year` = academic year start (2023-2024 → 2023), `--term fall|spring|summer`.
- `--exam-type midterm|final|makeup|quiz|resit|sample`.
- `--week N` for weekly slides/notes when the week is known.
- `--title`: short, human, Turkish OK ("Vize A grubu", "Hafta 5 - Bellek Yönetimi").
- `--topics "Dinamik Programlama, Greedy"` when obvious from the content (helps exam matching).
- `--lang tr|en|mixed`.
Leave anything you do not know empty. Never guess a year from the file's modification date alone.

## Confidence policy
| Situation | Action |
|---|---|
| course AND kind certain, scan ok, not duplicate | `place --confidence high` |
| course certain, kind unclear (or vice versa) | `review-open` with your best proposal |
| course uncertain | `review-open` |
| belongs to no course (career, general book, university form…) | `review-open --general <category>` proposal |
| obviously irrelevant or private | skip (do not place, do not review) |

## Commands
```
python -X utf8 tools/archive.py place <file> --course BM218 --kind exam --year 2023 --term fall --exam-type midterm --title "Vize"
python -X utf8 tools/archive.py place <file> --course CENG205 --kind student-notes --handwritten --title "Ağaçlar el notu"
python -X utf8 tools/archive.py review-open <file> --reason "course unclear: only 'final' on page" --course BM218 --kind exam --question "Is this BM218 or CENG205?"
```
`place` moves the file, normalizes the name, writes the sidecar and refuses duplicates and unsafe files.
