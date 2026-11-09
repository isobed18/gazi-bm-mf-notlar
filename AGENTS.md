# AGENTS.md — rules for every AI agent working in this repository

This repository is a **course resource archive** for Gazi University Computer Engineering
(Bilgisayar Mühendisliği). It stores lecture slides, notes, past exams, homework, labs and
student notes, organised by course, with a metadata sidecar for every file. It is
**independent of Obsidian**; an Obsidian vault and a public website are *generated* from it.

Read this file completely before doing anything. Then load the skill that matches your task
from `.agents/skills/` (skills are loaded on demand; read the SKILL.md of the one you use).

## Repository map
| Path | What | Committed? |
|---|---|---|
| `catalog/curriculum.yaml` | every course: code, names, curriculum semester, category, **aliases** | yes |
| `catalog/taxonomy.yaml` | resource kinds → folder names, general categories, download variants | yes |
| `catalog/index.json` | generated index of all resources (`archive.py index`) | yes |
| `courses/<CODE>/<kind-dir>/` | resources + `*.meta.yaml` sidecars; `README.md` is generated | sidecars/md only — files live on **Google Drive** |
| `general/<category>/` | non-course resources, **only after human review** | sidecars/md only |
| `inbox/<batch>/` | raw intake (may contain private material) | **never** |
| `review/R-…/` | items waiting for a human decision | **never** |
| `quarantine/` | blocked/unsafe files | **never** |
| `local/` | logs, temp extraction, personal overrides | **never** |
| `tools/archive.py` | the only way to add/move resources | yes |
| `.agents/skills/` | task procedures for agents | yes |

## Non-negotiable rules
1. **Use `tools/archive.py` for every file operation** on `courses/` and `general/`
   (`intake`, `scan`, `place`, `review-open`, `review-apply`, `validate`, `index`).
   Never copy files there by hand and never hand-write a `.meta.yaml`.
   Run it as `python -X utf8 tools/archive.py <command>`.
2. **Privacy first** (details: `.agents/skills/privacy-guard/SKILL.md`):
   - Never commit chat transcripts, phone numbers, e-mail addresses, TC kimlik numbers, IBANs,
     personal photos (people, selfies, homes, screenshots of private chats), location data.
   - Names written on exam papers, homework and lab reports are **not** a privacy problem in this
     project. Do not spend effort redacting them.
   - When unsure whether something is private → `review-open`, never `place`.
3. **Safety**: never execute, open with macros, or unpack-and-run anything you receive.
   `archive.py scan` blocks dangerous types; a `block` verdict goes to quarantine, full stop.
4. **Supervision policy — be decisive.** Place directly when the course and kind are clear from
   reasonable evidence (code/name/alias in the file name, header, content or the message that came
   with it), the scan verdict is `ok` and it is not a duplicate. Most course material is clear: do
   not be pessimistic, do not ask the human about things you can determine yourself.
   Material from messy sources (WhatsApp, dumps) is placed with `--status unverified`; a later stage
   (Obsidian sync / human) confirms it.
   Open a review item only when you genuinely cannot decide (two plausible courses, unreadable,
   possibly private) — and **always** for material that belongs to no course (the maintainer decides
   whether it goes to `general/` or is dropped). Review items are published as **GitHub issues**
   (`review-publish`), see `review-queue`.
5. **Process everything, in batches — never replace reading with searching.** Keyword search
   (e.g. "çıkmış", "vize") or the `whatsapp-index` ranking may be used to *start* quickly, but they
   are not a substitute: every message of a chat and every file of a batch must be looked at, batch
   by batch, with a progress file proving coverage (see `whatsapp-triage`). Irrelevant items are
   skipped after being looked at, not before.
6. **No invented content.** Titles, years, exam types and topics come from the file itself or
   its message context. If unknown, leave the field empty.
