---
name: obsidian-sync
description: Generate or update the Obsidian vault from this archive - copy resources with archive.py export-obsidian, then write/refresh per-course study notes (hub, topic notes, past-exam notes) following the vault conventions. Use when the user wants the vault updated after new material was placed.
---

# Obsidian sync (archive → vault)

The archive is the source of truth for **files**. The vault holds **study notes** that link to those files.

## 1. Copy resources
```
python -X utf8 tools/archive.py export-obsidian --vault "<vault path>" [--variant core] [--dry-run]
```
- Finds the existing course folder in the vault (`Dersler/**/<CODE> - …`), otherwise creates
  `Dersler/<N>. Sinif <Guz|Bahar>/<CODE> - <Name>` from the curriculum semester (electives: `Dersler/Secmeli Dersler`).
- Copies files to `<course folder>/Arsiv/<kind-dir>/` (only new ones) and rewrites `<CODE> Arsiv Kaynaklari.md`.
- `--variant core` leaves out `student-notes`.

## 2. Write notes (per course, only courses that changed)
Vault conventions (learned the hard way; follow them):
- Course hub: `<CODE> - <Name>.md` (same name as the folder). Front matter `tags: [<code>, ders, <donem-tag>]`,
  `Dönem: [[<semester note>]]`, one-line description, topic table, link to `[[<CODE> Arsiv Kaynaklari]]`,
  link to `[[<CODE> Cikmis Sorular]]`.
- Topic notes: `<CODE> - <Topic>.md`, **1.5–4 KB**, specific to the topic: definitions, key formula/algorithm/code,
  one concrete worked example, a `> [!warning]` with a typical mistake. Header line:
  `Üst: [[hub]] · Önceki: [[…]] · Sonraki: [[…]] · Kaynak: [[file.pdf]]`.
- **No filler**: no generic paragraphs repeated across notes ("solution approach…", "test yourself…"). If material is thin,
  the note is short.
- Past exams note `<CODE> Cikmis Sorular.md`: built from `courses/<CODE>/exam-map.md` (see `exam-matching`):
  per exam a link + question→topic mapping, "En çok çıkan konular".
- Note names are unique across the vault (Obsidian resolves links by name) → always prefix with the course code.
- No characters `[ ] # ^ | \ : * ? " < >` in file names.
- Write files with your file-edit tool as UTF-8. On Windows never pass Turkish text through PowerShell.
- Never write personal data (grades, GPA, student numbers) into the vault; the vault is shared.
- Do not delete user-written notes. Only overwrite notes you generated (they carry `generated: true` in front matter —
  add it to every note you create).

## 3. Check
Run the vault checker if available (`python -X utf8 <vault-tools>/validate.py`) or at least: no broken `[[links]]`,
no duplicate note names, no `?`/mojibake in Turkish text. Report per course: notes written, files copied.
