# Architecture

## Layers
```mermaid
flowchart LR
    subgraph Sources
      WA[WhatsApp exports] ; DR[Drive folders] ; UP[Student uploads / PRs] ; INS[Instructor material]
    end
    Sources --> IN[inbox/ (private)]
    IN -->|scan + classify| D{confident?}
    D -->|yes| AR[courses/CODE/kind + .meta.yaml]
    D -->|no / no course| RV[review/R-… (human decides)]
    RV -->|decision| AR
    RV -->|general| GE[general/category]
    IN -->|unsafe| Q[quarantine/]
    AR --> IDX[catalog/index.json + course READMEs]
    AR --> OB[Obsidian vault (study notes)]
    AR --> SITE[Public site + release zips (full / core)]
```
- **Archive (this repo)**: the source of truth for *files* and their metadata. Tool-agnostic: plain folders, YAML
  sidecars, a JSON index. Any agent/tool can read it.
- **Obsidian vault**: generated study layer (hub/topic/past-exam notes) that links to archive files.
  `archive.py export-obsidian` copies files, agents write notes (`obsidian-sync` skill).
- **Site**: later, a static site (e.g. Quartz, which renders Obsidian-style markdown) built from the notes + course
  READMEs, deployed by CI on merge.

## Ingestion pipeline (local, with the owner as supervisor)
1. `intake` → inbox with sha256 + duplicate detection (against archive and earlier inbox batches).
2. Triage (big dumps): `whatsapp-index` ranks attachments; agents open only promising files.
3. `scan` → `ok | review | block` (type allow/block lists, magic bytes, PDF active content, Office macros/external
   links, size limits, privacy patterns, optional ClamAV).
4. `place` (high confidence) or `review-open` (everything else, and **always** for non-course material).
5. Owner edits `decision:`/`comment:` in `review/R-…/review.md`; `review-apply` executes it.
6. `validate` + `index`; commit `courses/ catalog/ general/`.

Agents used: **agy (Gemini 3.8 Flash, medium)** for WhatsApp/large-dump triage into the archive;
**Codex (gpt-6-luna)** agents for writing Obsidian notes from the archive.

## Public contribution flow (phase 2, GitHub)
```mermaid
sequenceDiagram
    participant S as Student + own agent
    participant GH as GitHub (issue / PR)
    participant CI as CI (validate, AV scan)
    participant M as Maintainer agent
    participant H as Human maintainer
    S->>GH: PR (files placed with archive.py) or issue (attachments)
    GH->>CI: validate.yml (schema, names, privacy regex, ClamAV, size)
    GH->>M: maintainer-review skill: placement, duplicates, privacy, value, notes impact
    M->>GH: one structured comment + labels
    H->>GH: approve + merge
    GH->>CI: index, release zips, site deploy; follow-ups: exam-matching, obsidian-sync
```

## Storage decision (open)
Binary files are tracked with **Git LFS** (`.gitattributes`). GitHub's free LFS quota is small (≈1 GB storage and
1 GB/month bandwidth), which a full archive will exceed once public. Options before going public:
1. Buy GitHub LFS data packs (simplest).
2. Keep only metadata + small files in git; store binaries in object storage (Cloudflare R2 / Backblaze B2) keyed by
   sha256; `archive.py` would download on demand. Sidecars already carry `sha256`, so this is a drop-in change.
3. Hugging Face dataset repo for binaries (free, large), git repo for metadata/notes.

## Privacy model
- Inbox, review, quarantine and local are git-ignored: raw dumps never reach git.
- Committed files passed `scan` and (for anything uncertain) a human decision.
- Names on exam/homework papers are accepted; chat text, phone numbers, personal photos are not.
- Git history is permanent: a mistake requires history rewriting (`git filter-repo`) and a force push. Prevention beats cure.
