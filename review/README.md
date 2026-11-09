Human review queue (git-ignored). Each `R-YYYYMMDD-NNN/` folder holds one file and a `review.md`.
Maintainer: fill in `decision:` and `comment:` in review.md, then ask an agent to run
`python -X utf8 tools/archive.py review-apply <id>` (or `review-list` to see what is pending).
