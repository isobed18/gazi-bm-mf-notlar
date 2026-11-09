# Weekly maintenance: deterministic pre step -> agy (Gemini) agent -> deterministic post step.
# Scheduled by tools/install-weekly-task.ps1; can also be run by hand:  powershell -File tools\weekly.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$day = Get-Date -Format "yyyy-MM-dd"
$wdir = Join-Path $root "local\weekly\$day"
New-Item -ItemType Directory -Force $wdir | Out-Null

python -X utf8 tools\weekly.py pre *> (Join-Path $wdir "pre.log")

$prompt = "Run the weekly maintenance of this repository: read AGENTS.md and .agents/skills/weekly-maintenance/SKILL.md, then work through local/weekly/$day/todo.md completely. Write local/weekly/$day/report.md at the end. Do not commit."
agy --model gemini-3.8-flash-high --dangerously-skip-permissions -p $prompt *> (Join-Path $wdir "agent.log")

python -X utf8 tools\weekly.py post *> (Join-Path $wdir "post.log")
