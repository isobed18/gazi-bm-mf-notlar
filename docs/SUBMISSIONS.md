# How files reach the archive

## Channels
| Channel | Who | How it arrives | Trust |
|---|---|---|---|
| **Google Form "Kaynak Gönder"** (main) | anyone with a Google account | file upload question → form owner's Drive folder; answers (course, kind, year) → response sheet | untrusted → `--status unverified`, review when doubtful |
| GitHub issue (optional public `gazi-bm-kaynak-gonder` repo with the issue form) | people with a GitHub account | issue attachments / links | untrusted |
| Drop folders `drop_dirs`, Drive `drive_drop` | maintainers only | local folder / private Drive folder | trusted |

Why a Google Form and not a shared Drive folder or Git LFS:
- **Immutable for submitters.** Uploaded files are stored in the form owner's Drive; a respondent can neither see nor
  delete other submissions (nor their own after submitting). A public editable Drive folder would let anyone delete
  everything; Drive has no native "file request" for consumer accounts — the Form upload question is that.
- **No GitHub account, no git, no LFS** for contributors; binaries never enter git.
- **Safety**: the form limits file types (PDF, image, document, presentation) and size; Google scans files up to
  100 MB; the weekly run copies files out, scans every file (type allowlist, magic bytes, macros, PDF active content,
  privacy patterns, Windows Defender / ClamAV) and never opens anything with macros or executes anything.
- **Privacy**: "Collect e-mail addresses" stays **off**. Forms with a file-upload question require sign-in, but the
  response does not store who uploaded unless the owner enables it.

## Setting up the form (once, with the storage Google account)
1. forms.google.com → new form **"Gazi BM Kaynak Gönder"**. Settings → Responses: *Collect email addresses* = **Do not collect**,
   *Limit to 1 response* = off, *Allow response editing* = **off**.
2. Questions:
   - **Dosyalar** — *File upload*: allow specific types: PDF, Image, Document, Presentation, Spreadsheet; max 10 files;
     max size 100 MB.
   - **Ders** — *Short answer*: "Ders kodu veya adı (örn. BM218 Algoritma)".
   - **Tür** — *Multiple choice*: Çıkmış sınav, Sınav çözümü, Ders notu (hoca), Öğrenci notu, Slayt, Özet, Ödev, Diğer.
   - **Yıl / dönem** — *Short answer*: "örn. 2023-2024 Güz vize".
   - **Not** — *Paragraph* (optional).
   - **Onay** — *Checkbox* (required): "Paylaşma hakkım var; dosyalarda kişisel veri (sohbet, telefon, kimlik) yok."
3. Responses → *Link to Sheets* → create the response spreadsheet.
4. Put the two paths into `local/config.yaml` → `form.uploads` (the "… (File responses)/Dosyalar (File responses)" folder that
   Forms creates in Drive) and `form.responses` (the spreadsheet). Check with `rclone lsf "<uploads path>"`.
5. Share the form link (README, class groups).

## Weekly processing
`tools/weekly.py pre` copies new uploads into `local/weekly/<date>/form/`, moves them to `_islendi/<date>/` inside the
upload folder (owner-only; nothing is deleted), exports the response sheet as CSV and intakes the files
(`--source form:<date>`). The agent then scans, classifies (response sheet = hint only), places with
`--status unverified` or opens review items. Verified on a later run (`verify-resources`).
