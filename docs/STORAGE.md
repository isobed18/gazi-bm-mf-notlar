# Storage: git for metadata, Google Drive for files

| What | Where |
|---|---|
| sidecars (`*.meta.yaml`), `course.yaml`, generated READMEs, `exam-map.md`, catalog, tools, skills | **git** (this repo) |
| the resource files themselves (pdf, pptx, images, zip …) | **Google Drive mirror** `gazi-bm-mf-notlar/` with the *same folder layout* (`courses/<CODE>/<kind-dir>/…`) |

Git never contains binaries (`.gitignore` excludes every non-yaml/md file under `courses/` and `general/`).
Each sidecar has `sha256` and `size`, so the Drive copy can always be verified.

## Setup (maintainers / the archive machine)
1. Install rclone (`winget install Rclone.Rclone`).
2. `rclone config create gdrive-arsiv drive scope=drive` → log in with the **storage Google account** in the browser.
3. Recommended: your own OAuth client (rclone's shared client is being retired):
   Google Cloud Console → new project → enable *Google Drive API* → OAuth consent screen (External, add the storage
   account as test user, or publish) → Credentials → *OAuth client ID* → *Desktop app*. Then:
   `rclone config update gdrive-arsiv client_id <ID> client_secret <SECRET> --drive-auth-owner-only` and re-authorize:
   `rclone config reconnect gdrive-arsiv:`.
4. Optional: `ARCHIVE_REMOTE` env var to point to another remote/folder (default `gdrive-arsiv:gazi-bm-mf-notlar`).

## Commands
```
python -X utf8 tools/archive.py place …          # places the file AND uploads it (use --no-push to skip)
python -X utf8 tools/archive.py storage-push     # upload every local resource that is not on Drive yet
python -X utf8 tools/archive.py storage-pull [--course BM218] [--variant core]   # download missing files
python -X utf8 tools/archive.py storage-verify   # compare Drive with metadata (missing, size mismatch, untracked)
```
Rules: agents only **add** to Drive. Never delete or overwrite files on Drive; deletions are done by a maintainer.

## Sharing
- Readers who only want files: share the Drive folder `gazi-bm-mf-notlar` (viewer). The layout is browsable by course.
  People who do not want the optional student-notes layer simply skip `student-notes/` folders, or use
  `storage-pull --variant core`.
- Contributors do **not** get Drive write access. They submit through GitHub issues (attachments or links); the
  maintainer agent places and uploads (see `.agents/skills/maintainer-review`).
- CI does not need Drive access for validation. The optional `release` workflow uses a `RCLONE_CONF` secret
  (read-only use) to build download zips; add it only when needed:
  `gh secret set RCLONE_CONF < "%APPDATA%/rclone/rclone.conf"` (contains a token — keep the repo's Actions restricted).
