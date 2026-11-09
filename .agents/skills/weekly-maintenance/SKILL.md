---
name: weekly-maintenance
description: The weekly run of the archive - apply maintainer decisions from GitHub issues, take in new files from drop folders and submission issues (scan incl. antivirus, classify, place), verify unverified resources, process new chat exports, then let the deterministic post step index, audit, export the vault and commit. Run by tools/weekly.ps1 (scheduled) or by hand.
---

# Weekly maintenance

`tools/weekly.ps1` runs three stages; you are the middle one:
1. `python -X utf8 tools/weekly.py pre` (deterministic) — `git pull`, `review-sync`, collects new files from the drop
   folders (`drop_dirs` and Drive `drive_drop` in `local/config.yaml`) into one inbox batch, lists open `submission`
   issues and new chat exports. Writes `local/weekly/<date>/todo.md`.
2. **You** (agy, Gemini) — work through `todo.md`:
   - **Review comments** listed there (plain-language answers from the maintainer): interpret and apply per
     `review-queue` (`review-decide`, then `review-ack`).
   - **New inbox batch**: for every file `scan` (antivirus runs automatically: Windows Defender / ClamAV) then
     `classify-and-place` with `--status unverified` (drop folders are trusted sources) or `review-open` when unsure.
     At the end `review-publish --source <batch source>`.
   - **Form submissions** (`## Form submissions` in todo.md): untrusted; scan every file, use the response sheet CSV only as
     a hint, place with `--status unverified`, review-open anything doubtful or possibly private.
   - **Submission issues**: follow `maintainer-review` (download attachments into `local/issues/<n>/`, never execute,
     intake, scan, place, comment). Close the issue only after the maintainer approved.
   - **New chat exports** (zip/folder with `_chat.txt`): `chat-chunk --slug <slug>`, then read every chunk per
     `chat-exam-intel` (small chats yourself; for > 20 chunks write `local/weekly/<date>/needs-chat-agents.md` so the
     maintainer starts parallel reading jobs). Media/documents of the export: `whatsapp-triage`.
   - **Verification**: `verify-resources` for resources placed this week (status `unverified`), at most ~60 files.
   - Write `local/weekly/<date>/report.md`: what was placed, reviewed, verified, skipped; open questions.
3. `python -X utf8 tools/weekly.py post` (deterministic) — `chat-merge` (if findings changed), `index`, `validate`,
   `audit`, `export-obsidian`, `storage-verify`, then commits `catalog/ courses/ general/` and pushes. If `audit` or
   `validate` fails it does **not** commit and writes the reason into the report.

## Rules
- Everything in `AGENTS.md` applies (privacy, decisive placement, read everything, UTF-8 via file-edit tool).
- Never commit yourself; the post stage does it after the audit.
- Do not touch the personal vault; only `export-obsidian` writes the official vault.
- If there is nothing to do, write a one-line report and stop.
