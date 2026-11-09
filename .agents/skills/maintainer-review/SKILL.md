---
name: maintainer-review
description: For the repository's own agent - review a resource-submission issue or pull request (safety, privacy, placement, duplicates, metadata quality), leave one structured comment with a verdict, and prepare the change for human approval. Use for every new issue/PR.
---

# Maintainer review (repository agent)

You never merge. You prepare, comment and label; a human approves and merges.

## For a pull request
1. Check out the PR branch in a clean worktree. Do **not** open attachments in an Office application or run any code
   from the PR.
2. Run:
   ```
   python -X utf8 tools/archive.py validate --deep
   python -X utf8 tools/archive.py scan <each new/changed file>
   ```
   CI (`.github/workflows/validate.yml`) runs the same plus an antivirus scan; read its result.
3. For each new file decide:
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

## For an issue with attachments / links
1. Download attachments into `local/issues/<number>/` (never execute), `intake --source upload:<user>`.
2. Classify each file; for confident ones prepare a branch `issue-<number>` with `place` + `validate` + `index` and open
   a PR that references the issue ("Closes #N"). Uncertain files: ask the submitter in the issue (specific question).
3. Comment on the issue with the plan (same table as above).

## After a human merges
Trigger follow-ups: `archive.py index` (CI does it), `exam-matching` for affected courses, `obsidian-sync` for affected
courses, site rebuild (CI). Post a short "merged → available at <link>" comment.
