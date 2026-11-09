"""
Generate the official study vault from the archive (one-way: archive -> vault).

Layout (semester based, like a student's own vault):

    Başlangıç.md                       landing page
    Dersler/
      Dersler.md                       all semesters -> courses, with counts
      1. Sınıf Güz/
        1. Sınıf Güz.md                semester note
        BM101 - Bilgisayar Programlama I/
          BM101 - Bilgisayar Programlama I.md     course hub
          BM101 Çıkmış Sorular.md                 exams + solutions + exam info from chats
          BM101 Ders Notları.md                   lecture notes, student notes, summaries
          BM101 Slaytlar.md                       official slides
          BM101 Harf Notu Dağılımları.md          (only if any)
          Arsiv/<kind-dir>/<files>
      ...
      Seçmeli Dersler/                 electives (no fixed curriculum semester)

The semester is the course's semester in catalog/curriculum.yaml. Generated notes carry `generated: true`;
only those are rewritten or removed. User-written notes are never touched.
"""
import os
import re
import shutil

SEM_NAMES = {1: "1. Sınıf Güz", 2: "1. Sınıf Bahar", 3: "2. Sınıf Güz", 4: "2. Sınıf Bahar",
             5: "3. Sınıf Güz", 6: "3. Sınıf Bahar", 7: "4. Sınıf Güz", 8: "4. Sınıf Bahar"}
ELECTIVES = "Seçmeli Dersler"
TERM_TR = {"fall": "Güz", "spring": "Bahar", "summer": "Yaz"}
EXAM_TR = {"midterm": "Vize", "final": "Final", "makeup": "Bütünleme", "quiz": "Quiz", "resit": "Tek ders", "sample": "Örnek"}
GROUPS = [  # (id, note suffix, kinds)
    ("exams", "Çıkmış Sorular", {"exam", "exam-solution"}),
    ("notes", "Ders Notları", {"lecture-notes", "student-notes", "summary"}),
    ("slides", "Slaytlar", {"slides"}),
    ("grades", "Harf Notu Dağılımları", {"grade-distribution"}),
]
EXPORT_KINDS = set().union(*(g[2] for g in GROUPS)) | {"announcement"}
SKIP_ANNOUNCEMENT_TITLES = re.compile(r"takvim|program|staj|calendar|schedule", re.I)


def semester_of(c):
    s = c.get("semester")
    return SEM_NAMES.get(s, ELECTIVES) if s else ELECTIVES


def kind_of(m, slugify):
    if "harf-notu-dagilim" in slugify(m.get("title", ""), 120):
        return "grade-distribution"
    return m.get("kind")


def when(m):
    y, t = m.get("year"), m.get("term")
    if not y:
        return ""
    if t == "fall":
        return "%d-%d Güz" % (y, y + 1)
    if t in ("spring", "summer"):
        return "%d-%d %s" % (y, y + 1, TERM_TR[t])
    return "%d-%d" % (y, y + 1)


def label(s):
    return re.sub(r"[\[\]|#^]", " ", str(s or "")).strip()


def front(tags, extra=None):
    lines = ["---", "generated: true", "tags: [%s]" % ", ".join(tags)]
    for k, v in (extra or {}).items():
        lines.append("%s: %s" % (k, v))
    return lines + ["---"]


def is_generated(path):
    try:
        with open(path, encoding="utf-8") as fh:
            head = fh.read(300)
        return head.startswith("---") and "generated: true" in head.split("---", 2)[1]
    except (OSError, IndexError):
        return False


ASCII_SEM = {1: "1. Sinif Guz", 2: "1. Sinif Bahar", 3: "2. Sinif Guz", 4: "2. Sinif Bahar",
             5: "3. Sinif Guz", 6: "3. Sinif Bahar", 7: "4. Sinif Guz", 8: "4. Sinif Bahar"}


