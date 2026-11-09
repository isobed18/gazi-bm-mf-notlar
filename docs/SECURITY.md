# Security & privacy policy

## File safety (enforced by `tools/archive.py scan` and CI)
| Check | Result |
|---|---|
| Blocked types: exe, msi, bat, cmd, ps1, vbs, js-scripts as attachments, lnk, dll, jar, apk, iso, docm/xlsm/pptm, rar, 7z… | block → quarantine |
| Extension does not match content (magic bytes) | block |
| Office file with VBA macros (`vbaProject.bin`) | block |
| PDF with JavaScript / Launch / EmbeddedFile / RichMedia / XFA | review |
| Office file with external links, legacy .doc/.ppt/.xls | review |
| zip archives | review (extract, place contents individually) |
| > 100 MB review, > 500 MB block, empty file block | |
| ClamAV (`clamscan`) when installed; always in CI | infected → block |
| Images: EXIF GPS stripped when placed | |

## Privacy (enforced by scan heuristics + agent skill `privacy-guard` + human review)
Not allowed: chat transcripts/screenshots, phone numbers, private e-mails, TC kimlik numbers, IBANs, photos of people,
ID/student cards, grade lists, transcripts, location data.
Allowed: names on exam papers, homework, reports and notes; instructors' names and university e-mail addresses.

## Reporting
If you find personal data or unsafe content, open an issue with the label `privacy` (do not quote the data) or contact
the maintainers. Removal from git history will be done with `git filter-repo`.
