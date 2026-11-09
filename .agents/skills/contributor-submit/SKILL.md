---
name: contributor-submit
description: For a student's own AI agent - send course files (past exams, solutions, notes, slides) to this archive through the "Gazi BM Kaynak Gönder" Google Form, one form submission per course + kind. Use when a user says "add my files to the archive" / "bu dosyaları arşive gönder".
---

# Contributing (for the contributor's agent)

Files are stored on the maintainers' Google Drive, not in git. The channel is the **Google Form "Gazi BM Kaynak Gönder"**
(https://docs.google.com/forms/d/e/1FAIpQLSccuOWOSr4S9dCxMROm2lOoa0IgOjIznh9X3YZ1ieTljdW9Ng/viewform). Every submission = **one course + one kind**; that is what lets the maintainers' agent place files
without guessing. You do not need git or a GitHub account.

## 1. Sort the files (locally, read every file)
- Open/read each file and decide: **course** (pick the exact entry from the form's "Ders" list, e.g.
  `BM218 - Algoritma Tasarımı ve Analizi`; course list: `catalog/curriculum.yaml`), **kind** (one of the form's "Tür"
  options), **year/term + exam type** (e.g. `2023-2024 Güz vize`; `bilinmiyor` if unknown).
- Group files by (course, kind). Each group becomes one submission (max 10 files, 100 MB each; split bigger groups).
- Drop files that must not be shared: chats or chat screenshots, phone numbers, ID cards, personal photos, grade lists /
  transcripts, executables, macro Office files (`.docm`, `.xlsm`), full copyrighted textbooks (give a link in "Not").
  Names written on exam papers or homework are fine. Unpack `.zip/.rar/.7z` first (the form does not accept archives).
- Give files readable names if possible: `BM218_2023-guz_vize.pdf`, `BM218_2023-guz_vize_cozum.pdf`.

## 2. Show the plan to the user
A table, one row per submission: `| # | Ders | Tür | Yıl/dönem | dosyalar |`. Ask the user to confirm.

## 3. Submit
- If you can control a browser (e.g. Claude in Chrome): open the form, fill one submission per row (upload the files,
  pick Ders and Tür, type Yıl/dönem, Not, tick "Onaylıyorum"), submit, then "Başka bir yanıt gönder" for the next row.
  The user must be signed in to Google; never type passwords yourself.
- Otherwise give the user the table plus the exact answers per submission so they can fill it in quickly.

## Notes
- Google records which account uploaded each file; only the maintainers see it, it is never published.
- After submitting nothing can be edited or deleted by the submitter; mistakes are fixed by the maintainers.
- Text-only changes (metadata fixes, a new elective in `catalog/curriculum.yaml`, docs) may be sent as a pull request;
  binaries in a PR are rejected by CI.
