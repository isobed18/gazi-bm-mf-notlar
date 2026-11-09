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
  export-obsidian     generate the semester-based study vault (Dersler/<dönem>/<ders>/: Çıkmış Sorular, Ders Notları, Slaytlar)
  chat-chunk          split a chat into numbered chunks for reading agents (chat-coverage, chat-merge follow)
  audit               privacy/secret audit of everything that would be shared
  variant             list files of a download variant (full | core)
  storage-push        upload local resources to the Google Drive mirror (place does this automatically)
  storage-pull        download missing resources from Drive (--course, --variant core)
  storage-verify      compare Drive with metadata

Only stdlib + PyYAML are required. PyMuPDF (fitz), python-docx and Pillow are used when present.
"""
import argparse
import csv
import glob
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
sys.path.insert(0, os.path.join(ROOT, "tools"))
CAT = os.path.join(ROOT, "catalog")
COURSES = os.path.join(ROOT, "courses")
GENERAL = os.path.join(ROOT, "general")
INBOX = os.path.join(ROOT, "inbox")
REVIEW = os.path.join(ROOT, "review")
QUARANTINE = os.path.join(ROOT, "quarantine")
LOCAL = os.path.join(ROOT, "local")          # git-ignored: logs, personal layout overrides
LOG = os.path.join(LOCAL, "ingest-log.jsonl")
# Machine-specific settings (vault path, drop folders, remote) live in local/config.yaml (git-ignored);
# see config.example.yaml. Nothing personal is hard-coded in the repository.
def _local_config():
    p = os.path.join(LOCAL, "config.yaml")
    try:
        with open(p, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except OSError:
        return {}


CONFIG = _local_config()
# Binary resources live in a Google Drive mirror with the same folder layout (docs/STORAGE.md).
REMOTE = os.environ.get("ARCHIVE_REMOTE") or CONFIG.get("remote") or "gdrive-arsiv:gazi-bm-mf-notlar"
# Never shared: review staging, retired files, private material (sibling folder of the shared mirror)
REMOTE_PRIVATE = CONFIG.get("remote_private") or REMOTE.rstrip("/") + "-ozel"


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
    if re.search(r"downloaded by .{0,60}@|studocu", text, re.I): findings["download_watermark"] = "Studocu-style 'Downloaded by <name> (<e-mail>)'"
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

    av = defender_bin()
    if shutil.which("clamscan"):
        r = subprocess.run(["clamscan", "--no-summary", path], capture_output=True, text=True)
        if r.returncode == 1:
            bump("block", "antivirus: %s" % r.stdout.strip())
        info["antivirus"] = "clamscan:%s" % ("clean" if r.returncode == 0 else "error" if r.returncode > 1 else "infected")
    elif av:
        # Windows Defender custom scan of one file; exit code 2 = threat found
        r = subprocess.run([av, "-Scan", "-ScanType", "3", "-File", os.path.abspath(path), "-DisableRemediation"],
                           capture_output=True, text=True, errors="ignore")
        if r.returncode == 2:
            bump("block", "antivirus (Windows Defender): threat found")
        info["antivirus"] = "defender:%s" % ("clean" if r.returncode == 0 else "infected" if r.returncode == 2 else "error-%d" % r.returncode)
    else:
        info["antivirus"] = "not-run (no clamscan / Windows Defender)"
    return {"verdict": verdict, "reasons": reasons, "privacy": priv, "info": info}


def defender_bin():
    cands = glob.glob(r"C:\ProgramData\Microsoft\Windows Defender\Platform\*\MpCmdRun.exe")
    cands.append(r"C:\Program Files\Windows Defender\MpCmdRun.exe")
    return next((c for c in sorted(cands, reverse=True) if os.path.isfile(c)), None) if os.name == "nt" else None


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
        "status": getattr(a, "status", None) or "approved",
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
    os.makedirs(os.path.join(LOCAL, "tmp"), exist_ok=True)
    # unique per call: several agents may upload at the same time
    lst = os.path.join(LOCAL, "tmp", "rclone-files-%d-%s.txt" % (os.getpid(), hashlib.sha1(os.urandom(8)).hexdigest()[:6]))
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
    # unique even when several agents open items in parallel
    os.makedirs(REVIEW, exist_ok=True)
    return "R-%s-%s" % (dt.datetime.now().strftime("%Y%m%d-%H%M%S"), hashlib.sha1(os.urandom(8)).hexdigest()[:4])


def cmd_review_open(a):
    src = a.path
    rid = next_review_id()
    rdir = os.path.join(REVIEW, rid)
    os.makedirs(rdir)
    scan = scan_file(src)
    source = a.source or intake_source(sha256(src)) or "unknown"
    dest = os.path.join(rdir, os.path.basename(src))
    shutil.move(src, dest)
    q = "\n".join("- %s" % x for x in (a.question or [])) or "- (none)"
    fm = {"id": rid, "status": "open", "created": dt.datetime.now().isoformat(timespec="seconds"),
          "file": os.path.basename(src), "source": source,
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


# ------------------------------------------------------------------ review via GitHub issues

def gh(*args, input_text=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", input=input_text, cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError("gh %s failed: %s" % (" ".join(args[:2]), r.stderr.strip()[:400]))
    return r.stdout


def set_front(path, **kv):
    txt = open(path, encoding="utf-8").read()
    _, fm_txt, body = txt.split("---", 2)
    fm = yaml.safe_load(fm_txt)
    fm.update(kv)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + "---" + body)


def open_review_ids():
    if not os.path.isdir(REVIEW):
        return []
    return sorted(d for d in os.listdir(REVIEW) if d.startswith("R-") and os.path.isfile(os.path.join(REVIEW, d, "review.md")))


def cmd_review_publish(a):
    """Upload review files to Drive (_review/<id>/) and open ONE GitHub issue listing the items."""
    ids = a.ids
    if not ids:
        unpublished = [i for i in open_review_ids() if not read_review(i)[2].get("issue")]
        want = a.source or (slugify(a.batch, 200) if a.batch else None)

        def mine(rid):  # only items that came from this agent's source (several agents run in parallel)
            src = str(read_review(rid)[2].get("source") or "")
            ref = src.split(":", 1)[-1]
            return src == want or (ref and ref != "unknown" and ref in (want or ""))
        ids = [i for i in unpublished if mine(i)] if want else unpublished
    if not ids:
        print("nothing to publish (no unpublished items for source %s)" % (a.source or a.batch))
        return
    rows, details = [], []
    for n, rid in enumerate(ids, 1):
        p, txt, fm, _, _ = read_review(rid)
        set_front(p, item=n)
        f = os.path.join(REVIEW, rid, fm["file"])
        try:
            rclone("copy", f, "%s/_review/%s" % (REMOTE_PRIVATE, rid))
            where = "Drive (özel): `%s/_review/%s/%s`" % (REMOTE_PRIVATE.split(":", 1)[-1], rid, fm["file"])
        except RuntimeError as ex:
            where = "local only (%s)" % ex
        prop = fm.get("proposal") or {}
        prop_s = ("general/%s" % prop["general"]) if prop.get("general") else "%s / %s" % (prop.get("course") or "?", prop.get("kind") or "?")
        reason = re.search(r"## Why this needs a human\n(.*?)\n\n## ", txt, re.S)
        qs = re.search(r"## Questions for the maintainer\n(.*?)\n\n## ", txt, re.S)
        rows.append("| %d | `%s` | %s | %s | %s |" % (n, rid, fm["file"][:50], prop_s, prop.get("confidence") or "low"))
        details.append("### %d. %s\n- Öneri: **%s** · başlık: %s\n- Neden: %s\n- Sorular:\n%s\n- Dosya: %s\n- id: `%s`\n"
                       % (n, fm["file"], prop_s, prop.get("title") or "-", (reason.group(1).strip() if reason else "-"),
                          (qs.group(1).strip() if qs else "- (none)"), where, rid))
    body = ("Agent'ların emin olamadığı %d öncelikli dosya.\n\n"
            "**Öncelik:** çıkmış sorular ve çözümleri; ders notları; hocanın resmi slaytları. Bu sırayı koruyun.\n"
            "Müfredat, sınav/ders takvimi, ödev takvimi veya tekil ödev ayrıntısı, akademik takvim, staj, kariyer ve\n"
            "genel belgeler kapsam dışıdır. Dersle açıkça eşleşen kitaplar eklenebilir; kitap için soru açmayın.\n"
            "Ders adı açıksa eksik/önemsiz ders kodu için sormayın. Yalnızca öncelikli bir kaynağın güvenli yerleşimini\n"
            "engelleyen gerçek belirsizlik veya gizlilik sorunu varsa soru sorun.\n\n"
            "**Nasıl cevaplanır:** Düz Türkçe yorum yazman yeterli, maddelere numarayla değin. Örnek:\n"
            "> 1 ve 2 BM218'in 2023 güz vizesi. 3'ü sil. 4'ü BM371 resmi slayt olarak ekle.\n\n"
            "Bir agent yorumunu okur, uygular ve ne anladığını cevap olarak yazar; emin olamadığını sana tekrar sorar.\n"
            "(İstersen kısa komut da olur: `3: reject`, `1: place BM218 exam 2023 Vize`, `all: approve`.)\n\n"
            "| # | id | dosya | öneri | güven |\n|---|---|---|---|---|\n%s\n\n%s") % (len(ids), "\n".join(rows), "\n".join(details))
    title = a.title or "[review] %s — %d dosya" % (a.batch or dt.date.today().isoformat(), len(ids))
    url = gh("issue", "create", "--title", title, "--body-file", "-", "--label", "review", input_text=body).strip()
    num = int(url.rstrip("/").rsplit("/", 1)[1])
    for rid in ids:
        set_front(os.path.join(REVIEW, rid, "review.md"), issue=num)
    log_event(event="review-publish", issue=num, ids=ids)
    print("issue #%d: %s (%d items)" % (num, url, len(ids)))


DECISION_LINE = re.compile(r"^\s*/?(R-[\w-]+|all|#?\d{1,3})\s*[:.)]\s*(approve|place|general|reject|quarantine)\b(.*)$", re.I | re.M)
SYNC_STATE = os.path.join(LOCAL, "review-sync-state.json")
AGENT_MARK = "<!-- archive-agent -->"   # comments posted by agents (they use the owner's gh login) carry this mark


def _sync_state():
    try:
        return json.load(open(SYNC_STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {"handled_comments": []}


def _save_sync_state(st):
    os.makedirs(LOCAL, exist_ok=True)
    json.dump(st, open(SYNC_STATE, "w", encoding="utf-8"), indent=1)


def write_decision(rid, dec, com=""):
    p = os.path.join(REVIEW, rid, "review.md")
    txt = open(p, encoding="utf-8").read()
    txt = re.sub(r"^decision:.*$", "decision: %s" % dec, txt, count=1, flags=re.M)
    txt = re.sub(r"^comment:.*$", "comment: %s" % com, txt, count=1, flags=re.M)
    open(p, "w", encoding="utf-8", newline="\n").write(txt)


def apply_one(rid):
    class A:
        pass
    ns = A()
    ns.id = rid
    cmd_review_apply(ns)
    try:
        rclone("purge", "%s/_review/%s" % (REMOTE_PRIVATE, rid))
    except RuntimeError:
        pass


def issue_items():
    """{issue number: {item number: review id}} for open review items."""
    out = {}
    for rid in open_review_ids():
        fm = read_review(rid)[2]
        if fm.get("issue"):
            out.setdefault(int(fm["issue"]), {})[int(fm.get("item") or 0)] = rid
    return out


def cmd_review_sync(a):
    """Apply decisions from issue comments by the owner/collaborators.
    Short commands (`3: reject`, `R-…: place BM218 exam 2023 Vize`, `all: approve`) are applied here.
    Plain-language comments are written to local/review-inbox.json for an agent to interpret
    (skill review-queue); the agent applies them with review-decide and confirms with review-ack."""
    owner = gh("repo", "view", "--json", "owner", "-q", ".owner.login").strip()
    st = _sync_state()
    inbox = []
    for num, items in sorted(issue_items().items()):
        data = json.loads(gh("issue", "view", str(num), "--json", "comments,state"))
        decisions = {}
        for c in data["comments"]:
            if c["author"]["login"] != owner and c.get("authorAssociation") not in ("OWNER", "COLLABORATOR", "MEMBER"):
                continue
            if c.get("id") in st["handled_comments"] or AGENT_MARK in c["body"]:
                continue
            found = list(DECISION_LINE.finditer(c["body"]))
            for m in found:
                key, rest = m.group(1).lstrip("#"), (m.group(2) + m.group(3)).strip()
                dec, _, com = rest.partition(" -- ")
                if key.lower() == "all":
                    for rid in items.values():
                        decisions.setdefault(rid, (dec.strip(), com.strip()))
                elif key.isdigit() and int(key) in items:
                    decisions[items[int(key)]] = (dec.strip(), com.strip())
                elif key in items.values():
                    decisions[key] = (dec.strip(), com.strip())
            if found:
                st["handled_comments"].append(c.get("id"))
            else:
                inbox.append({"issue": num, "comment_id": c.get("id"), "body": c["body"],
                              "items": {n: {"id": rid, "file": read_review(rid)[2]["file"], "proposal": read_review(rid)[2].get("proposal")}
                                        for n, rid in sorted(items.items())}})
        done = []
        for rid, (dec, com) in decisions.items():
            write_decision(rid, dec, com)
            try:
                apply_one(rid)
                done.append("`%s` → %s" % (rid, dec))
            except SystemExit as ex:
                done.append("`%s` → HATA: %s" % (rid, ex))
        if done:
            gh("issue", "comment", str(num), "--body", "Uygulandı:\n" + "\n".join("- " + d for d in done) + "\n" + AGENT_MARK)
        left = [r for r in items.values() if r not in decisions]
        if not left and data["state"] == "OPEN":
            gh("issue", "close", str(num), "--comment", "Bütün maddeler işlendi.\n" + AGENT_MARK)
        print("issue #%d: %d applied, %d waiting" % (num, len(done), len(left)))
    _save_sync_state(st)
    with open(os.path.join(LOCAL, "review-inbox.json"), "w", encoding="utf-8") as fh:
        json.dump(inbox, fh, ensure_ascii=False, indent=1)
    if inbox:
        print("%d plain-language comment(s) need interpretation -> local/review-inbox.json (see skill review-queue)" % len(inbox))
        for x in inbox:
            print("--- issue #%d comment %s:\n%s" % (x["issue"], x["comment_id"], x["body"][:1500]))


def cmd_review_decide(a):
    """Write one decision (interpreted by an agent from a plain comment) and apply it."""
    write_decision(a.id, a.decision, a.comment or "")
    apply_one(a.id)
    print("%s: %s" % (a.id, a.decision))


def cmd_review_ack(a):
    """Mark a plain-language comment as handled and post the agent's reply (what it understood / did / asks)."""
    st = _sync_state()
    if a.comment_id not in st["handled_comments"]:
        st["handled_comments"].append(a.comment_id)
    _save_sync_state(st)
    gh("issue", "comment", str(a.issue), "--body", a.reply + "\n\n" + AGENT_MARK)
    items = issue_items().get(a.issue, {})
    if not items:
        gh("issue", "close", str(a.issue), "--comment", "Bütün maddeler işlendi.\n" + AGENT_MARK)
    print("acknowledged comment %s on #%d (%d items left)" % (a.comment_id, a.issue, len(items)))


