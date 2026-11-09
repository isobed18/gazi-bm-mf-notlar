# Registers the weekly maintenance as a Windows scheduled task (Sunday 21:00).
# StartWhenAvailable: if the PC was off at that time, it runs as soon as it is on again.
param([string]$Day = "Sunday", [string]$At = "21:00")
$root = Split-Path -Parent $PSScriptRoot
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$root\tools\weekly.ps1`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 6) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "gazi-bm-mf-notlar weekly" -Action $action -Trigger $trigger -Settings $settings -Description "Weekly archive maintenance (issues, drop folders, scan, verify, Obsidian export, commit)" -Force
