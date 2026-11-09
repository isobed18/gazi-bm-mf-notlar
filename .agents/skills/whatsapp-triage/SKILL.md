---
name: whatsapp-triage
description: Process an exported WhatsApp chat (zip or folder with _chat.txt and media) step by step - rank attachments by relevance without reading everything, extract only course material, and never copy chat text or personal media into the archive. Use for any WhatsApp/Telegram group export.
---

# WhatsApp export triage

Class group exports are ~90% irrelevant (chat, memes, photos of people, screenshots, ads).
The goal is to fish out course material **without reading everything** and **without leaking personal data**.
Load `privacy-guard` together with this skill.

## Step 0 — set up
- Work on one export at a time. Exports stay outside the repo or under `local/` (git-ignored).
- Give the export a slug for `--source`, e.g. `whatsapp:bm-2023-sinif`. Never use people's names.

## Step 1 — index (no file opening yet)
```
python -X utf8 tools/archive.py whatsapp-index "<export.zip or folder>" --out local/triage/<slug>.csv
```
The CSV has one row per attachment: `score, date, time, sender (pseudonym P001…), file, ext, exists, courses, keywords, context`.
- Senders are pseudonymized; phone numbers and e-mails in the context are masked. Keep it that way.
- `keywords` prefixed with `~` came only from neighbouring messages (weak evidence).
- Files present in the export but never referenced in the chat appear with context `(not referenced in chat)`.

## Step 2 — triage in passes (stop when the remaining scores are low)
1. **Documents** (`pdf docx pptx xlsx doc ppt`), highest score first. These are usually slides, exam papers,
   homework. Open the first page / slide titles only, then intake + classify.
2. **Images with score ≥ 4** or with exam keywords in their *own* context (`vize`, `final`, `çıkmış`, `soru`,
   `cevap`, `quiz`): look at a downscaled version. Keep only photos of exam papers, boards with lecture content,
   handwritten notes. Several photos of the same exam sent together (same sender, within minutes) belong together.
3. **Images with score ≤ 3**: sample at most 20 per 1000 to confirm they are irrelevant; do not open the rest.
4. Voice notes, videos, stickers, `.vcf` contacts, `.opus`: skip entirely.
Record for every pass how many files you opened and how many you kept.

## Step 3 — move kept files into the pipeline
```
python -X utf8 tools/archive.py intake <kept files...> --source whatsapp:<slug> --batch wa-<slug>-<n>
```
Then follow `archive-intake` and `classify-and-place` for each file. Use the message context to fill
year/term/exam type (a message dated 12.04.2024 saying "vize soruları" → 2023 spring midterm).

## Step 4 — text-only information
Useful announcements in messages (exam dates, "finalde 3-7. haftalar var", instructor's topic list) may be saved
as a short `announcement` (.md) **written in your own words**, without names, phone numbers or quotes of private
messages. Example: "2024 bahar BM218 final konuları: 3–7. haftalar, DP ve greedy ağırlıklı."

## Hard rules
- **Never** commit `_chat.txt`, any part of the chat transcript, contact cards, or profile photos.
- **Never** place photos showing people, personal screenshots, ID cards, documents with phone numbers/addresses.
- The owner's personal chat ("You" / self chat) is especially sensitive: process **documents only**, and only those
  that are clearly course material; every image from that chat goes to `review-open` or is skipped, never placed directly.
- When a file is relevant but its course is unclear → `review-open` with the (masked) message context in `--reason`.
- Report: counts per pass (indexed / opened / kept / placed / reviewed / skipped), no chat contents.