# ------------------------------------------------------------------ metadata edits

EDITABLE = {"title", "year", "term", "exam_type", "week", "language", "topics", "related", "status", "notes", "handwritten"}


def cmd_retire(a):
    """Remove a resource from the archive (e.g. it contains personal data): local file + sidecar are deleted,
    the Drive copy is moved to the private sibling folder (<remote>-ozel/_retired/), never left in the shared mirror."""
    for path in a.paths:
        src = path[:-10] if path.endswith(".meta.yaml") else path
        rel = os.path.relpath(src, ROOT).replace("\\", "/")
        try:
            rclone("moveto", "%s/%s" % (REMOTE, rel), "%s/_retired/%s" % (REMOTE_PRIVATE, rel))
        except RuntimeError as ex:
            print("WARNING: Drive copy not moved (%s)" % str(ex)[:120])
        for p in (src, src + ".meta.yaml"):
            if os.path.exists(p):
                os.remove(p)
        log_event(event="retire", file=rel, reason=a.reason)
        print("retired %s (%s)" % (rel, a.reason))


def cmd_relocate(a):
    """Move a placed resource to another course and/or kind (fixes misclassification); keeps metadata, renames,
    moves the Drive copy too. Use `meta-set` for title/year/term/status changes."""
    src = a.path[:-10] if a.path.endswith(".meta.yaml") else a.path
    mp = src + ".meta.yaml"
    if not os.path.isfile(mp):
        sys.exit("no sidecar: %s" % mp)
    m = load_yaml(mp) or {}
    tax, cat = taxonomy(), catalog()
    course = (a.course or m.get("course") or "").upper()
    kind = a.kind or m.get("kind")
    if course not in cat:
        sys.exit("unknown course %s" % course)
    if kind not in tax["kinds"]:
        sys.exit("unknown kind %s" % kind)
    e = ext_of(m["file"])
    name = normalized_name(course, kind, e, m.get("title"), m.get("year"), m.get("term"), m.get("exam_type"), m.get("week"))
    ddir = os.path.join(COURSES, course, tax["kinds"][kind]["dir"])
    os.makedirs(ddir, exist_ok=True)
    dest = unique_path(os.path.join(ddir, name))
    old_rel = os.path.relpath(src, ROOT).replace("\\", "/")
    new_rel = os.path.relpath(dest, ROOT).replace("\\", "/")
    if os.path.isfile(src):
        shutil.move(src, dest)
    try:
        rclone("moveto", "%s/%s" % (REMOTE, old_rel), "%s/%s" % (REMOTE, new_rel))
    except RuntimeError as ex:
        if os.path.isfile(dest):
            push_files([new_rel])
        else:
            print("WARNING: Drive move failed (%s)" % ex)
    m.update({"file": os.path.basename(dest), "course": course, "kind": kind})
    if a.status:
        m["status"] = a.status
    if a.notes:
        m["notes"] = a.notes
    os.remove(mp)
    dump_yaml(m, dest + ".meta.yaml")
    log_event(event="relocate", old=old_rel, new=new_rel)
    print("relocated %s -> %s" % (old_rel, new_rel))