7. **Text encoding**: write text files as UTF-8 with the agent's native file-edit tool
   (`apply_patch` / write tool). On Windows never pipe non-ASCII text through PowerShell
   (`echo`, `Set-Content`, here-strings): PowerShell 5.1 turns Turkish characters into `?`.
8. **Student notes are an optional layer** (`kind: student-notes`). Keep them in that kind so
   the `core` download variant can exclude them. Set `--handwritten` for scans of handwriting.
9. **Storage**: resource files are not in git; they are mirrored to Google Drive (`docs/STORAGE.md`).
   `place` uploads automatically. Use `storage-pull [--course X]` to download files you need to read,
   `storage-verify` to check. Never delete or overwrite anything on Drive.
10. Before you finish: `archive.py validate` must report 0 errors, then run `archive.py index`.

## Maintainer's content priorities
The maintainer wants a compact study vault organised **by semester** (Dersler → dönem → ders → Çıkmış Sorular /
Ders Notları / Slaytlar), generated by `archive.py export-obsidian`. Work in this order:
1. PDF past exam questions and solutions (highest priority).
2. Course notes, including official notes and handwritten student notes.
3. Official instructor slides.
4. Course-level aggregate letter-grade distributions, when no individual student is identifiable.

Do not spend review or Obsidian space on curricula, course/exam schedules, homework calendars or one-off homework
details, academic calendars, general university documents, internship rules/forms/chats, career material, or unrelated
files. Skip these without asking. Books are secondary: if the course match is clear, archive them without asking, but
do not surface them in the official study vault.
Include an aggregate letter-grade distribution only when it contains counts/percentages without student names,
numbers, or individual grades. If a period is stated, record it; otherwise file it under the course as
"Geçmiş Harf Notu Dağılımları". Never copy an identifiable grade list.
For a clearly identified elective, use its course name as the identity; do not block useful notes, slides, or exams
just because its catalog code is missing or uncertain. Ask only when the material itself cannot be safely or
reliably assigned. Keep questions to the maintainer short and limited to decisions that affect the three priorities.

## Obsidian separation
Two vaults exist on the maintainer's machine; their paths are in `local/config.yaml` (git-ignored, see
`config.example.yaml`), never in committed files:
- `personal_vault` — the maintainer's private vault. **Never** read, edit, copy, or export into it.
- `vault` — the official, archive-generated study vault. Sync is one-way: archive → official vault
  (`archive.py export-obsidian`). Never import personal notes into the archive or the official vault.
A transcript may be used locally only to match course names/codes; never copy grades, averages, student numbers,
or transcript pages anywhere.

## Vocabulary
- *kind*: one of the keys in `catalog/taxonomy.yaml` (`exam`, `slides`, `student-notes`, …).
- *year/term*: academic year start + `fall|spring|summer` (2023 fall = 2023-2024 Güz).
- *exam_type*: `midterm` (vize), `final`, `makeup` (bütünleme), `quiz`, `resit` (tek ders), `sample`.

## Skills
| Skill | Use when |
|---|---|
| `archive-intake` | any new file or folder arrives (upload, drive dump, zip) |
| `classify-and-place` | deciding course/kind/metadata for one file and placing it |
| `whatsapp-triage` | processing an exported WhatsApp chat (zip/folder): media and documents |
| `chat-exam-intel` | reading every chat message to extract exam information written as text |
| `privacy-guard` | anything that may contain personal data (always for chats/images) |
| `review-queue` | opening review items, writing good questions, applying decisions |
| `exam-matching` | linking past exam questions to course topics, "most asked topics" |
| `contributor-submit` | a student's agent proposing files to this repo (issue/PR) |
| `maintainer-review` | the repository's agent reviewing an issue/PR |
| `obsidian-sync` | generating/updating the Obsidian vault from this archive |
| `verify-resources` | confirming or fixing automatically placed (unverified) resources |
| `weekly-maintenance` | the weekly run: issues, drop folders, scan, verify, export, commit |
