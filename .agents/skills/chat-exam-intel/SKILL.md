---
name: chat-exam-intel
description: Read EVERY message of a class group chat (pre-split into numbered chunks) and record exam information written as text - what was asked, topics, exam style, solution hints, instructor habits, shared past-exam pointers - as structured JSONL findings per chunk. Findings of all chats are merged into one note per course. Never use keyword search instead of reading.
---

# Exam information from chat messages

Students write what came up in exams in plain words ("vizede 3 soru vardı biri DP", "ikinci soru ağaçtı",
"geçen senenin finali aynen geldi", "hoca ispat sorar", "final 4-9. haftalar"). Often without keywords, often as a
reply several lines after a question. Only reading finds it. This is the most valuable part of a chat.

## Pipeline
```
python -X utf8 tools/archive.py chat-chunk "<export folder or _chat.txt>" --slug <slug>   # done by the maintainer agent
#   -> local/chat/<slug>/chunks/NNN.txt  (each line: "<line no>| dd.mm.yyyy hh:mm P012: text"; senders pseudonymized)
#   -> you write local/chat/<slug>/findings/NNN.jsonl for every chunk you are assigned
python -X utf8 tools/archive.py chat-coverage            # every chunk must have a findings file
python -X utf8 tools/archive.py chat-merge               # all findings -> courses/<CODE>/announcements/<CODE>_..._sohbetten-sinav-bilgileri.md
```

## Reading
- Open each assigned chunk **completely** and read it top to bottom. Keep the context of the previous chunk in mind
  (a question at the end of chunk 11 may be answered at the start of chunk 12 — record it in the chunk where the answer is).
- Use the message date to know which exam period is meant (Nov/Apr = vize, Jan/Jun = final, Jan-Feb/Jul = bütünleme).
- Identify the course with `catalog/curriculum.yaml` (`aliases`, names, codes; instructor + topic often reveal it:
  "Lineer" → MAT199, "ayrık" → BM104, "devre" → BM211, "OS/işletim" → BM309, "algoritma" → BM218, "otomata" → BM303).
  If you cannot tell the course, still record the finding with `"course": null` and a short `"course_hint"`.

## What to record (one JSON object per finding)
| type | record when students say… |
|---|---|
| `asked-in-exam` | which questions/topics actually came in an exam, how many questions, which was hard, "same as last year" |
| `exam-topics` | what the exam covers (weeks, chapters, "X dahil değil") as announced or relayed |
| `exam-format` | duration, number of questions, test/classical, open/closed book, formula sheet, calculator, grading rules |
| `instructor-tip` | how an instructor asks/grades ("tanım sorar", "slayttan çıkar", "kısmi puan vermez", "her yıl semafor") |
| `solution-hint` | how a past exam question is solved / its answer, discussed in the chat |
| `resource-pointer` | a past exam / solution / note was shared (file name in `[ek: …]`) — record course + what it is |
| `grade-distribution` | anonymous course-wide grade statistics (no individual grades) |
Do **not** record: schedules, room/date logistics, registration, social chat, complaints, individual grades, anything
about a person. One message can yield several findings; a long discussion can be one finding.

## Findings file format — `local/chat/<slug>/findings/NNN.jsonl`
One JSON object per line, UTF-8 (write with your file-edit tool; never through PowerShell):
```json
{"chunk": 12, "lines": "2850-2871", "date": "21.11.2023", "course": "BM103", "exam": "midterm", "type": "asked-in-exam", "summary": "Vizede minterm/maxterm sadeleştirme ve bilgisayar kuşakları soruldu; lab konuları çıkmadı."}
{"chunk": 12, "lines": "2903", "date": "22.11.2023", "course": null, "course_hint": "Şerife hocanın dersi", "exam": "final", "type": "exam-topics", "summary": "Final 7. bölüm özdeğer-özvektör dahil, 4-5 soru."}
```
- `exam`: `midterm | final | makeup | quiz | resit | null`. `date`: the message date (dd.mm.yyyy).
- `summary`: Turkish, your own words, **specific** (topics, question types, numbers), ≤ 45 words. Instructor names are
  fine; never student names, pseudonyms (P012), phone numbers, or verbatim private messages.
- A chunk with nothing to record gets exactly one line: `{"chunk": 12, "none": true}` — every assigned chunk needs a file.

## Quality bar
Typical class chats yield **2–10 findings per 250 lines during exam periods** and few outside them. If you find
nothing in an exam-period chunk, read it again. Prefer recording a borderline finding to dropping it.
