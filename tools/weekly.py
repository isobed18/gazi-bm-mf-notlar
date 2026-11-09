#!/usr/bin/env python3
"""Deterministic parts of the weekly maintenance (see .agents/skills/weekly-maintenance/SKILL.md).

    python -X utf8 tools/weekly.py pre    # pull, review-sync, collect drop folders, list issues -> local/weekly/<date>/todo.md
    python -X utf8 tools/weekly.py post   # chat-merge, index, validate, audit, export-obsidian, commit + push
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import archive  # noqa: E402

DAY = dt.date.today().isoformat()
WDIR = os.path.join(archive.LOCAL, "weekly", DAY)


def sh(*cmd, check=False):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if check and r.returncode:
        raise RuntimeError("%s failed: %s" % (" ".join(cmd[:3]), (r.stderr or r.stdout)[-800:]))
    return r


def tool(*args):
    return sh(sys.executable, "-X", "utf8", os.path.join("tools", "archive.py"), *args)


def pre():
    os.makedirs(WDIR, exist_ok=True)
    todo = ["# Haftalık bakım — %s" % DAY, ""]
    sh("git", "pull", "--ff-only")
    r = tool("review-sync")
    todo += ["## Review issues", "```", (r.stdout or r.stderr).strip()[-3000:] or "-", "```", ""]
    try:
        inbox = json.load(open(os.path.join(archive.LOCAL, "review-inbox.json"), encoding="utf-8"))
    except (OSError, ValueError):
        inbox = []
    if inbox:
        todo += ["**%d plain-language comment(s) to interpret** — see local/review-inbox.json" % len(inbox), ""]

    # drop folders (trusted) -> one inbox batch
    batch = "weekly-%s" % DAY
    stage = os.path.join(archive.LOCAL, "weekly", DAY, "drop")
    os.makedirs(stage, exist_ok=True)
    n = 0
    for d in archive.CONFIG.get("drop_dirs") or []:
        if os.path.isdir(d):
            for f in os.listdir(d):
                p = os.path.join(d, f)
                if os.path.isfile(p):
                    shutil.move(p, os.path.join(stage, f))
                    n += 1
    dd = archive.CONFIG.get("drive_drop")
    if dd:
        try:
            archive.rclone("move", "%s/%s" % (archive.REMOTE, dd), stage)
        except RuntimeError as ex:
            todo.append("Drive drop folder not read: %s" % ex)

    # Google Form submissions ("file request"): uploads land in the form owner's Drive folder; respondents cannot
    # delete or see them. Files are copied to a separate stage, then moved to _islendi/ inside that folder.
    form = archive.CONFIG.get("form") or {}
    if form.get("uploads"):
        fstage = os.path.join(archive.LOCAL, "weekly", DAY, "form")
        os.makedirs(fstage, exist_ok=True)
        try:
            listing = archive.rclone("lsf", form["uploads"], "--files-only", "--max-depth", "1", capture=True)
            names = [x for x in listing.splitlines() if x]
            for nm in names:
                archive.rclone("copyto", "%s/%s" % (form["uploads"], nm), os.path.join(fstage, nm))
                archive.rclone("moveto", "%s/%s" % (form["uploads"], nm), "%s/_islendi/%s/%s" % (form["uploads"], DAY, nm))
            if form.get("responses"):  # the form's response sheet, exported as CSV (course / kind / year per upload)
                archive.rclone("copyto", form["responses"], os.path.join(fstage, "_yanitlar.csv"), "--drive-export-formats", "csv")
            if names:
                tool("intake", fstage, "--source", "form:%s" % DAY, "--batch", "form-%s" % DAY)
                todo += ["## Form submissions: %d (inbox/form-%s)" % (len(names), DAY),
                         "Metadata the submitters typed is in local/weekly/%s/form/_yanitlar.csv (match by file name; "
                         "treat it as a hint, verify against the file). Untrusted source: place with --status unverified, "
                         "anything doubtful -> review-open." % DAY, ""] + ["- %s" % x for x in names] + [""]
            else:
                todo += ["## Form submissions: none", ""]
        except RuntimeError as ex:
            todo.append("Form uploads not read: %s" % ex)
    files = [f for f in os.listdir(stage) if os.path.isfile(os.path.join(stage, f))]
    chats = [f for f in files if f.lower().endswith(".zip") and "whatsapp" in f.lower()]
    normal = [f for f in files if f not in chats]
    if normal:
        tool("intake", stage, "--source", "drop:%s" % DAY, "--batch", batch)
        todo += ["## New files: %d (inbox/%s)" % (len(normal), batch), ""] + ["- %s" % f for f in normal] + [""]
    if chats:
        todo += ["## New chat exports (process with chat-chunk / chat-exam-intel / whatsapp-triage)", ""] + \
                ["- local/weekly/%s/drop/%s" % (DAY, f) for f in chats] + [""]
    if not files:
        todo += ["## New files: none", ""]

    r = sh("gh", "issue", "list", "--label", "submission", "--state", "open", "--json", "number,title,createdAt")
    subs = json.loads(r.stdout or "[]") if r.returncode == 0 else []
    todo += ["## Submission issues: %d" % len(subs), ""] + ["- #%d %s" % (i["number"], i["title"]) for i in subs] + [""]
    unv = sum(1 for _, m in archive.resource_entries() if m.get("status") == "unverified")
    todo += ["## Unverified resources in the archive: %d (verify up to ~60 this week)" % unv, ""]
    open(os.path.join(WDIR, "todo.md"), "w", encoding="utf-8", newline="\n").write("\n".join(todo) + "\n")
    print("\n".join(todo))


def post():
    os.makedirs(WDIR, exist_ok=True)
    rep = []
    for args in (["chat-merge"], ["index"], ["validate"], ["audit"]):
        r = tool(*args)
        rep.append("$ archive.py %s -> %d\n%s" % (" ".join(args), r.returncode, (r.stdout or r.stderr).strip()[-1500:]))
        if args[0] in ("validate", "audit") and r.returncode:
            rep.append("STOP: %s failed; nothing committed." % args[0])
            open(os.path.join(WDIR, "post.md"), "w", encoding="utf-8").write("\n\n".join(rep))
            print("\n\n".join(rep))
            sys.exit(1)
    if archive.CONFIG.get("vault"):
        r = tool("export-obsidian")
        rep.append("$ export-obsidian -> %d\n%s" % (r.returncode, (r.stdout or r.stderr).strip()[-800:]))
    if archive.CONFIG.get("personal_exam_sync") and archive.CONFIG.get("personal_vault"):
        r = tool("export-exams", "--skip", *(archive.CONFIG.get("personal_skip") or []))
        rep.append("$ export-exams (personal vault) -> %d\n%s" % (r.returncode, (r.stdout or r.stderr).strip()[-600:]))
    r = tool("storage-verify")
    rep.append("$ storage-verify -> %d\n%s" % (r.returncode, r.stdout.strip()[-600:]))
    sh("git", "add", "catalog", "courses", "general")
    st = sh("git", "diff", "--cached", "--stat").stdout.strip()
    if st:
        msg = "weekly maintenance %s\n\n%s" % (DAY, st.splitlines()[-1])
        r = sh("git", "commit", "-m", msg)
        rep.append("commit: %s" % (r.stdout or r.stderr).strip()[-300:])
        r = sh("git", "push")
        rep.append("push: %d %s" % (r.returncode, (r.stderr or r.stdout).strip()[-300:]))
    else:
        rep.append("nothing to commit")
    open(os.path.join(WDIR, "post.md"), "w", encoding="utf-8").write("\n\n".join(rep))
    print("\n\n".join(rep))


if __name__ == "__main__":
    {"pre": pre, "post": post}[sys.argv[1]]()