def cmd_meta_set(a):
    path = a.path if a.path.endswith(".meta.yaml") else a.path + ".meta.yaml"
    if not os.path.isfile(path):
        sys.exit("no sidecar: %s" % path)
    m = load_yaml(path) or {}
    tax = taxonomy()
    for kv in a.set:
        k, _, v = kv.partition("=")
        if k not in EDITABLE:
            sys.exit("field %s is not editable (editable: %s); course/kind changes need a re-place" % (k, ", ".join(sorted(EDITABLE))))
        if k == "topics":
            m[k] = [t.strip() for t in v.split(",") if t.strip()]
        elif k in ("year", "week"):
            m[k] = int(v) if v else None
        elif k == "handwritten":
            m[k] = v.lower() in ("1", "true", "yes")
        else:
            m[k] = v or None
        if k == "status" and v not in tax["statuses"]:
            sys.exit("status must be one of %s" % tax["statuses"])
    dump_yaml({k: v for k, v in m.items() if v not in (None, [], "")}, path)
    log_event(event="meta-set", file=os.path.relpath(path, ROOT), changes=a.set)
    print("updated %s" % os.path.relpath(path, ROOT))


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


# ------------------------------------------------------------------ Obsidian export (semester layout)

def cmd_export_obsidian(a):
    import obsidian_export
    vault = a.vault or CONFIG.get("vault")
    if not vault:
        sys.exit("no vault path: pass --vault or set `vault:` in local/config.yaml")
    obsidian_export.export(sys.modules[__name__], vault, a.variant, set(a.course or []), a.dry_run)


