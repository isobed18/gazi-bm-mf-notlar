---
name: review-queue
description: Open review items for files that need a human decision, write clear proposals and questions for the maintainer, and apply the maintainer's decisions. Use whenever confidence is not high, a file belongs to no course, or a scan says review.
---

# Review queue (human supervision)

The maintainer is a human who reads `review/R-*/review.md`, writes a decision and a comment, and asks an agent
to apply it. Make their job fast: one clear proposal, specific questions.

## Open
```
python -X utf8 tools/archive.py review-open <inbox file> \
  --reason "<1-2 sentences: what it is and why you are not sure>" \
  [--course CODE --kind KIND | --general CATEGORY] [--title "..."] [--confidence low|medium] \
  [--question "Specific question?"]  (repeatable)
```
Good reason: "3 sayfalık sınav fotoğrafı, başlıkta sadece 'Final 2023' yazıyor; sorular graf algoritmaları → BM218 olabilir."
Bad reason: "not sure".
Always propose something (course+kind or general category) even with low confidence.
Group near-identical items: if 15 photos belong to the same exam, open **one** item for the first photo and mention
the others in the reason (keep the rest in the inbox until the decision is known).

### Maintainer focus
Only open a review item when a safety/privacy or real course-matching decision blocks a past exam question/solution,
course note, or official instructor slide. Prioritize PDF exams first, then course notes, then official slides. Never
open items for curriculum, course/exam schedules, homework calendars or one-off homework details, academic calendars,
general/university documents, internships, career material, or unrelated files; skip these without asking. Books are
secondary: if a book clearly matches a course, add it without opening an issue; do not include books in the official
Obsidian export.
When an elective's name is clear, keep the material with that course name and do not ask for a course number merely
because the catalog lacks one. Ask only about a real course/content ambiguity or a safety/privacy concern that blocks
placing a high-priority resource. For private chat archives, do not publish filenames, chat excerpts, or unresolved
personal material to GitHub; skip uncertain items locally and count them without describing them. Keep review questions
short.

## Decisions the maintainer can write (`decision:` line in review.md)
```
approve                         place exactly as proposed
place BM218 exam 2023 Vize      place into a course with a title
general career Staj rehberi     place under general/<category>/
reject                          delete (junk, private, duplicate)
quarantine                      keep aside as unsafe
```
plus a free-text `comment:`. If the comment contains extra instructions ("year is 2022", "merge with R-…"),
follow them: run `place` yourself with the corrected metadata instead of `review-apply`, then close the item by
moving it to `review/_closed/` with `status: closed (manual)`.

## Apply
```
python -X utf8 tools/archive.py review-list            # DECIDED items have a decision
python -X utf8 tools/archive.py review-apply R-YYYYMMDD-NNN
```
Then process the related files you kept in the inbox the same way. Learn from comments: if the maintainer
corrects a pattern ("WA images from group X are lab photos of BM222"), apply it to similar pending files and
mention it in your report.

## Publishing to GitHub (default way to reach the maintainer)
After a batch, publish only the remaining high-priority items as **one** issue:
```
python -X utf8 tools/archive.py review-publish --batch "<what this batch was>"
```
This uploads each file to Drive `gazi-bm-mf-notlar/_review/<id>/` (the maintainer opens it there) and creates an issue
labelled `review` with a table and per-item details. The maintainer answers in comments, one line per item:
```
R-20261109-165132-a118: place BM218 exam 2023 Vize -- yıl 2022 olabilir
R-…: approve
R-…: general university Sınav programı
R-…: reject
all: approve
```
Items in an issue are numbered (1, 2, 3 …). The maintainer usually answers in **plain Turkish**, e.g.
"1 ve 2 BM218'in 2023 güz vizesi. 3 çöp, sil. 4'ü staj klasörüne koy. Geri kalanlar öneri gibi olsun."
Short commands also work: `3: reject`, `1: place BM218 exam 2023 Vize`, `all: approve`.

Run at the start of every session (and whenever asked):
```
python -X utf8 tools/archive.py review-sync
```
- Short commands are applied directly; finished issues are closed.
- Plain-language comments are printed and saved to `local/review-inbox.json` together with the item list
  (number → id, file, proposal). **You interpret them**:
  1. For each item the comment clearly decides, run
     `python -X utf8 tools/archive.py review-decide <R-id> "<decision>" --comment "<what the maintainer said>"`
     where decision is `approve` | `place <CODE> <kind> [title words]` | `general <category> [title]` | `reject` | `quarantine`.
     Translate natural phrases: "sil / çöp / gerek yok" → reject; "öneri gibi / olduğu gibi / tamam" → approve;
     "staj klasörüne" → general internship; "X dersinin vizesi 2023" → place X exam 2023 Vize (+ set year/term/exam type
     afterwards with `meta-set` if the title is not enough).
  2. For anything ambiguous, do nothing for that item and ask a short question in your reply.
  3. Reply once with what you understood and did, then mark the comment handled:
     `python -X utf8 tools/archive.py review-ack <issue> <comment_id> --reply "Anladığım: 1,2 → BM218 vize 2023 güz (yerleştirildi); 3 → silindi; 5 için: hangi ders?"`
  The issue is closed automatically when no open items remain.
- Comments posted by agents carry a hidden marker and are ignored by `review-sync`.

Keep issues useful: be decisive elsewhere so that an issue contains only real questions (typically < 15 items per batch).
Never put names, phone numbers or chat quotes into reasons/questions — the issue is visible to collaborators.
