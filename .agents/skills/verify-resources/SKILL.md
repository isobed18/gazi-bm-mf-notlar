---
name: verify-resources
description: Check resources that were placed automatically (status unverified) - open each file, confirm or fix course, kind, year, term, exam type and title, then mark it approved; move misclassified files with relocate and retire junk. Use after bulk intake (WhatsApp, drive dumps) and in weekly maintenance.
---

# Verify automatically placed resources

## For each assigned course
```
python -X utf8 tools/archive.py storage-pull --course <CODE>       # download the files you must look at
```
List the course's sidecars with `status: unverified` (`courses/<CODE>/**/*.meta.yaml`). For **each** file:
1. Open it: PDF first 1–2 pages (PyMuPDF text, or render page 1 to PNG and look at it), pptx slide titles, images directly.
2. Decide what it really is:
   - **Course** — header, title, content. Use `catalog/curriculum.yaml` (codes, names, aliases).
   - **Kind** — `exam` (questions, points, duration, "Vize/Final/Bütünleme"), `exam-solution` (answers/çözüm),
     `slides` (instructor slides), `lecture-notes` (instructor handouts, book chapters by the instructor),
     `student-notes` (handwritten or typed by a student), `summary` (cheat sheet/özet), `homework`, `lab`, `book`, `syllabus`.
   - **year / term / exam_type / week / title** — from the document (header "2023-2024 Güz Final" → year 2023, fall, final).
3. Apply:
   - correct as is → `archive.py meta-set <file> status=approved` (+ `title=… year=… term=… exam_type=… week=…` fixes)
   - wrong course or kind → `archive.py relocate <file> --course <CODE> --kind <kind> --status approved` (then meta-set fixes)
   - not course material / useless (curriculum, calendar, schedule, poster, unrelated document, duplicate scan of worse
     quality, personal content) → `archive.py meta-set <file> status=deprecated notes="<one-word reason>"`
   - cannot tell → `archive.py meta-set <file> status=needs-review notes="<short question>"` (the maintainer sees these)
Titles are short Turkish labels: "2023-2024 Güz Vize", "Hafta 5 – Bellek Yönetimi", "Ağaçlar el notu".

## Rules
- Be decisive; most files are right or obviously wrong. `needs-review` should stay rare.
- Never delete files; deprecate instead. Never edit sidecars by hand; only `meta-set` / `relocate`.
- Privacy: if a file shows personal data (chat screenshot, ID, phone numbers, grade lists with names) → `status=deprecated notes=private`.
- Finish with `archive.py validate` (0 errors). Report per course: approved / relocated / deprecated / needs-review.