def cmd_export_exams(a):
    """Add archive past exams to a user-maintained vault (e.g. the personal vault), after a zip backup."""
    import obsidian_export
    import zipfile as zf
    vault = a.vault or CONFIG.get("personal_vault")
    if not vault or not os.path.isdir(vault):
        sys.exit("vault not found: %s" % vault)
    if not a.dry_run and not a.no_backup:
        bdir = CONFIG.get("backup_dir") or os.path.join(os.path.dirname(ROOT), "vault-backups")
        os.makedirs(bdir, exist_ok=True)
        zpath = os.path.join(bdir, "%s-%s.zip" % (os.path.basename(vault.rstrip(os.sep + "/")), dt.datetime.now().strftime("%Y%m%d-%H%M")))
        with zf.ZipFile(zpath, "w", zf.ZIP_DEFLATED) as z:
            for dp, ds, fs in os.walk(vault):
                for f in fs:
                    p = os.path.join(dp, f)
                    z.write(p, os.path.relpath(p, vault))
        print("backup: %s (%d MB)" % (zpath, os.path.getsize(zpath) // 2 ** 20))
        olds = sorted(f for f in os.listdir(bdir) if f.startswith(os.path.basename(vault.rstrip(os.sep + "/")) + "-") and f.endswith(".zip"))
        for f in olds[:-3]:  # keep the 3 newest backups
            os.remove(os.path.join(bdir, f))
    obsidian_export.export_exams_to_vault(sys.modules[__name__], vault, a.skip if a.skip is not None else (CONFIG.get("personal_skip") or []), a.dry_run)


# ------------------------------------------------------------------ exam information from chats

def cmd_chat_chunk(a):
    import chatintel
    total, n, base = chatintel.chunk(a.export, a.slug, LOCAL, a.size)
    print("%s: %d lines -> %d chunks in %s" % (a.slug, total, n, os.path.relpath(base, ROOT)))


def cmd_chat_coverage(a):
    import chatintel
    res = chatintel.coverage(LOCAL, a.slug)
    bad = 0
    for slug, (n, missing) in sorted(res.items()):
        bad += len(missing)
        print("%-28s %3d chunks, %3d done, missing: %s" % (slug, n, n - len(missing), (",".join(map(str, missing[:40])) or "-")))
    sys.exit(1 if bad else 0)


def cmd_chat_merge(a):
    """All chat findings -> one 'sohbetten sınav bilgileri' note per course (placed/updated in the archive)."""
    import chatintel
    cat = catalog()
    found, unknown, bad = chatintel.load_findings(LOCAL, cat)
    total = 0
    for code, rows in sorted(found.items()):
        text = chatintel.render(code, cat[code]["name_tr"], rows)
        ddir = os.path.join(COURSES, code, "announcements")
        os.makedirs(ddir, exist_ok=True)
        fname = "%s_announcement_sohbetten-sinav-bilgileri.md" % code
        dest = os.path.join(ddir, fname)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
        meta = {"file": fname, "sha256": sha256(dest), "size": os.path.getsize(dest), "course": code, "kind": "announcement",
                "title": "Sohbetlerden sınav bilgileri", "language": "tr", "handwritten": False,
                "source": {"type": "whatsapp", "ref": "merged:" + ",".join(sorted({r["slug"] for r in rows}))},
                "added": dt.date.today().isoformat(), "status": "unverified",
                "scan": {"verdict": "ok", "antivirus": "generated-text"},
                "notes": "generated by archive.py chat-merge from %d findings" % len(rows)}
        dump_yaml(meta, dest + ".meta.yaml")
        total += len(rows)
        # older per-chat announcement files (one per group, written by earlier agents) are superseded:
        # their Drive copy goes to _retired/, the local file + sidecar are removed
        for f in os.listdir(ddir):
            if f.endswith(".meta.yaml") and f != fname + ".meta.yaml":
                mp = os.path.join(ddir, f)
                m = load_yaml(mp) or {}
                if "sohbetten" in slugify(m.get("title", "") + " " + m.get("file", ""), 200):
                    old = os.path.join(ddir, m.get("file", f[:-10]))
                    rel = os.path.relpath(old, ROOT).replace("\\", "/")
                    if a.no_push:
                        with open(os.path.join(LOCAL, "retire-on-drive.txt"), "a", encoding="utf-8") as fh:
                            fh.write(rel + "\n")   # moved to _retired/ on Drive later (storage-retire)
                    else:
                        try:
                            rclone("moveto", "%s/%s" % (REMOTE, rel), "%s/_retired/%s" % (REMOTE_PRIVATE, rel))
                        except RuntimeError:
                            pass
                    for p in (old, mp):
                        if os.path.exists(p):
                            os.remove(p)
        if not a.no_push:
            try:
                rclone("copyto", dest, "%s/%s" % (REMOTE, os.path.relpath(dest, ROOT).replace("\\", "/")))
            except RuntimeError as ex:
                print("WARNING: %s not uploaded (%s)" % (code, ex))
    with open(os.path.join(LOCAL, "chat", "unmatched-findings.json"), "w", encoding="utf-8") as fh:
        json.dump(unknown, fh, ensure_ascii=False, indent=1)
    print("chat-merge: %d findings into %d courses; %d findings without a catalog course (local/chat/unmatched-findings.json); %d bad lines"
          % (total, len(found), len(unknown), bad))


# ------------------------------------------------------------------ privacy / secret audit of what would be shared

AUDIT_PAT = {
    "phone": re.compile(r"(?<![0-9a-f])(?:\+?90[\s\-]?)?\(?0?5\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?![0-9a-f])"),
    "email": re.compile(r"[\w.+-]+@(?!gazi\.edu\.tr|users\.noreply\.github\.com|anthropic\.com)[\w-]+\.[\w.-]+"),
    "secret": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|\"refresh_token\"|client_secret\s*[=:]\s*\S{8,}|-----BEGIN [A-Z ]*PRIVATE KEY"),
    "user-path": re.compile(r"[A-Z]:\\+Users\\+[^\\\s`'\"]+", re.I),
    "chat-line": re.compile(r"^\[?\d{1,2}[./]\d{1,2}[./]\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?\]? ?-? ?[^:\n]{2,40}: ", re.M),
}


def cmd_audit(a):
    """Scan everything that would be shared: tracked + untracked-not-ignored text, optionally git history and issues."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
    files = [f for f in (git("ls-files") + git("ls-files", "--others", "--exclude-standard")).splitlines() if f]
    hits = []
    for f in files:
        if not f.endswith((".md", ".yaml", ".yml", ".json", ".py", ".txt", ".csv", ".toml")) or f == "catalog/index.json":
            continue
        try:
            txt = open(os.path.join(ROOT, f), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        if f.endswith(".meta.yaml"):  # hashes look like numbers; only scan human fields
            m = yaml.safe_load(txt) or {}
            txt = " ".join(str(m.get(k, "")) for k in ("title", "notes", "topics", "contributor"))
        for k, rx in AUDIT_PAT.items():
            for mm in rx.finditer(txt):
                if k == "phone" and not valid_phone_context(txt, mm):
                    continue
                hits.append((k, f, mm.group(0)[:50]))
    if a.history:
        authors = set(git("log", "--all", "--format=%an <%ae>").splitlines())
        for au in authors:
            if not re.search(r"noreply", au):
                hits.append(("author-email", "git history", au))
    untracked = [f for f in git("ls-files", "--others", "--exclude-standard").splitlines() if f and not f.startswith(("courses/", "general/", "catalog/"))]
    for f in untracked:
        hits.append(("untracked", f, "not ignored and not archive content: commit deliberately or ignore"))
    for k, f, s in hits:
        print("%-12s %-70s %s" % (k, f[:70], s))
    blocking = [h for h in hits if h[0] != "untracked"]
    print("audit: %d findings (%d blocking)" % (len(hits), len(blocking)))
    sys.exit(1 if blocking else 0)


def valid_phone_context(txt, m):
    s = re.sub(r"\D", "", m.group(0))
    return len(s) in (10, 11, 12) and not re.search(r"[0-9a-f]{20,}", txt[max(0, m.start() - 20): m.end() + 20])


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
        s.add_argument("--status", choices=["approved", "unverified", "needs-review"], default="approved",
                       help="unverified = from a messy source (WhatsApp); a later stage confirms it")

    s = sp.add_parser("place"); place_args(s); s.add_argument("--course"); s.add_argument("--kind"); s.add_argument("--general")
    s.set_defaults(fn=cmd_place)

    s = sp.add_parser("review-open"); s.add_argument("path"); s.add_argument("--reason", required=True)
    s.add_argument("--course"); s.add_argument("--kind"); s.add_argument("--general"); s.add_argument("--title")
    s.add_argument("--confidence", default="low"); s.add_argument("--source"); s.add_argument("--question", action="append")
    s.set_defaults(fn=cmd_review_open)

    s = sp.add_parser("review-list"); s.set_defaults(fn=cmd_review_list)
    s = sp.add_parser("review-publish", help="upload open review items to Drive and open one GitHub issue")
    s.add_argument("--ids", nargs="*"); s.add_argument("--title")
    s.add_argument("--batch", help="free text; items whose source slug appears in it are published (e.g. 'gazi-bm-2021 documents')")
    s.add_argument("--source", help="exact source, e.g. whatsapp:gazi-bm-2021"); s.set_defaults(fn=cmd_review_publish)
    s = sp.add_parser("review-sync", help="apply decisions written as comments on review issues"); s.set_defaults(fn=cmd_review_sync)
    s = sp.add_parser("review-decide", help="apply one decision interpreted from a plain comment")
    s.add_argument("id"); s.add_argument("decision", help='e.g. "place BM218 exam 2023 Vize", "reject", "general internship Staj rehberi"')
    s.add_argument("--comment"); s.set_defaults(fn=cmd_review_decide)
    s = sp.add_parser("review-ack", help="mark a plain comment handled and reply on the issue")
    s.add_argument("issue", type=int); s.add_argument("comment_id"); s.add_argument("--reply", required=True); s.set_defaults(fn=cmd_review_ack)
    s = sp.add_parser("retire", help="remove resources from the archive (Drive copy goes to the private folder)")
    s.add_argument("paths", nargs="+"); s.add_argument("--reason", required=True); s.set_defaults(fn=cmd_retire)
    s = sp.add_parser("relocate", help="move a placed resource to another course/kind (misclassification fix)")
    s.add_argument("path"); s.add_argument("--course"); s.add_argument("--kind")
    s.add_argument("--status", choices=["approved", "unverified", "needs-review", "deprecated"]); s.add_argument("--notes")
    s.set_defaults(fn=cmd_relocate)
    s = sp.add_parser("meta-set", help="edit editable sidecar fields: key=value ...")
    s.add_argument("path"); s.add_argument("set", nargs="+"); s.set_defaults(fn=cmd_meta_set)
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
    s = sp.add_parser("export-obsidian", help="generate the semester-based study vault (vault path from --vault or local/config.yaml)")
    s.add_argument("--vault"); s.add_argument("--variant", default="full", choices=["full", "core"])
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--course", nargs="*", help="only these course codes")
    s.set_defaults(fn=cmd_export_obsidian)
    s = sp.add_parser("export-exams", help="add archive past exams to a user-maintained vault (zip backup first)")
    s.add_argument("--vault", help="default: personal_vault from local/config.yaml"); s.add_argument("--skip", nargs="*", help='semester folders to skip (default: personal_skip from local/config.yaml)')
    s.add_argument("--dry-run", action="store_true"); s.add_argument("--no-backup", action="store_true"); s.set_defaults(fn=cmd_export_exams)
    s = sp.add_parser("chat-chunk", help="split a chat export into numbered, pseudonymized chunks for reading agents")
    s.add_argument("export", help="export folder or _chat.txt"); s.add_argument("--slug", required=True); s.add_argument("--size", type=int, default=250)
    s.set_defaults(fn=cmd_chat_chunk)
    s = sp.add_parser("chat-coverage", help="which chunks still have no findings file"); s.add_argument("--slug"); s.set_defaults(fn=cmd_chat_coverage)
    s = sp.add_parser("chat-merge", help="merge all chat findings into one exam-info note per course")
    s.add_argument("--no-push", dest="no_push", action="store_true"); s.set_defaults(fn=cmd_chat_merge)
    s = sp.add_parser("audit", help="privacy/secret audit of everything that would be shared")
    s.add_argument("--history", action="store_true", help="also check commit author e-mails"); s.set_defaults(fn=cmd_audit)
    s = sp.add_parser("variant"); s.add_argument("name", choices=["full", "core"]); s.set_defaults(fn=cmd_variant)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
