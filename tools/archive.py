#!/usr/bin/env python3
"""
archive.py - the single CLI that every agent (and human) uses to work on this archive.

Agents must NOT move files into courses/ or general/ by hand. Use this tool so that every
file gets a scan, a normalized name, a sidecar .meta.yaml and a log entry.

Commands (run `python -X utf8 tools/archive.py <cmd> -h` for options):
  init-courses        create courses/<CODE>/course.yaml for every course in catalog/curriculum.yaml
  intake              copy raw files into inbox/<batch>/ with hashes and duplicate detection
  scan                safety + privacy scan of one file (json report)
  place               scan, normalize, move a file into courses/<CODE>/<kind-dir>/ with sidecar
  review-open         move an uncertain file into review/<id>/ with a review.md for the maintainer
  review-list         list review items and whether the maintainer has decided
  review-apply        execute the maintainer's decision written in review/<id>/review.md
  validate            check the whole archive (sidecars, names, duplicates, forbidden files)
  index               rebuild catalog/index.json and courses/<CODE>/README.md
  whatsapp-index      parse a WhatsApp export and rank attachments by relevance (no full reading)
  export-obsidian     copy resources into an Obsidian vault and write a resource-list note per course
  variant             list files of a download variant (full | core)
  storage-push        upload local resources to the Google Drive mirror (place does this automatically)
  storage-pull        download missing resources from Drive (--course, --variant core)
  storage-verify      compare Drive with metadata

Only stdlib + PyYAML are required. PyMuPDF (fitz), python-docx and Pillow are used when present.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required: pip install -r tools/requirements.txt")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = os.path.join(ROOT, "catalog")
COURSES = os.path.join(ROOT, "courses")
GENERAL = os.path.join(ROOT, "general")
INBOX = os.path.join(ROOT, "inbox")
REVIEW = os.path.join(ROOT, "review")
QUARANTINE = os.path.join(ROOT, "quarantine")
LOCAL = os.path.join(ROOT, "local")          # git-ignored: logs, personal layout overrides
LOG = os.path.join(LOCAL, "ingest-log.jsonl")
# Binary resources live in a Google Drive mirror with the same folder layout (docs/STORAGE.md).
REMOTE = os.environ.get("ARCHIVE_REMOTE", "gdrive-arsiv:gazi-bm-mf-notlar")


def rclone_bin():
    b = os.environ.get("RCLONE") or shutil.which("rclone")
    if not b:  # winget installs outside PATH until the shell restarts
        base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")
        if os.path.isdir(base):
            for dp, _, fs in os.walk(base):
                if "rclone.exe" in fs:
                    return os.path.join(dp, "rclone.exe")
    return b


def rclone(*args, capture=False):
    b = rclone_bin()
    if not b:
        raise RuntimeError("rclone not found (install it and configure the remote, see docs/STORAGE.md)")
    r = subprocess.run([b, *args, "--log-level", "ERROR"], capture_output=capture, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("rclone %s failed: %s" % (args[0], (r.stderr or "").strip()[:500]))
    return r.stdout if capture else ""

# ------------------------------------------------------------------ catalog helpers

def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=120)


def catalog():
    cur = load_yaml(os.path.join(CAT, "curriculum.yaml"))["courses"]
    return {c["code"]: c for c in cur}


def taxonomy():
    return load_yaml(os.path.join(CAT, "taxonomy.yaml"))


def log_event(**kw):
    os.makedirs(LOCAL, exist_ok=True)
    kw["at"] = dt.datetime.now().isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ small utils

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")


def fold(s):
    """lower-case ascii folding used for matching (keeps letters, digits, spaces)."""
    s = (s or "").translate(TR_MAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def slugify(s, maxlen=60):
    s = fold(s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen].rstrip("-") or "file"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ext_of(path):
    return os.path.splitext(path)[1].lower().lstrip(".")


def existing_hashes():
    """sha256 -> archive path, from all sidecars."""
    out = {}
    for base in (COURSES, GENERAL):
        for dp, _, fs in os.walk(base):
            for f in fs:
                if f.endswith(".meta.yaml"):
                    try:
                        m = load_yaml(os.path.join(dp, f)) or {}
                    except Exception:
                        continue
                    if m.get("sha256"):
                        out[m["sha256"]] = os.path.relpath(os.path.join(dp, m.get("file", f[:-10])), ROOT)
    return out


# ------------------------------------------------------------------ scanning

ALLOWED = {
    "document": {"pdf", "docx", "pptx", "xlsx", "odt", "odp", "ods", "txt", "md", "rtf", "csv"},
    "legacy-office": {"doc", "ppt", "xls"},                     # allowed, but always reviewed (macros possible)
    "image": {"png", "jpg", "jpeg", "webp", "heic", "gif", "bmp", "tif", "tiff"},
    "code": {"c", "h", "cpp", "hpp", "cs", "java", "py", "ipynb", "m", "sql", "hs", "pl", "asm", "s",
             "v", "vhd", "js", "ts", "html", "css", "json", "xml", "yaml", "yml", "r", "go", "rs", "sh"},
    "archive": {"zip"},                                          # contents are scanned; never auto-placed
}
BLOCKED = {"exe", "msi", "bat", "cmd", "com", "scr", "ps1", "vbs", "vbe", "jse", "wsf", "lnk", "dll", "sys",
           "jar", "apk", "app", "dmg", "iso", "img", "docm", "xlsm", "pptm", "dotm", "xlam", "hta", "reg",
           "rar", "7z", "torrent"}
MAGIC = {
    "pdf": [b"%PDF"],
    "png": [b"\x89PNG"],
    "jpg": [b"\xff\xd8\xff"], "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF8"],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],
    "docx": [b"PK\x03\x04"], "pptx": [b"PK\x03\x04"], "xlsx": [b"PK\x03\x04"],
    "odt": [b"PK\x03\x04"], "odp": [b"PK\x03\x04"], "ods": [b"PK\x03\x04"],
    "doc": [b"\xd0\xcf\x11\xe0"], "ppt": [b"\xd0\xcf\x11\xe0"], "xls": [b"\xd0\xcf\x11\xe0"],
    "webp": [b"RIFF"],
}
SOFT_MAX = 100 * 1024 * 1024
HARD_MAX = 500 * 1024 * 1024

# Privacy patterns. Names on exam/homework papers are NOT considered private in this project.
# What we look for: phone numbers, e-mail addresses, Turkish ID numbers, IBANs, chat transcripts.
RE_PHONE = re.compile(r"(?:\+?90[\s\-]?)?\(?0?5\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
RE_IBAN = re.compile(r"\bTR\d{2}[\s]?(?:\d{4}[\s]?){5}\d{2}\b")
RE_11 = re.compile(r"\b[1-9]\d{10}\b")
RE_CHATLINE = re.compile(r"^\[?\d{1,2}[./]\d{1,2}[./]\d{2,4},? \d{1,2}:\d{2}")


def valid_tckn(s):
    if len(s) != 11 or s[0] == "0" or not s.isdigit():
        return False
    d = list(map(int, s))
    if ((sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10) != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def extract_text(path, max_pages=8, max_chars=200_000):
    e = ext_of(path)
    try:
        if e in ("txt", "md", "csv") or e in ALLOWED["code"]:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return f.read(max_chars)
        if e == "pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(path)
            return "\n".join(doc[i].get_text() for i in range(min(max_pages, doc.page_count)))[:max_chars]
        if e in ("docx", "pptx", "xlsx"):
            with zipfile.ZipFile(path) as z:
                parts = [n for n in z.namelist() if n.endswith(".xml") and ("word/document" in n or "ppt/slides/slide" in n or "sharedStrings" in n)]
                txt = " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore")) for n in parts[:60])
                return txt[:max_chars]
    except Exception as ex:  # noqa: BLE001
        return "__EXTRACT_ERROR__ %s" % ex
    return ""


def mask(s):
    return s[:3] + "*" * max(0, len(s) - 5) + s[-2:] if len(s) > 5 else "***"


def privacy_scan(text):
    findings = {}
    phones = [m.group(0) for m in RE_PHONE.finditer(text)]
    emails = [m.group(0) for m in RE_EMAIL.finditer(text) if not m.group(0).lower().endswith(("gazi.edu.tr", ".edu", ".edu.tr"))]
    tckn = [m.group(0) for m in RE_11.finditer(text) if valid_tckn(m.group(0))]
    iban = [m.group(0) for m in RE_IBAN.finditer(text)]
    chat = sum(1 for line in text.splitlines()[:5000] if RE_CHATLINE.match(line))
    if phones: findings["phone"] = [mask(p) for p in phones[:5]] + (["+%d more" % (len(phones) - 5)] if len(phones) > 5 else [])
    if emails: findings["email"] = [mask(x) for x in emails[:5]]
    if tckn: findings["tc_kimlik"] = [mask(x) for x in tckn[:3]]
    if iban: findings["iban"] = [mask(x) for x in iban[:3]]
    if chat >= 5: findings["chat_transcript_lines"] = chat
    return findings


def scan_file(path):
    """Return dict(verdict=ok|review|block, reasons=[...], privacy={...}, info={...})."""
    reasons, verdict = [], "ok"
    e = ext_of(path)
    size = os.path.getsize(path)
    info = {"ext": e, "size": size}

    def bump(v, why):
        nonlocal verdict
        order = {"ok": 0, "review": 1, "block": 2}
        if order[v] > order[verdict]:
            verdict = v
        reasons.append(why)

    group = next((g for g, s in ALLOWED.items() if e in s), None)
    info["group"] = group
    if e in BLOCKED:
        bump("block", "blocked file type .%s" % e)
    elif group is None:
        bump("review", "unknown file type .%s" % e)
    if size > HARD_MAX:
        bump("block", "file larger than 500 MB")
    elif size > SOFT_MAX:
        bump("review", "file larger than 100 MB")
    if size == 0:
        bump("block", "empty file")

    with open(path, "rb") as f:
        head = f.read(4096)
    if e in MAGIC and not any(head.startswith(m) for m in MAGIC[e]):
        bump("block", "content does not match extension .%s (magic bytes)" % e)

    if e == "pdf":
        try:
            with open(path, "rb") as f:
                raw = f.read(min(size, 30 * 1024 * 1024))
            for tok in (b"/JavaScript", b"/JS ", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA"):
                if tok in raw:
                    bump("review", "pdf contains %s" % tok.decode().strip())
        except OSError:
            pass
    if e in ("docx", "pptx", "xlsx", "zip", "odt", "odp", "ods"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if any(n.lower().endswith("vbaproject.bin") for n in names):
                    bump("block", "office file contains VBA macros")
                if e == "zip":
                    bad = [n for n in names if ext_of(n) in BLOCKED]
                    if bad:
                        bump("block", "zip contains blocked files: %s" % ", ".join(bad[:5]))
                    info["zip_entries"] = len(names)
                    bump("review", "zip archives are always reviewed (extract and place contents individually)")
                for n in names:
                    if n.endswith(".rels"):
                        if b'TargetMode="External"' in z.read(n):
                            bump("review", "office file has external links")
                            break
        except zipfile.BadZipFile:
            bump("block", "corrupt zip/office container")
    if group == "legacy-office":
        bump("review", "legacy office format (.%s) may contain macros" % e)

    if group == "image":
        try:
            from PIL import Image
            with Image.open(path) as im:
                info["image_size"] = im.size
                exif = im.getexif()
                if exif and 34853 in exif:
                    info["exif_gps"] = True
                    reasons.append("image has GPS EXIF (will be stripped on place)")
        except Exception:
            pass

    text = extract_text(path) if group in ("document", "code") else ""
    info["text_chars"] = len(text)
    priv = privacy_scan(text) if text else {}
    if priv:
        bump("review", "possible personal data: %s" % ", ".join(priv))

    if shutil.which("clamscan"):
        r = subprocess.run(["clamscan", "--no-summary", path], capture_output=True, text=True)
        if r.returncode == 1:
            bump("block", "antivirus: %s" % r.stdout.strip())
        info["antivirus"] = "clamscan:%s" % ("clean" if r.returncode == 0 else "error" if r.returncode > 1 else "infected")
    else:
        info["antivirus"] = "not-run (clamscan not installed)"
    return {"verdict": verdict, "reasons": reasons, "privacy": priv, "info": info}


def strip_exif(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            data = list(im.getdata())
            clean = Image.new(im.mode, im.size)
            clean.putdata(data)
            clean.save(path)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ naming

def normalized_name(course, kind, ext, title=None, year=None, term=None, exam_type=None, week=None):
    parts = [course, kind.replace("-", "")]
    if year:
        parts.append("%s%s" % (year, "-" + term if term else ""))
    if exam_type:
        parts.append(exam_type)
    if week:
        parts.append("w%02d" % int(week))
    if title and slugify(title, 50) not in (exam_type, kind, slugify(course)):
        parts.append(slugify(title, 50))
    return "_".join(str(p) for p in parts) + "." + ext


def unique_path(path):
    if not os.path.exists(path):
        return path
    base, e = os.path.splitext(path)
    i = 2
    while os.path.exists("%s-%d%s" % (base, i, e)):
        i += 1
    return "%s-%d%s" % (base, i, e)


# ------------------------------------------------------------------ commands

def cmd_init_courses(a):
    cat = catalog()
    n = 0
    for code, c in cat.items():
        p = os.path.join(COURSES, code, "course.yaml")
        if os.path.exists(p) and not a.force:
            continue
        dump_yaml({k: c.get(k) for k in ("code", "name_tr", "name_en", "semester", "category", "curriculum", "replaced_by", "aliases") if c.get(k) is not None}, p)
        n += 1
    print("course.yaml written for %d courses" % n)


def cmd_intake(a):
    batch = a.batch or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(INBOX, batch)
    os.makedirs(os.path.join(bdir, "files"), exist_ok=True)
    known = existing_hashes()
    if os.path.isdir(INBOX):  # also files waiting in earlier inbox batches
        for b in os.listdir(INBOX):
            jl = os.path.join(INBOX, b, "intake.jsonl")
            if os.path.isfile(jl):
                for line in open(jl, encoding="utf-8"):
                    r = json.loads(line)
                    if r.get("inbox_path") and os.path.exists(os.path.join(ROOT, r["inbox_path"])):
                        known.setdefault(r["sha256"], r["inbox_path"])
    seen = {}
    rows = []
    for src in a.paths:
        srcs = [os.path.join(dp, f) for dp, _, fs in os.walk(src) for f in fs] if os.path.isdir(src) else [src]
        for s in srcs:
            h = sha256(s)
            dup = known.get(h) or seen.get(h)
            row = {"original": os.path.basename(s), "sha256": h, "size": os.path.getsize(s), "ext": ext_of(s),
                   "source": a.source, "duplicate_of": dup}
            if not dup:
                dst = unique_path(os.path.join(bdir, "files", os.path.basename(s)))
                shutil.copy2(s, dst)
                row["inbox_path"] = os.path.relpath(dst, ROOT)
                seen[h] = row["inbox_path"]
            rows.append(row)
    with open(os.path.join(bdir, "intake.jsonl"), "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    new = sum(1 for r in rows if not r["duplicate_of"])
    log_event(event="intake", batch=batch, files=len(rows), new=new, source=a.source)
    print("batch %s: %d files, %d new, %d duplicates -> %s" % (batch, len(rows), new, len(rows) - new, os.path.relpath(bdir, ROOT)))


def cmd_scan(a):
    print(json.dumps(scan_file(a.path), ensure_ascii=False, indent=2))


def intake_source(h):
    """source recorded at intake time for this content hash (so place does not need --source)."""
    if os.path.isdir(INBOX):
        for b in os.listdir(INBOX):
            jl = os.path.join(INBOX, b, "intake.jsonl")
            if os.path.isfile(jl):
                for line in open(jl, encoding="utf-8"):
                    r = json.loads(line)
                    if r.get("sha256") == h and r.get("source"):
                        return r["source"]
    return None


def build_meta(a, course, kind, dest_name, h, scan):
    src = a.source or intake_source(h) or "unknown"
    meta = {
        "file": dest_name,
        "sha256": h,
        "size": getattr(a, "_size", None),
        "course": course,
        "kind": kind,
        "title": a.title or os.path.splitext(os.path.basename(a.path))[0],
        "year": a.year,
        "term": a.term,
        "exam_type": a.exam_type,
        "week": a.week,
        "language": a.lang,
        "handwritten": bool(a.handwritten),
        "topics": [t.strip() for t in (a.topics or "").split(",") if t.strip()],
        "related": a.related,
        "source": {"type": src.split(":")[0], "ref": src.split(":", 1)[1] if ":" in src else None},
        "contributor": a.contributor,
        "added": dt.date.today().isoformat(),
        "status": "approved",
        "scan": {"verdict": scan["verdict"], "antivirus": scan["info"].get("antivirus")},
        "notes": a.notes,
    }
    return {k: v for k, v in meta.items() if v not in (None, [], "")}


def place_file(a, course, kind, general_category=None):
    tax = taxonomy()
    src = a.path
    if not os.path.isfile(src):
        sys.exit("not a file: %s" % src)
    scan = scan_file(src)
    if scan["verdict"] == "block":
        qdir = os.path.join(QUARANTINE, dt.datetime.now().strftime("%Y%m%d"))
        os.makedirs(qdir, exist_ok=True)
        shutil.move(src, unique_path(os.path.join(qdir, os.path.basename(src))))
        log_event(event="quarantine", file=os.path.basename(src), reasons=scan["reasons"])
        sys.exit("BLOCKED -> quarantine: %s" % "; ".join(scan["reasons"]))
    if scan["verdict"] == "review" and not a.force:
        sys.exit("NEEDS REVIEW (use review-open, or --force after a human approved): %s" % "; ".join(scan["reasons"]))
    h = sha256(src)
    a.source = a.source or intake_source(h)
    dup = existing_hashes().get(h)
    if dup:
        sys.exit("DUPLICATE of %s (not placed)" % dup)
    e = ext_of(src)
    if general_category:
        if general_category not in tax["general_categories"]:
            sys.exit("unknown general category %s" % general_category)
        ddir = os.path.join(GENERAL, general_category)
        name = "%s.%s" % (slugify(a.title or os.path.splitext(os.path.basename(src))[0]), e)
        course_field = None
    else:
        if course not in catalog():
            sys.exit("unknown course %s (add it to catalog/curriculum.yaml first, via review)" % course)
        if kind not in tax["kinds"]:
            sys.exit("unknown kind %s; valid: %s" % (kind, ", ".join(tax["kinds"])))
        ddir = os.path.join(COURSES, course, tax["kinds"][kind]["dir"])
        name = normalized_name(course, kind, e, a.title, a.year, a.term, a.exam_type, a.week)
        course_field = course
    os.makedirs(ddir, exist_ok=True)
    dest = unique_path(os.path.join(ddir, name))
    (shutil.copy2 if a.copy else shutil.move)(src, dest)
    if scan["info"].get("exif_gps"):
        strip_exif(dest)
        h = sha256(dest)
    a._size = os.path.getsize(dest)
    meta = build_meta(a, course_field, kind if not general_category else "general:" + general_category, os.path.basename(dest), h, scan)
    dump_yaml(meta, dest + ".meta.yaml")
    log_event(event="place", file=os.path.relpath(dest, ROOT), sha256=h, confidence=a.confidence, source=a.source)
    print("placed -> %s" % os.path.relpath(dest, ROOT))
    if not getattr(a, "no_push", False):
        try:
            push_files([os.path.relpath(dest, ROOT)])
            print("uploaded to %s" % REMOTE)
        except RuntimeError as ex:
            print("WARNING: not uploaded (%s). Run `archive.py storage-push` later." % ex)
    return dest


# ------------------------------------------------------------------ Drive storage

def resource_entries():
    """(relative path with forward slashes, meta) for every resource described by a sidecar."""
    for dp, f in iter_resources():
        m = load_yaml(os.path.join(dp, f)) or {}
        yield os.path.relpath(os.path.join(dp, m.get("file", "")), ROOT).replace("\\", "/"), m


def _files_from(paths):
    os.makedirs(LOCAL, exist_ok=True)
    lst = os.path.join(LOCAL, "rclone-files.txt")
    with open(lst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(p.replace("\\", "/") for p in paths) + "\n")
    return lst


def push_files(rel_paths):
    if rel_paths:
        rclone("copy", ROOT, REMOTE, "--files-from", _files_from(rel_paths))


def cmd_storage_push(a):
    present = [p for p, m in resource_entries() if os.path.isfile(os.path.join(ROOT, p))]
    push_files(present)
    print("storage-push: %d local resources synced to %s (existing files are skipped by rclone)" % (len(present), REMOTE))


def cmd_storage_pull(a):
    excl = set(taxonomy()["variants"][a.variant]["exclude_kinds"])
    want = [p for p, m in resource_entries()
            if m.get("kind") not in excl and (not a.course or m.get("course") == a.course)
            and not os.path.isfile(os.path.join(ROOT, p))]
    if want:
        rclone("copy", REMOTE, ROOT, "--files-from", _files_from(want))
    print("storage-pull: %d files downloaded (variant=%s%s)" % (len(want), a.variant, ", course=" + a.course if a.course else ""))


def cmd_storage_verify(a):
    out = rclone("lsf", REMOTE, "-R", "--files-only", "--format", "ps", "--separator", "\t", capture=True)
    remote = {}
    for line in out.splitlines():
        if "\t" in line:
            p, s = line.rsplit("\t", 1)
            remote[p] = int(s)
    entries = dict(resource_entries())
    missing_remote = [p for p in entries if p not in remote]
    size_mismatch = [p for p, m in entries.items() if p in remote and m.get("size") and m["size"] != remote[p]]
    extra_remote = [p for p in remote if p not in entries and not p.endswith((".md", ".yaml"))]
    missing_local = [p for p in entries if not os.path.isfile(os.path.join(ROOT, p))]
    for title, lst in (("missing on Drive", missing_remote), ("size differs", size_mismatch),
                       ("on Drive but not in metadata", extra_remote)):
        for p in lst[:50]:
            print("%-28s %s" % (title, p))
    print("storage-verify: %d resources, %d on Drive, missing on Drive %d, size mismatch %d, untracked on Drive %d, not downloaded locally %d"
          % (len(entries), len(remote), len(missing_remote), len(size_mismatch), len(extra_remote), len(missing_local)))
    sys.exit(1 if missing_remote or size_mismatch else 0)


def cmd_place(a):
    if a.general:
        place_file(a, None, None, a.general)
    else:
        place_file(a, a.course, a.kind)


def next_review_id():
    os.makedirs(REVIEW, exist_ok=True)
    today = dt.date.today().strftime("%Y%m%d")
    n = 1 + sum(1 for d in os.listdir(REVIEW) if d.startswith("R-" + today))
    return "R-%s-%03d" % (today, n)


def cmd_review_open(a):
    src = a.path
    rid = next_review_id()
    rdir = os.path.join(REVIEW, rid)
    os.makedirs(rdir)
    scan = scan_file(src)
    dest = os.path.join(rdir, os.path.basename(src))
    shutil.move(src, dest)
    q = "\n".join("- %s" % x for x in (a.question or [])) or "- (none)"
    fm = {"id": rid, "status": "open", "created": dt.datetime.now().isoformat(timespec="seconds"),
          "file": os.path.basename(src), "source": a.source or "unknown",
          "proposal": {"course": a.course, "kind": a.kind, "general": a.general, "title": a.title,
                       "confidence": a.confidence or "low"},
          "scan_verdict": scan["verdict"]}
    front = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    body = """---
{front}---
# Review {rid}

