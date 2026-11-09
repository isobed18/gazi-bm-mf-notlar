---
name: contributor-submit
description: For a student's own AI agent - propose files (slides, past exams, notes) to this repository through a GitHub issue (files) or a pull request (notes/metadata only) that follows the repository rules. Use when a user says "add my files to the archive".
---

# Contributing (for the contributor's agent)

You act for a student who wants to share course material. Files are stored on the maintainers' Google Drive,
**not in git**, so contributors send files through a **GitHub issue**; the repository's maintainer agent places and
uploads them, and a human approves.

## 1. Prepare locally (recommended, so the issue is clean)
```
git clone <repo> && cd gazi-bm-mf-notlar && pip install -r tools/requirements.txt
python -X utf8 tools/archive.py intake <files...> --source upload:<github-username>
python -X utf8 tools/archive.py scan <each inbox file>
```
- Drop files whose scan verdict is `block`. Fix or drop `review` files that contain personal data (see `privacy-guard`).
- Decide course + kind + year/term/exam type for each file (`classify-and-place`), but **do not run `place`**
  (you have no Drive access; it would only create local sidecars).

## 2. Open the issue (template "Kaynak önerisi / Resource submission")
- Title: `[kaynak] BM218 2023 güz vize + final`.
- Attach files (GitHub accepts pdf/docx/pptx/zip/images up to its size limits) or give a share link
  (Drive/OneDrive/WeTransfer). Zip many files into one archive.
- In the body add a table, one row per file:
  `| dosya | ders | tür | yıl/dönem | sınav türü | not |`
  plus the source (own notes / instructor / exam photo) and tick both consent boxes.
- One course per issue when possible.

## 3. Pull requests
Open a PR only for text: fixing metadata (`*.meta.yaml` topics/titles), course catalog additions
(`catalog/curriculum.yaml`, e.g. a new elective), or documentation. Run `archive.py validate` before pushing.
Binary files in a PR are rejected by CI.

## Never submit
Copyrighted textbooks as full PDFs (link them instead), chats or chat screenshots, personal data, executables,
macro-enabled Office files, `.rar/.7z`.
