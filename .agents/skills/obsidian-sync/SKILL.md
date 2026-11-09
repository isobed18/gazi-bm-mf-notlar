---
name: obsidian-sync
description: Generate or update the official Obsidian study vault from this archive (one-way, semester-based layout - Dersler / dönem / ders / Çıkmış Sorular, Ders Notları, Slaytlar) with archive.py export-obsidian. Use after new material was placed, verified or chat findings were merged.
---

# Obsidian sync (archive → official vault)

The archive is the source of truth. The official vault is **generated**; do not hand-edit its generated notes.
Vault paths come from `local/config.yaml` (`vault:` official, `personal_vault:` private). **Never** read, edit,
copy or export into the personal vault.

## Run
```
python -X utf8 tools/archive.py storage-pull                    # files must be local to be copied (or --course X)
python -X utf8 tools/archive.py export-obsidian [--variant core] [--course BM218 …] [--dry-run]
```

## Layout produced
```
Başlangıç.md
Dersler/
  Dersler.md                                  semesters → courses with counts
  1. Sınıf Güz/1. Sınıf Güz.md               semester note (table of its courses)
  1. Sınıf Güz/BM101 - Bilgisayar Programlama I/
     BM101 - Bilgisayar Programlama I.md      course hub (links to the notes below, Dönem: [[…]])
     BM101 Çıkmış Sorular.md                  exams (newest first) + solutions + "Öğrencilerden aktarılan sınav bilgileri"
     BM101 Ders Notları.md                    lecture notes, student notes (optional layer), summaries
     BM101 Slaytlar.md                        instructor slides
     BM101 Harf Notu Dağılımları.md           anonymous grade distributions (only if any)
     Arsiv/<kind-dir>/…                       the files
  Seçmeli Dersler/…                           electives (no fixed curriculum semester)
```
- Semester = the course's `semester` in `catalog/curriculum.yaml` (shared vault → curriculum semester, not a
  student's personal history). Legacy courses use their old curriculum semester.
- Exported kinds: exams, exam solutions, lecture/student notes, summaries, slides, grade distributions, and the merged
  chat exam-info note (`announcement` .md from `chat-merge`). Not exported: syllabus, schedules, books, homework,
  internship/career material, `deprecated` resources.
- Old course folders from earlier layouts are moved into the semester folders; stale generated notes are removed.
  Notes without `generated: true` (user-written) are never overwritten or removed.

## Rules
- Note names stay unique by prefixing the course code; no `[ ] # ^ | \ : * ? " < >` in names.
- Never write personal data (grades, GPA, student numbers, chat quotes) into the vault.
- After export check: no broken `[[links]]`, no duplicate note names, no `?`/mojibake.
