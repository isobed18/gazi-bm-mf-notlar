"""
Exam information from group chats, done so that coverage is provable.

1. chunk:    split _chat.txt into numbered chunks (~250 lines, cut at day boundaries). Senders become P001…,
             phone numbers / e-mails are masked, attachments become [ek: <file>]. Every line keeps its line number.
2. agents:   read every chunk and write one JSONL file per chunk into findings/ (skill chat-exam-intel).
             A chunk without findings still gets a file with {"chunk": N, "none": true}.
3. coverage: lists chunks that have no findings file yet.
4. merge:    all findings of all chats -> one note per course
             courses/<CODE>/announcements/<CODE>_announcement_sohbetten-sinav-bilgileri.md (placed/updated with sidecar),
             older per-chat announcement files of that course are marked deprecated.
"""
import datetime as dt
import glob
import json
import os
import re

LINE = re.compile(r"^‎?\[?(\d{1,2})[./](\d{1,2})[./](\d{2,4}),? (\d{1,2}:\d{2})(?::\d{2})?\]? ?-? ?([^:]{1,60}?): (.*)$")
ATTACH = re.compile(r"<(?:attached|ekli|eklendi)[:\s]+([^>]+)>|([\w\-. ()]+\.\w{2,5}) \((?:file attached|dosya ekli|dosya eklendi)\)", re.I)
PHONE = re.compile(r"(?:\+?90[\s\-]?)?\(?0?5\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TYPES = ["asked-in-exam", "exam-topics", "exam-format", "instructor-tip", "solution-hint", "resource-pointer", "grade-distribution"]
TYPE_TR = {"asked-in-exam": "Sınavda çıkan", "exam-topics": "Sınav konuları", "exam-format": "Sınav formatı",
           "instructor-tip": "Hoca / ders ipucu", "solution-hint": "Çözüm ipucu", "resource-pointer": "Paylaşılan kaynak",
           "grade-distribution": "Not dağılımı"}
EXAM_TR = {"midterm": "Vize", "final": "Final", "makeup": "Bütünleme", "quiz": "Quiz", "resit": "Tek ders"}


def chat_dir(local, slug):
    return os.path.join(local, "chat", slug)


def chunk(export, slug, local, size=250):
    path = export if export.endswith(".txt") else os.path.join(export, "_chat.txt")
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    senders, out, cur, cur_day, start = {}, [], [], None, 1
    for i, raw in enumerate(lines, 1):
        m = LINE.match(raw)
        text = raw
        day = cur_day
        if m:
            d, mo, y, hm, who, msg = m.groups()
            y = int(y) + (2000 if len(y) == 2 else 0)
            day = "%02d.%02d.%d" % (int(d), int(mo), y)
            sid = senders.setdefault(who.strip(), "P%03d" % (len(senders) + 1))
            am = ATTACH.search(msg)
            if am:
                msg = ATTACH.sub("[ek: %s]" % (am.group(1) or am.group(2)).strip(), msg)
            text = "%s %s %s: %s" % (day, hm, sid, msg)
        text = PHONE.sub("[tel]", EMAIL.sub("[mail]", text))
        if len(cur) >= size and day != cur_day:
            out.append((start, i - 1, cur))
            cur, start = [], i
        cur.append("%d| %s" % (i, text))
        cur_day = day
    if cur:
        out.append((start, len(lines), cur))
    base = chat_dir(local, slug)
    os.makedirs(os.path.join(base, "chunks"), exist_ok=True)
    os.makedirs(os.path.join(base, "findings"), exist_ok=True)
    manifest = []
    for n, (a, b, rows) in enumerate(out, 1):
        name = "%03d.txt" % n
        with open(os.path.join(base, "chunks", name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(rows) + "\n")
        manifest.append({"chunk": n, "file": name, "lines": [a, b], "first": rows[0][:40], "last": rows[-1][:40]})
    json.dump({"slug": slug, "source": path, "total_lines": len(lines), "chunks": manifest},
              open(os.path.join(base, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(lines), len(out), base


def coverage(local, slug=None):
    res = {}
    for mf in glob.glob(os.path.join(local, "chat", slug or "*", "manifest.json")):
        man = json.load(open(mf, encoding="utf-8"))
        base = os.path.dirname(mf)
        missing = [c["chunk"] for c in man["chunks"] if not os.path.isfile(os.path.join(base, "findings", "%03d.jsonl" % c["chunk"]))]
        res[man["slug"]] = (len(man["chunks"]), missing)
    return res


def academic(date):
    d, mo, y = map(int, date.split("."))
    return (y, "fall") if mo >= 9 else ((y - 1, "fall") if mo == 1 else (y - 1, "spring"))


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def load_findings(local, catalog):
    found, unknown, bad = {}, [], 0
    for fp in glob.glob(os.path.join(local, "chat", "*", "findings", "*.jsonl")):
        slug = fp.split(os.sep)[-3]
        for line in open(fp, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if r.get("none") or not r.get("summary"):
                continue
            r["slug"] = slug
            code = (r.get("course") or "").upper().replace(" ", "")
            if code not in catalog:
                unknown.append(r)
                continue
            found.setdefault(code, []).append(r)
    return found, unknown, bad


def render(code, name, rows):
    groups = {}
    seen = set()
    for r in rows:
        key = norm(r["summary"])[:120]
        if key in seen:
            continue
        seen.add(key)
        try:
            y, t = academic(r["date"])
            label = "%d-%d %s" % (y, y + 1, "Güz" if t == "fall" else "Bahar")
            sort = (y, 0 if t == "spring" else 1)
        except (KeyError, ValueError, AttributeError):
            label, sort = "Tarihi belirsiz", (0, 0)
        groups.setdefault((sort, label), []).append(r)
    out = ["# %s – Sohbetlerden derlenen sınav bilgileri" % code, "",
           "%s · Kaynak: sınıf grup sohbetleri · doğrulanmadı (öğrenci aktarımı) · %d bilgi" % (name, len(seen)),
           "Derleme: %s" % dt.date.today().isoformat(), ""]
    for (sort, label), rs in sorted(groups.items(), key=lambda kv: kv[0][0], reverse=True):
        out += ["## %s" % label, ""]
        for r in sorted(rs, key=lambda r: (TYPES.index(r.get("type")) if r.get("type") in TYPES else 99, r.get("date", ""))):
            tag = TYPE_TR.get(r.get("type"), "Bilgi")
            ex = EXAM_TR.get(r.get("exam") or "", "")
            out.append("- **%s%s** (%s): %s" % (tag, (" · " + ex) if ex else "", r.get("date", "?"), r["summary"].strip()))
        out.append("")
    return "\n".join(out)