def export_exams_to_vault(ns, vault, skip_semester_dirs, dry_run, log=print):
    """Add archive past exams (+ solutions + merged chat exam info) to an existing, user-maintained vault.

    Never overwrites user notes: files go to <course>/Cikmis Sorular/, a generated note
    '<CODE> Arşiv Çıkmışları.md' lists them, and one link line is appended to the course's own
    '… Cikmis Sorular' note (or hub) if not present yet. Courses inside `skip_semester_dirs` are skipped."""
    import hashlib
    cat = ns.catalog()
    root = os.path.join(vault, "Dersler")
    want = {}
    for dp, f in ns.iter_resources():
        m = ns.load_yaml(os.path.join(dp, f)) or {}
        code = m.get("course")
        if not code or code not in cat or m.get("status") == "deprecated":
            continue
        k = m.get("kind")
        if k in ("exam", "exam-solution") or (k == "announcement" and "sohbetten-sinav-bilgileri" in m.get("file", "")):
            want.setdefault(code, []).append((dp, m, k))
    # existing course folders of the vault, matched by folded code prefix (TÜR101 == TUR101)
    folders = {}
    for dp, ds, _ in os.walk(root):
        for d in ds:
            head = ns.slugify(d.split(" - ")[0], 20).replace("-", "").upper()
            if head in cat and head not in folders and " - " in d:
                folders[head] = os.path.join(dp, d)

    def sha(p):
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    added = notes = skipped = 0
    for code, rows in sorted(want.items()):
        cdir = folders.get(code)
        if cdir and any(os.sep + s + os.sep in cdir + os.sep for s in skip_semester_dirs):
            skipped += 1
            continue
        if not cdir:
            sem_dir = ASCII_SEM.get(cat[code].get("semester"), "Secmeli Dersler")
            if sem_dir in skip_semester_dirs:
                skipped += 1
                continue
            cdir = os.path.join(root, sem_dir, "%s - %s" % (code, cat[code]["name_tr"]))
        edir = os.path.join(cdir, "Cikmis Sorular")
        have = set()
        if os.path.isdir(edir):
            have = {sha(os.path.join(edir, f)) for f in os.listdir(edir) if os.path.isfile(os.path.join(edir, f))}
        exams, sols, chat = [], [], []
        for dp, m, k in rows:
            src = os.path.join(dp, m["file"])
            if not os.path.isfile(src):
                log("  skip (not downloaded; storage-pull --course %s): %s" % (code, m["file"]))
                continue
            dst = os.path.join(edir, m["file"])
            if k == "announcement" or (m.get("sha256") not in have and not os.path.exists(dst)):
                if not dry_run:
                    os.makedirs(edir, exist_ok=True)
                    shutil.copy2(src, dst)
                added += k != "announcement"
            (chat if k == "announcement" else exams if k == "exam" else sols).append(m)
        if not (exams or sols or chat):
            continue
        name = "%s Arşiv Çıkmışları" % code
        body = front(["arsiv-cikmis", code.lower()]) + ["# %s — Arşivden çıkmış sorular" % code, "",
                "Bu not `gazi-bm-mf-notlar` arşivinden otomatik üretilir (her güncellemede yeniden yazılır).", ""]
        if exams:
            body += ["## Sınavlar", ""]
            for m in sorted(exams, key=lambda m: (-(m.get("year") or 0), m.get("term") or "", m.get("exam_type") or "")):
                tag = " · ".join(x for x in (when(m), EXAM_TR.get(m.get("exam_type"), "")) if x)
                body.append("- [[%s|%s]]%s" % (m["file"], label(m.get("title") or m["file"]), (" — " + tag) if tag else ""))
            body.append("")
        if sols:
            body += ["## Çözümler", ""] + ["- [[%s|%s]] %s" % (m["file"], label(m.get("title") or m["file"]), when(m)) for m in sols] + [""]
        if chat:
            body += ["## Öğrencilerden aktarılan sınav bilgileri (doğrulanmadı)", ""] + ["![[%s]]" % m["file"] for m in chat] + [""]
        target = os.path.join(cdir, name + ".md")
        if not dry_run:
            if os.path.exists(target) and not is_generated(target):
                log("  keep user note: %s" % target)
            else:
                os.makedirs(cdir, exist_ok=True)
                open(target, "w", encoding="utf-8", newline="\n").write("\n".join(body).rstrip() + "\n")
                notes += 1
            # one link line in the user's own exam note (or hub), appended once
            own = [os.path.join(cdir, f) for f in os.listdir(cdir) if f.endswith(".md") and "cikmis" in ns.slugify(f, 80)
                   and f != name + ".md" and not is_generated(os.path.join(cdir, f))]
            hub = os.path.join(cdir, os.path.basename(cdir) + ".md")
            host = own[0] if own else (hub if os.path.exists(hub) else None)
            if host:
                txt = open(host, encoding="utf-8").read()
                if "[[%s]]" % name not in txt:
                    open(host, "a", encoding="utf-8", newline="\n").write("\n\n> Arşivden gelen çıkmışlar: [[%s]]\n" % name)
    log("exams to vault: %d files added, %d notes written, %d courses skipped (%s)%s"
        % (added, notes, skipped, ", ".join(skip_semester_dirs), " (dry run)" if dry_run else ""))


