---
name: review-queue
description: Open review items for files that need a human decision, write clear proposals and questions for the maintainer, and apply the maintainer's decisions. Use whenever confidence is not high, a file belongs to no course, or a scan says review.
---

# Review queue (human supervision)

The maintainer is a human who reads `review/R-*/review.md`, writes a decision and a comment, and asks an agent
to apply it. Make their job fast: one clear proposal, specific questions.

## Open
```
python -X utf8 tools/archive.py review-open <inbox file> \
  --reason "<1-2 sentences: what it is and why you are not sure>" \
  [--course CODE --kind KIND | --general CATEGORY] [--title "..."] [--confidence low|medium] \
  [--question "Specific question?"]  (repeatable)
```
Good reason: "3 sayfalık sınav fotoğrafı, başlıkta sadece 'Final 2023' yazıyor; sorular graf algoritmaları → BM218 olabilir."
Bad reason: "not sure".
Always propose something (course+kind or general category) even with low confidence.
Group near-identical items: if 15 photos belong to the same exam, open **one** item for the first photo and mention
the others in the reason (keep the rest in the inbox until the decision is known).

## Decisions the maintainer can write (`decision:` line in review.md)
```
approve                         place exactly as proposed
place BM218 exam 2023 Vize      place into a course with a title
general career Staj rehberi     place under general/<category>/
reject                          delete (junk, private, duplicate)
quarantine                      keep aside as unsafe
```
plus a free-text `comment:`. If the comment contains extra instructions ("year is 2022", "merge with R-…"),
follow them: run `place` yourself with the corrected metadata instead of `review-apply`, then close the item by
moving it to `review/_closed/` with `status: closed (manual)`.

## Apply
```
python -X utf8 tools/archive.py review-list            # DECIDED items have a decision
python -X utf8 tools/archive.py review-apply R-YYYYMMDD-NNN
```
Then process the related files you kept in the inbox the same way. Learn from comments: if the maintainer
corrects a pattern ("WA images from group X are lab photos of BM222"), apply it to similar pending files and
mention it in your report.

## In a GitHub setting
Review items become issue/PR comments instead (see `maintainer-review`). The same decision words are used as
labels/commands: `/approve`, `/place BM218 exam`, `/general career`, `/reject`.
