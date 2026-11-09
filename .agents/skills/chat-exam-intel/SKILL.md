---
name: chat-exam-intel
description: Read EVERY message of an exported group chat in sequential batches and extract exam information written as text (what was asked in exams, exam topics, instructor announcements, exam format, tips) into per-course markdown notes in the archive. Never use keyword search as a substitute for reading. Use for any WhatsApp/Telegram chat export.
---

# Exam information from chat messages

Students often write what came up in an exam ("vizede 3 soru vardı, biri DP", "final konuları 4-9. hafta",
"hoca açık uçlu sorar", "geçen sene de aynısı çıktı"). This information is valuable and only findable by reading.

## The rule
**Read every message.** Split the chat into consecutive batches (≈300 lines; respect day boundaries) and read each batch
completely, in order. A keyword search (`çıkmış`, `vize`, `final`, a course name) may be used once at the start to get
oriented, but it is **not** a substitute: information is often phrased without keywords ("bugünkü sınavda şu geldi",
"ikinci soru ağaçtı"). Coverage is checked.

## Setup
- Chat file: `<export>/_chat.txt` (format `[dd.mm.yyyy, hh:mm:ss] Sender: text`). Count its lines.
- Progress file: `local/progress/<slug>-chat.md` with one row per batch:
  `| batch | lines | dates | findings |` — update after every batch. The last batch must end at the last line.
- Findings log (local, not committed): `local/progress/<slug>-chat-findings.md` — per finding: date, line range,
  course, type, your own summary. No names, no phone numbers, no verbatim private messages.

## What counts as a finding
| Type | Example (your own words) |
|---|---|
| asked-in-exam | "2023 bahar BM218 vize: 3 soru — Master teoremi, DP (LCS), greedy ispatı" |
| exam-topics | "CENG206 final: 5–11. haftalar, Newton-Raphson ve interpolasyon ağırlıklı" |
| exam-format | "MATH201 vize 90 dk, 5 soru, formül kâğıdı yok" |
| instructor-tip | "BM309 hocası tanım sorar; semaforlar her yıl geliyor" |
| resource-pointer | "BM222 için 2022 final çözümleri grupta paylaşıldı (dosya: …)" → tell the media agent / note the file name |
Not findings: social chat, schedules without content, complaints, personal matters, grades of people.

## Output (after all batches are read)
For every course with findings, write one markdown file and place it:
```
local/tmp/<slug>/<CODE>-sinav-bilgileri.md
python -X utf8 tools/archive.py place local/tmp/<slug>/<CODE>-sinav-bilgileri.md --copy --course <CODE> --kind announcement \
  --title "Sohbetten sınav bilgileri (<slug>)" --source whatsapp:<slug> --status unverified
```
File format (Turkish, written by you, UTF-8 via your file-edit tool):
```markdown
# <CODE> – Sohbetten derlenen sınav bilgileri
Kaynak: <slug> grup sohbeti · derleme tarihi · doğrulanmadı (unverified)

## 2023-2024 Bahar
- **Vize** (12.04.2024): 3 soru — Master teoremi, LCS ile DP, greedy ispatı. *(öğrenci aktarımı)*
- **Final konuları**: 4–9. haftalar.

## Genel ipuçları
- …
```
Group by academic year/term, newest first. Each bullet = one finding, with the message date. If a course is unclear,
write it into a `GENEL-sinav-bilgileri.md` and open a review item for it (`review-open --general university`).

## Finish
`validate`, `index`, `review-publish` (if you opened items). Report: total lines, batches read (must cover 1..N),
findings per course, files placed. Never commit.
