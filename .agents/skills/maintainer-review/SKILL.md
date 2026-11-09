---
name: maintainer-review
description: For the repository's own agent - review a resource-submission issue or pull request (safety, privacy, placement, duplicates, metadata quality), leave one structured comment with a verdict, and prepare the change for human approval. Use for every new issue/PR.
---

# Maintainer review (repository agent)

You never merge. You prepare, comment and label; a human approves and merges.

Files live on Google Drive, not in git. Submissions of **files** come as issues; PRs carry only text
(metadata, catalog, docs). A PR that adds binaries is rejected (CI fails); ask the author to open an issue instead.

## For a pull request (text only)
1. Check out the PR branch in a clean worktree; never run code from the PR.
2. `python -X utf8 tools/archive.py validate` and read CI.
3. Review metadata changes for correctness (course codes exist, kinds valid, topics consistent with `exam-map.md`).
4. Comment and label as below.

## Deciding about each submitted file (used by the issue flow below)
1. Run `archive.py scan` on it (antivirus runs if ClamAV is installed on the archive machine).
2. Decide:
   - **Placement**: right course? right kind? metadata plausible (year/term/exam type)? Compare against
     `catalog/curriculum.yaml` aliases and the file content (first page / slide titles).
   - **Duplicate / near-duplicate**: same exam already present in a different scan? (`catalog/index.json`, same
     course+year+term+exam_type) → ask to drop or mark as better quality.
   - **Privacy** (`privacy-guard`): look at every image. Names on exam papers are fine.
   - **Copyright**: full commercial textbooks → request a link instead.
   - **Value**: does it add something (new year, solution, better scan, missing topic)?
   - **Notes impact**: does this change study notes? (new exam → `exam-matching` should be re-run for the course;
     new slides → Obsidian notes for that week need updating). List these follow-ups.
4. Post **one** comment:
   ```
   ## Agent review — <APPROVE | CHANGES REQUESTED | NEEDS HUMAN>
   | File | Course/kind | Verdict | Note |
   |---|---|---|---|
   ...
   **Safety:** scan/AV summary  **Privacy:** ...  **Duplicates:** ...
   **Follow-ups after merge:** exam-matching BM218, obsidian-sync BM218
   ```
   Labels: `agent-approved`, `changes-requested`, `needs-human`, `course:<CODE>`.
5. If small fixes are needed (wrong kind, missing year) and the PR allows maintainer edits, push a commit that
   re-places the file with `archive.py` and explain it in the comment.

## For an issue with attachments / links (the main file flow)
1. Download attachments/links into `local/issues/<number>/` (never execute anything); extract zips with Python's
   `zipfile`; `intake --source upload:<github-user>`.
2. Apply "Deciding about each submitted file" above. Uncertain files: ask the submitter one specific question in the issue,
   or `review-open` them for the human maintainer.
3. For accepted files: branch `issue-<number>`, `place` (uploads to Drive) + `validate` + `index`, commit **only**
   sidecars/READMEs, open a PR "Closes #N" with the review table. The human merges; Drive already has the files.
4. If the PR is rejected, tell the human; files uploaded to Drive for that PR must be removed by a maintainer.

## After a human merges
Trigger follow-ups: `archive.py index` (CI does it), `exam-matching` for affected courses, `obsidian-sync` for affected
courses, site rebuild (CI). Post a short "merged → available at <link>" comment.
