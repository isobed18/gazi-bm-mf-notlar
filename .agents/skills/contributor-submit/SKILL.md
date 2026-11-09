---
name: contributor-submit
description: For a student's own AI agent - propose files (slides, past exams, notes) to this repository through a GitHub issue or pull request that follows the repository rules. Use when a user says "add my files to the archive".
---

# Contributing files (for the contributor's agent)

You act for a student who wants to share course material. The repository's maintainer agent and a human will
review your submission. Follow this exactly; non-conforming PRs are closed.

## 1. Prepare locally
```
git clone <repo>  &&  cd gazi-bm-mf-notlar
pip install -r tools/requirements.txt
git checkout -b add/<course-or-topic>-<short-slug>
```
For each file the user gives you:
```
python -X utf8 tools/archive.py intake <files...> --source upload:<github-username>
python -X utf8 tools/archive.py scan <inbox file>
python -X utf8 tools/archive.py place <inbox file> --course <CODE> --kind <kind> [metadata] --contributor <github-username>
```
Use `classify-and-place` and `privacy-guard`. If you are not sure about a file, **do not place it**: list it in the
issue instead (see 3). Never commit `inbox/`, `review/`, `local/` (they are git-ignored; keep it so).

## 2. Check
```
python -X utf8 tools/archive.py validate   # must be 0 errors
python -X utf8 tools/archive.py index
```

## 3. Open the PR (or an issue)
- **PR** when every file is placed: title `add(<CODE>): <what>` e.g. `add(BM218): 2023 vize ve final`.
  Fill `.github/PULL_REQUEST_TEMPLATE.md` completely: source of the files (own notes / instructor / exam photos),
  consent statement, list of files with course/kind/year.
- **Issue** (template "Kaynak önerisi / Resource submission") when you are unsure where files belong or the files are
  large: attach or link them and describe them; the maintainer agent will propose a place.
- One course per PR when possible. Max ~50 files / 200 MB per PR.

## Never submit
Copyrighted textbooks as full PDFs (link them instead), chats, personal data (see `privacy-guard`), executables,
macro-enabled Office files, archives you have not extracted (`.rar`, `.7z`).