**File:** `{fname}` ({size} bytes, .{ext}) · **Source:** {source}

## Why this needs a human
{reason}

## Scan
{scan_reasons}

## Agent proposal
- Course: {pc} · Kind: {pk} · General category: {pg}
- Title: {pt}
- Confidence: {conf}

## Questions for the maintainer
{q}

## Decision (maintainer fills this in; then run `review-apply {rid}`)
<!--
decision options:
  approve                       -> place as proposed
  place COURSE KIND [title...]  -> place into a course, e.g. `place BM218 exam 2023 Vize`
  general CATEGORY [title...]   -> place under general/<category>/
  reject                        -> delete (not useful / private / duplicate)
  quarantine                    -> keep aside, unsafe
-->
decision:
comment:
""".format(front=front, rid=rid, fname=os.path.basename(src),
           source=a.source or "unknown", pc=a.course or "-", pk=a.kind or "-", pg=a.general or "-",
           pt=a.title or "-", conf=a.confidence or "low", verdict=scan["verdict"], size=os.path.getsize(dest),
           ext=ext_of(dest), reason=a.reason or "(not given)",
           scan_reasons="\n".join("- %s" % r for r in scan["reasons"]) or "- clean", q=q)
    with open(os.path.join(rdir, "review.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    log_event(event="review-open", id=rid, file=os.path.basename(src), reason=a.reason)
    print("review item %s -> %s" % (rid, os.path.relpath(rdir, ROOT)))


def read_review(rid):
    p = os.path.join(REVIEW, rid, "review.md")
    txt = open(p, encoding="utf-8").read()
    fm = yaml.safe_load(txt.split("---", 2)[1])
    m = re.search(r"^decision:[ \t]*(.*)$", txt, re.M)
    c = re.search(r"^comment:[ \t]*(.*)$", txt, re.M)
    return p, txt, fm, (m.group(1).strip() if m else ""), (c.group(1).strip() if c else "")


def cmd_review_list(a):
    if not os.path.isdir(REVIEW):
        print("no review items")
        return
    for rid in sorted(d for d in os.listdir(REVIEW) if d.startswith("R-")):
        try:
            _, _, fm, dec, com = read_review(rid)
        except Exception as ex:  # noqa: BLE001
            print("%s  <unreadable: %s>" % (rid, ex))
            continue
        state = fm.get("status")
        if state == "open" and dec:
            state = "DECIDED"
        print("%s  %-8s  %-40s  decision=%s  comment=%s" % (rid, state, fm.get("file", "")[:40], dec or "-", com[:60] or "-"))


def cmd_review_apply(a):
    p, txt, fm, dec, com = read_review(a.id)
    if not dec:
        sys.exit("no decision written in %s" % p)
    rdir = os.path.dirname(p)
    f = os.path.join(rdir, fm["file"])
    words = dec.split()
    act = words[0].lower()

    class NS:  # reuse place_file's argument interface
        pass
    ns = NS()
    prop = fm.get("proposal") or {}
    ns.path, ns.copy, ns.force, ns.confidence = f, False, True, "human"
    ns.title = prop.get("title") if prop.get("title") not in (None, "-") else None
    for k in ("year", "term", "exam_type", "week", "lang", "topics", "related", "contributor", "notes", "handwritten"):
        setattr(ns, k, None)
    ns.source = fm.get("source")
    ns.notes = com or None
    if act == "approve":
        if prop.get("general") not in (None, "-"):
            place_file(ns, None, None, prop["general"])
        else:
            place_file(ns, prop.get("course"), prop.get("kind"))
    elif act == "place":
        ns.title = " ".join(words[3:]) or ns.title
        place_file(ns, words[1].upper(), words[2])
    elif act == "general":
        ns.title = " ".join(words[2:]) or ns.title
        place_file(ns, None, None, words[1])
    elif act == "reject":
        os.remove(f)
    elif act == "quarantine":
        os.makedirs(QUARANTINE, exist_ok=True)
        shutil.move(f, unique_path(os.path.join(QUARANTINE, os.path.basename(f))))
    else:
        sys.exit("unknown decision: %s" % dec)
    txt = txt.replace("status: open", "status: closed (%s)" % act, 1)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    done = os.path.join(REVIEW, "_closed")
    os.makedirs(done, exist_ok=True)
    shutil.move(rdir, os.path.join(done, a.id))
    log_event(event="review-apply", id=a.id, decision=dec, comment=com)
    print("%s: %s done" % (a.id, act))


FORBIDDEN_NAME = re.compile(r"[\[\]#^|\\:*?\"<>]")


def iter_resources():
    for base in (COURSES, GENERAL):
        for dp, _, fs in os.walk(base):
            for f in fs:
                if f.endswith(".meta.yaml"):
                    yield dp, f


def cmd_validate(a):
    tax = taxonomy()
    cat = catalog()
    errors, warnings = [], []
    hashes = {}
    for dp, f in iter_resources():
        mp = os.path.join(dp, f)
        rel = os.path.relpath(mp, ROOT)
        try:
            m = load_yaml(mp) or {}
        except Exception as ex:  # noqa: BLE001
            errors.append("%s: invalid yaml (%s)" % (rel, ex))
            continue
        target = os.path.join(dp, m.get("file", ""))
        if not os.path.isfile(target):
            # binaries live on Drive; a missing local copy is normal (run storage-pull to download)
            (errors if a.require_files else warnings).append("%s: file not present locally (%s)" % (rel, m.get("file")))
        for k in ("file", "sha256", "kind", "added", "status"):
            if k not in m:
                errors.append("%s: missing field %s" % (rel, k))
        if m.get("course") and m["course"] not in cat:
            errors.append("%s: unknown course %s" % (rel, m["course"]))
        k = str(m.get("kind", ""))
        if not k.startswith("general:") and k not in tax["kinds"]:
            errors.append("%s: unknown kind %s" % (rel, k))
        if m.get("sha256") in hashes:
            errors.append("%s: duplicate content of %s" % (rel, hashes[m["sha256"]]))
        hashes[m.get("sha256")] = rel
        if a.deep and os.path.isfile(target) and sha256(target) != m.get("sha256"):
            errors.append("%s: sha256 mismatch" % rel)
    for base in (COURSES, GENERAL):
        for dp, _, fs in os.walk(base):
            for f in fs:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, ROOT)
                if f.endswith(".meta.yaml") or f in ("course.yaml", "README.md", ".gitkeep"):
                    continue
                if not os.path.exists(p + ".meta.yaml"):
                    errors.append("%s: no sidecar .meta.yaml (files must be added with archive.py place)" % rel)
                if FORBIDDEN_NAME.search(f):
                    errors.append("%s: forbidden character in file name" % rel)
                if ext_of(f) in BLOCKED:
                    errors.append("%s: blocked file type" % rel)
    for code in os.listdir(COURSES) if os.path.isdir(COURSES) else []:
        if code not in cat:
            warnings.append("courses/%s is not in catalog/curriculum.yaml" % code)
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print("validate: %d errors, %d warnings" % (len(errors), len(warnings)))
    sys.exit(1 if errors else 0)


def cmd_index(a):
    tax = taxonomy()
    cat = catalog()
    items = []
    for dp, f in iter_resources():
        m = load_yaml(os.path.join(dp, f)) or {}
        m["path"] = os.path.relpath(os.path.join(dp, m.get("file", "")), ROOT).replace("\\", "/")
        items.append(m)
    items.sort(key=lambda m: m["path"])
    with open(os.path.join(CAT, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"generated": dt.datetime.now().isoformat(timespec="seconds"), "count": len(items), "resources": items},
                  fh, ensure_ascii=False, indent=1, default=str)
    by_course = {}
    for m in items:
        by_course.setdefault(m.get("course"), []).append(m)
    for code, c in cat.items():
        cdir = os.path.join(COURSES, code)
        if not os.path.isdir(cdir):
            continue
        rows = by_course.get(code, [])
        lines = ["<!-- generated by tools/archive.py index; do not edit -->",
                 "# %s – %s" % (code, c["name_tr"]), "",
                 "*%s* · %s · curriculum semester: %s" % (c["name_en"], c["category"], c.get("semester") or "elective"), ""]
        if not rows:
            lines.append("No resources yet. Contributions welcome — see CONTRIBUTING.md.")
        for kind, spec in tax["kinds"].items():
            sel = [m for m in rows if m.get("kind") == kind]
            if not sel:
                continue
            lines += ["", "## %s%s" % (kind, " (optional layer)" if spec.get("optional") else ""), "",
                      "| File | Title | Year/term | Type |", "|---|---|---|---|"]
            for m in sel:
                yt = "%s %s" % (m.get("year") or "", m.get("term") or "")
                lines.append("| [%s](%s) | %s | %s | %s |" % (m["file"], spec["dir"] + "/" + m["file"], m.get("title", ""),
                                                              yt.strip(), m.get("exam_type") or ""))
        with open(os.path.join(cdir, "README.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines) + "\n")
    print("index: %d resources" % len(items))


# ------------------------------------------------------------------ WhatsApp export triage

WA_IOS = re.compile(r"^‎?\[(\d{1,2}[./]\d{1,2}[./]\d{2,4}),? (\d{1,2}:\d{2}(?::\d{2})?)\] ([^:]+): (.*)$")
WA_ANDROID = re.compile(r"^(\d{1,2}[./]\d{1,2}[./]\d{2,4}),? (\d{1,2}:\d{2}) - ([^:]+): (.*)$")
WA_ATTACH = re.compile(r"<(?:attached|ekli|eklendi)[:\s]+([^>]+)>|([\w\-. ]+\.\w{2,5}) \((?:file attached|dosya ekli|dosya eklendi)\)", re.I)
EXAM_WORDS = ["vize", "final", "butunleme", "but ", "cikmis", "soru", "sinav", "quiz", "odev", "homework", "lab",
              "slayt", "slide", "ders notu", "notlar", "cevap", "cozum", "midterm", "exam", "proje", "kitap", "pdf",
              "konular", "hoca", "sunum"]


def cmd_whatsapp_index(a):
    src = a.export
    tmp = None
    if src.lower().endswith(".zip"):
        tmp = os.path.join(LOCAL, "wa-tmp", slugify(os.path.basename(src)))
        os.makedirs(tmp, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        src = tmp
    chat_files = [os.path.join(dp, f) for dp, _, fs in os.walk(src) for f in fs if f.lower().endswith(".txt") and ("chat" in f.lower() or "sohbet" in f.lower() or "whatsapp" in f.lower())]
    all_files = {f: os.path.join(dp, f) for dp, _, fs in os.walk(src) for f in fs}
    cat = catalog()
    alias = [(code, fold(x)) for code, c in cat.items() for x in c.get("aliases", []) + [code.lower()]]
    msgs = []
    for cf in chat_files:
        with open(cf, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.rstrip("\n")
                m = WA_IOS.match(line) or WA_ANDROID.match(line)
                if m:
                    msgs.append({"date": m.group(1), "time": m.group(2), "sender": m.group(3), "text": m.group(4)})
                elif msgs:
                    msgs[-1]["text"] += " " + line
    senders = {}
    rows = []
    referenced = set()
    for i, m in enumerate(msgs):
        am = WA_ATTACH.search(m["text"])
        if not am:
            continue
        fname = (am.group(1) or am.group(2)).strip()
        referenced.add(fname)
        # "own" context = the attachment message, its file name, and adjacent messages by the SAME sender
        # (captions are usually sent right before/after). "wide" context = +-2 messages, weighted less,
        # because neighbouring messages in a busy group are often about something else.
        own = [m["text"]] + [x["text"] for x in (msgs[i - 1] if i else None, msgs[i + 1] if i + 1 < len(msgs) else None)
                              if x and x["sender"] == m["sender"]]
        wide = [x["text"] for x in msgs[max(0, i - 2): i + 3]]

        def norm(t):
            return fold(re.sub(r"[_\-.()]+", " ", t))
        f_own, f_wide = norm(" ".join(own) + " " + fname), norm(" ".join(wide))

        def courses_in(t):
            return {code for code, al in alias if al and re.search(r"\b%s\b" % re.escape(al), t)}
        c_own, c_wide = courses_in(f_own), courses_in(f_wide)
        w_own = {w for w in EXAM_WORDS if w in f_own}
        w_wide = {w for w in EXAM_WORDS if w in f_wide} - w_own
        courses = sorted(c_own | c_wide)
        e = ext_of(fname)
        base = 3 if e in ALLOWED["document"] | ALLOWED["legacy-office"] else 1 if e in ALLOWED["image"] else 0
        score = base + 3 * len(c_own) + 1 * len(c_wide - c_own) + len(w_own) + 0.5 * len(w_wide)
        words = sorted(w_own) + ["~" + w for w in sorted(w_wide)]
        ctx = RE_PHONE.sub("[tel]", RE_EMAIL.sub("[mail]", " | ".join(wide)))
        sid = senders.setdefault(m["sender"], "P%03d" % (len(senders) + 1))
        rows.append({"score": score, "date": m["date"], "time": m["time"], "sender": sid, "file": fname, "ext": e,
                     "exists": fname in all_files, "courses": " ".join(courses), "keywords": " ".join(words),
                     "context": ctx[:240]})
    for f in all_files:
        if f not in referenced and not f.lower().endswith(".txt"):
            e = ext_of(f)
            rows.append({"score": 3 if e in ALLOWED["document"] else 0, "date": "", "time": "", "sender": "", "file": f,
                         "ext": e, "exists": True, "courses": "", "keywords": "", "context": "(not referenced in chat)"})
    rows.sort(key=lambda r: (-r["score"], r["date"]))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ["score"])
        w.writeheader()
        w.writerows(rows)
    by_ext = {}
    for r in rows:
        by_ext[r["ext"]] = by_ext.get(r["ext"], 0) + 1
    print("messages: %d, attachments: %d, senders (pseudonymized): %d" % (len(msgs), len(rows), len(senders)))
    print("by type: %s" % ", ".join("%s=%d" % kv for kv in sorted(by_ext.items(), key=lambda kv: -kv[1])))
    print("score>=6 (likely relevant): %d, score<=1 (likely irrelevant): %d" % (sum(r["score"] >= 6 for r in rows), sum(r["score"] <= 1 for r in rows)))
    print("written: %s  (files extracted under %s)" % (a.out, os.path.relpath(src, ROOT) if tmp else src))


# ------------------------------------------------------------------ Obsidian export

def find_vault_course_dir(vault, code, c):
    root = os.path.join(vault, "Dersler")
    if os.path.isdir(root):
        for dp, ds, _ in os.walk(root):
            for d in ds:
                if d.upper().startswith(code + " ") or d.upper().startswith(code + "-"):
                    return os.path.join(dp, d)
    sem = c.get("semester")
    sem_dir = "%d. Sinif %s" % ((sem + 1) // 2, "Guz" if sem % 2 else "Bahar") if sem else "Secmeli Dersler"
    return os.path.join(root, sem_dir, "%s - %s" % (code, c["name_tr"]))


def cmd_export_obsidian(a):
    tax = taxonomy()
    cat = catalog()
    excl = set(tax["variants"][a.variant]["exclude_kinds"])
    items = []
    for dp, f in iter_resources():
        m = load_yaml(os.path.join(dp, f)) or {}
        if m.get("course") and m.get("kind") not in excl:
            items.append((dp, m))
    copied = 0
    by_course = {}
    for dp, m in items:
        by_course.setdefault(m["course"], []).append((dp, m))
    for code, lst in sorted(by_course.items()):
        c = cat[code]
        cdir = find_vault_course_dir(a.vault, code, c)
        kdir = os.path.join(cdir, "Arsiv")
        lines = ["---", "tags: [%s, arsiv]" % code.lower(), "---",
                 "# %s Arşiv Kaynakları" % code,
                 "Bu not `gazi-bm-mf-notlar` deposundan otomatik üretildi; elle düzenleme (bir sonraki export üzerine yazar).",
                 "Ders: [[%s]]" % os.path.basename(cdir), ""]
        for kind, spec in tax["kinds"].items():
            sel = [(dp, m) for dp, m in lst if m["kind"] == kind]
            if not sel:
                continue
            lines += ["## %s" % kind, ""]
            for dp, m in sel:
                dst = os.path.join(kdir, spec["dir"], m["file"])
                if not os.path.isfile(os.path.join(dp, m["file"])):
                    print("  skip (not downloaded, run storage-pull --course %s): %s" % (code, m["file"]))
                    continue
                if not os.path.exists(dst) and not a.dry_run:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(os.path.join(dp, m["file"]), dst)
                    copied += 1
                extra = " · ".join(str(x) for x in (m.get("year"), m.get("term"), m.get("exam_type")) if x)
                lines.append("- [[%s]] — %s%s" % (m["file"], m.get("title", ""), (" (%s)" % extra) if extra else ""))
            lines.append("")
        if not a.dry_run:
            os.makedirs(cdir, exist_ok=True)
            with open(os.path.join(cdir, "%s Arsiv Kaynaklari.md" % code), "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(lines))
        print("%s -> %s (%d resources)" % (code, cdir, len(lst)))
    print("copied %d new files%s" % (copied, " (dry run)" if a.dry_run else ""))


def cmd_variant(a):
    excl = set(taxonomy()["variants"][a.name]["exclude_kinds"])
    for dp, f in iter_resources():
        m = load_yaml(os.path.join(dp, f)) or {}
        if m.get("kind") not in excl:
            print(os.path.relpath(os.path.join(dp, m["file"]), ROOT).replace("\\", "/"))


# ------------------------------------------------------------------ CLI

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("init-courses"); s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_init_courses)

    s = sp.add_parser("intake"); s.add_argument("paths", nargs="+"); s.add_argument("--source", required=True,
        help="e.g. whatsapp:<group-slug>, drive:<folder>, upload:<github-user>, instructor"); s.add_argument("--batch")
    s.set_defaults(fn=cmd_intake)

    s = sp.add_parser("scan"); s.add_argument("path"); s.set_defaults(fn=cmd_scan)

    def place_args(s):
        s.add_argument("path")
        s.add_argument("--title"); s.add_argument("--year", type=int); s.add_argument("--term", choices=["fall", "spring", "summer"])
        s.add_argument("--exam-type", dest="exam_type"); s.add_argument("--week", type=int); s.add_argument("--lang", choices=["tr", "en", "mixed"])
        s.add_argument("--topics", help="comma separated topic names"); s.add_argument("--related", help="path of a related resource (e.g. exam of a solution)")
        s.add_argument("--handwritten", action="store_true"); s.add_argument("--source"); s.add_argument("--contributor")
        s.add_argument("--notes"); s.add_argument("--confidence", choices=["high", "medium", "low", "human"], default="high")
        s.add_argument("--copy", action="store_true", help="copy instead of move"); s.add_argument("--force", action="store_true",
                       help="place even if scan says review (ONLY after a human approved)")
        s.add_argument("--no-push", dest="no_push", action="store_true", help="do not upload to the Drive mirror now")

    s = sp.add_parser("place"); place_args(s); s.add_argument("--course"); s.add_argument("--kind"); s.add_argument("--general")
    s.set_defaults(fn=cmd_place)

    s = sp.add_parser("review-open"); s.add_argument("path"); s.add_argument("--reason", required=True)
    s.add_argument("--course"); s.add_argument("--kind"); s.add_argument("--general"); s.add_argument("--title")
    s.add_argument("--confidence", default="low"); s.add_argument("--source"); s.add_argument("--question", action="append")
    s.set_defaults(fn=cmd_review_open)

    s = sp.add_parser("review-list"); s.set_defaults(fn=cmd_review_list)
    s = sp.add_parser("review-apply"); s.add_argument("id"); s.set_defaults(fn=cmd_review_apply)
    s = sp.add_parser("validate"); s.add_argument("--deep", action="store_true", help="re-hash every local file")
    s.add_argument("--require-files", dest="require_files", action="store_true", help="error if a resource is not downloaded")
    s.set_defaults(fn=cmd_validate)
    s = sp.add_parser("storage-push"); s.set_defaults(fn=cmd_storage_push)
    s = sp.add_parser("storage-pull"); s.add_argument("--course"); s.add_argument("--variant", default="full", choices=["full", "core"])
    s.set_defaults(fn=cmd_storage_pull)
    s = sp.add_parser("storage-verify"); s.set_defaults(fn=cmd_storage_verify)
    s = sp.add_parser("index"); s.set_defaults(fn=cmd_index)
    s = sp.add_parser("whatsapp-index"); s.add_argument("export", help="WhatsApp export folder or .zip"); s.add_argument("--out", required=True)
    s.set_defaults(fn=cmd_whatsapp_index)
    s = sp.add_parser("export-obsidian"); s.add_argument("--vault", required=True); s.add_argument("--variant", default="full", choices=["full", "core"])
    s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_export_obsidian)
    s = sp.add_parser("variant"); s.add_argument("name", choices=["full", "core"]); s.set_defaults(fn=cmd_variant)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