def export(ns, vault, variant, only_courses, dry_run, log=print):
    """ns: archive module (catalog, taxonomy, iter_resources, load_yaml, slugify)."""
    tax, cat = ns.taxonomy(), ns.catalog()
    excl = set(tax["variants"][variant]["exclude_kinds"])
    root = os.path.join(vault, "Dersler")
    by_course = {}
    for dp, f in ns.iter_resources():
        m = ns.load_yaml(os.path.join(dp, f)) or {}
        code = m.get("course")
        if not code or code not in cat or (only_courses and code not in only_courses):
            continue
        k = kind_of(m, ns.slugify)
        if k not in EXPORT_KINDS or k in excl or m.get("status") == "deprecated":
            continue
        if k == "announcement" and (not m["file"].endswith(".md") or SKIP_ANNOUNCEMENT_TITLES.search(m.get("title", ""))):
            continue
        by_course.setdefault(code, []).append((dp, m, k))

    written, copied, moved = set(), 0, 0
    expected_files = set()

    def write(path, lines):
        written.add(os.path.normcase(os.path.abspath(path)))
        if dry_run:
            return
        if os.path.exists(path) and not is_generated(path):
            log("  keep user note (not generated): %s" % path)
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines).rstrip() + "\n")

    sem_rows = {}
    for code in sorted(by_course):
        c = cat[code]
        sem = semester_of(c)
        name = "%s - %s" % (code, c["name_tr"])
        cdir = os.path.join(root, sem, name)
        # move an existing folder of this course (old layouts) instead of copying everything again
        if os.path.isdir(root) and not os.path.isdir(cdir):
            for dp, ds, _ in os.walk(root):
                hit = next((d for d in ds if d.upper().startswith(code + " ") and os.path.join(dp, d) != cdir), None)
                if hit:
                    if not dry_run:
                        os.makedirs(os.path.dirname(cdir), exist_ok=True)
                        shutil.move(os.path.join(dp, hit), cdir)
                    moved += 1
                    break
        items = []
        for dp, m, k in by_course[code]:
            src = os.path.join(dp, m["file"])
            dst = os.path.join(cdir, "Arsiv", tax["kinds"][k]["dir"], m["file"])
            if not os.path.isfile(src):
                log("  skip (not downloaded; run storage-pull --course %s): %s" % (code, m["file"]))
                continue
            expected_files.add(os.path.normcase(os.path.abspath(dst)))
            if not dry_run and (not os.path.exists(dst) or (k == "announcement" and os.path.getsize(dst) != os.path.getsize(src))):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1
            items.append((m, k))

        counts = {}
        hub = front([code.lower(), "ders"], {"donem": '"%s"' % sem}) + [
            "# %s" % name, "", "Dönem: [[%s]] · %s" % (sem, c.get("name_en", "")), ""]
        for gid, suffix, kinds in GROUPS:
            sel = [(m, k) for m, k in items if k in kinds]
            chat = [m for m, k in items if k == "announcement"] if gid == "exams" else []
            counts[gid] = len(sel)
            if gid != "exams" and not sel:
                continue
            note = "%s %s" % (code, suffix)
            hub.append("- [[%s]] — %d %s" % (note, len(sel), "sınav/çözüm" if gid == "exams" else "kaynak"))
            body = front(["gazi-arsiv", gid, code.lower()]) + ["# %s — %s" % (code, suffix), "", "Ders: [[%s]]" % name, ""]
            if gid == "exams":
                exams = sorted([m for m, k in sel if k == "exam"], key=lambda m: (-(m.get("year") or 0), m.get("term") or "", m.get("exam_type") or ""))
                sols = [m for m, k in sel if k == "exam-solution"]
                body += ["## Sınavlar", ""] + ([] if exams else ["Arşivde bu ders için sınav kağıdı yok.", ""])
                for m in exams:
                    tag = " · ".join(x for x in (when(m), EXAM_TR.get(m.get("exam_type"), "")) if x)
                    body.append("- [[%s|%s]]%s" % (m["file"], label(m.get("title") or m["file"]), (" — " + tag) if tag else ""))
                if sols:
                    body += ["", "## Çözümler", ""]
                    for m in sols:
                        body.append("- [[%s|%s]] %s" % (m["file"], label(m.get("title") or m["file"]), when(m)))
                if chat:
                    body += ["", "## Öğrencilerden aktarılan sınav bilgileri (doğrulanmadı)", "",
                             "Grup sohbetlerinden derlendi; sınavda ne çıktığı, konular ve sınav tarzı.", ""]
                    for m in chat:
                        body.append("![[%s]]" % m["file"])
            else:
                for m, k in sorted(sel, key=lambda x: (x[1], x[0].get("week") or 0, x[0].get("title") or "")):
                    title = label(m.get("title") or m["file"])
                    extra = " · ".join(x for x in (when(m), ("Hafta %d" % m["week"]) if m.get("week") else "",
                                                   "öğrenci notu" if k == "student-notes" else "", "özet" if k == "summary" else "") if x)
                    if gid == "grades":
                        body.append("![[%s]]" % m["file"])
                        body.append("%s%s" % (title, (" — " + extra) if extra else ""))
                        body.append("")
                    else:
                        body.append("- [[%s|%s]]%s" % (m["file"], title, (" — " + extra) if extra else ""))
            write(os.path.join(cdir, note + ".md"), body)
        write(os.path.join(cdir, name + ".md"), hub)
        sem_rows.setdefault(sem, []).append((code, name, counts.get("exams", 0), counts.get("notes", 0), counts.get("slides", 0)))

    order = list(SEM_NAMES.values()) + [ELECTIVES]
    index = front(["gazi", "dersler"]) + ["# Dersler", "",
             "Dönem → ders → çıkmış sorular / ders notları / slaytlar.", ""]
    for sem in order:
        rows = sorted(sem_rows.get(sem, []))
        if not rows:
            continue
        index.append("## [[%s]]" % sem)
        snote = front(["gazi", "donem"]) + ["# %s" % sem, "", "Üst: [[Dersler]]", "",
                 "| Ders | Çıkmış | Not | Slayt |", "|---|---|---|---|"]
        for code, name, ex, no, sl in rows:
            snote.append("| [[%s]] | %d | %d | %d |" % (name, ex, no, sl))
            index.append("- [[%s]] · çıkmış %d · not %d · slayt %d" % (name, ex, no, sl))
        index.append("")
        write(os.path.join(root, sem, sem + ".md"), snote)
    write(os.path.join(root, "Dersler.md"), index)
    write(os.path.join(vault, "Başlangıç.md"), front(["gazi"]) + [
        "# Gazi BM Ders Arşivi", "", "Başlamak için: [[Dersler]]", "",
        "Her derste önce **Çıkmış Sorular**, sonra **Ders Notları** ve **Slaytlar**.",
        "Kaynaklar `gazi-bm-mf-notlar` arşivinden otomatik üretilir; bu notları elle düzenleme.", ""])

    removed = 0
    if not only_courses and not dry_run:
        for dp, ds, fs in os.walk(vault):
            if ".obsidian" in dp:
                continue
            for f in fs:
                p = os.path.join(dp, f)
                if f.endswith(".md") and os.path.normcase(os.path.abspath(p)) not in written and is_generated(p):
                    os.remove(p)
                    removed += 1
        # files under generated Arsiv/ folders that are no longer exported (relocated / deprecated resources)
        for dp, ds, fs in os.walk(root):
            if os.sep + "Arsiv" in dp + os.sep:
                for f in fs:
                    p = os.path.join(dp, f)
                    if os.path.normcase(os.path.abspath(p)) not in expected_files:
                        os.remove(p)
                        removed += 1
        for dp, ds, fs in sorted(os.walk(root, topdown=False), key=lambda x: -len(x[0])):
            if dp != root and not os.listdir(dp):
                os.rmdir(dp)
    log("export: %d courses, %d files copied, %d course folders moved, %d stale generated notes/files removed%s"
        % (len(by_course), copied, moved, removed, " (dry run)" if dry_run else ""))
