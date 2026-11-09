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
    S->>GH: issue with attachments/links (files) or PR (notes/metadata only)
    GH->>M: download attachments into local inbox, scan (types, macros, PDF JS, privacy, ClamAV)
    M->>GH: PR with sidecars (files uploaded to Drive) + review comment
    GH->>CI: validate.yml (schema, names, no binaries in git, index up to date)
    GH->>M: maintainer-review skill: placement, duplicates, privacy, value, notes impact
    M->>GH: one structured comment + labels
    H->>GH: approve + merge
    GH->>CI: index, release zips, site deploy; follow-ups: exam-matching, obsidian-sync
```

## Storage
Git holds metadata, notes and tools; **resource files live in a Google Drive mirror** with the same folder layout
(`gdrive-arsiv:gazi-bm-mf-notlar`, ~5 TB available). `place` uploads automatically; `storage-pull/verify` keep
machines in sync. Details: [STORAGE.md](STORAGE.md).
Consequence for contributions: PRs carry only text (metadata, notes); files arrive through **issues**
(attachments/links) and the maintainer agent places + uploads them.

## Privacy model
- Inbox, review, quarantine and local are git-ignored: raw dumps never reach git.
- Committed files passed `scan` and (for anything uncertain) a human decision.
- Names on exam/homework papers are accepted; chat text, phone numbers, personal photos are not.
- Git history is permanent: a mistake requires history rewriting (`git filter-repo`) and a force push. Prevention beats cure.
