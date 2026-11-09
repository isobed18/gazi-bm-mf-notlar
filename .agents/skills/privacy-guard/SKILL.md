---
name: privacy-guard
description: Decide what counts as personal data in this archive and how to handle it (skip, review, redact). Load whenever handling chat exports, images, personal folders or any file archive.py scan flags with "possible personal data".
---

# Privacy guard

This archive will be shared with other students and may become public. Treat privacy mistakes as unrecoverable
(git history keeps everything).

## Personal data → never place
- Chat transcripts or screenshots of chats (WhatsApp, Telegram, Instagram, e-mail).
- Phone numbers, private e-mail addresses, home addresses, TC kimlik numbers, IBAN/bank info, passwords, tokens.
- Photos of people (selfies, group photos, events), ID cards, student cards, transcripts, grade lists,
  health reports, receipts, tickets, anything showing someone's private life.
- GPS location (archive.py strips EXIF GPS from images on place).
- Grades / GPA of a person (including the archive owner).
- Course-wide letter-grade distributions are allowed only as anonymous totals or percentages with no student-level rows,
  names, IDs, or small cells that could identify a student. Use the course and stated period when present; otherwise
  label the resource `Geçmiş Harf Notu Dağılımları`.

## NOT personal data in this project (do not redact)
- Names written on exam papers, homework, lab reports, project reports, handwritten notes.
- Instructors' names and university e-mail addresses (`@gazi.edu.tr`), course codes, classroom numbers.

## Handling
| Case | Action |
|---|---|
| Course material with a phone number/e-mail somewhere in it (e.g. on a homework cover) | `review-open` and say where it is; the maintainer decides (crop/redact or accept) |
| Mixed photo: exam paper + a person's face/hand with ring etc. | `review-open` |
| Clearly private, no course value | skip; do not copy anywhere in the repo |
| Unsure | `review-open` — never place |

`archive.py scan` flags phones, e-mails, valid TC numbers, IBANs and chat-transcript-like text in documents. It
cannot see images: **you** must look at images before proposing them.

## Writing about files
In reports, review items, PR comments and notes: describe files by type and course ("BM218 vize fotoğrafı, 3 sayfa"),
never quote private messages, never write people's names from chats, never include phone numbers. Pseudonyms
from `whatsapp-index` (P001…) are fine in local reports, not in committed files.
