---
name: archive-intake
description: Bring any new files (upload, drive dump, folder, zip) into the archive safely - copy into inbox with hashes, detect duplicates, scan, then route each file to place / review / quarantine. Use for every new input.
---

# Archive intake

## 1. Intake (never skip)
```
python -X utf8 tools/archive.py intake <file-or-folder> [...] --source <type:ref> [--batch <name>]
```
- `--source` examples: `whatsapp:bm-2023-giris`, `drive:3-sinif-guz`, `upload:<github-user>`, `instructor`, `self`.
  Use a short slug, never a person's name or phone number.
- Output: `inbox/<batch>/files/` (copies) + `inbox/<batch>/intake.jsonl` (sha256, size, ext, duplicate_of).
- Duplicates (same sha256 already in the archive or inbox) are **not** copied. Do not process them again.
- Zip/rar inputs: extract into `local/tmp/<batch>/` first with Python's `zipfile` (never run anything),
  then intake the extracted folder. `.rar/.7z` are blocked types: open a review item asking the maintainer.

## 2. Make a work list before opening files
Build a list from `intake.jsonl`: name, ext, size. Sort documents (pdf, docx, pptx, xlsx, doc, ppt)
first, then code, then images. **Do not open every file.** For big batches follow `whatsapp-triage`.

## 3. For each file, in order
1. `archive.py scan <file>` → verdict `ok | review | block`.
   - `block` → it will be quarantined by `place`; just record it in your report.
   - `review` → `review-open` (load `review-queue`), include the scan reasons.
2. Identify course + kind (load `classify-and-place`). Open the file only as much as needed:
   first page of a pdf, slide titles of a pptx, a downscaled look at an image.
3. Confident → `place`. Not confident, or no course → `review-open`.
4. Irrelevant (memes, selfies, ads, chat screenshots, unrelated documents) → leave it in the inbox and
   list it as `skipped` in your report. Do not create review items for obvious junk. The batch folder is
   deleted by the maintainer after the batch report is accepted.

## 4. Finish
```
python -X utf8 tools/archive.py validate
python -X utf8 tools/archive.py index
python -X utf8 tools/archive.py review-list
```
Write a batch report to `local/reports/<batch>.md`:
| file | action (placed / review R-… / skipped / quarantined / duplicate) | course | kind | why |
Report counts at the top. Do not paste file contents or chat text into the report.
