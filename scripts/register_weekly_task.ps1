# Registers the weekly collection as a Windows scheduled task for the current user.
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\register_weekly_task.ps1
# Remove:    Unregister-ScheduledTask -TaskName jobhunt-weekly-collect -Confirm:$false
param(
    [string]$Day = "Monday",
    [string]$Time = "07:00"
)

$script = Join-Path $PSScriptRoot "weekly_collect.ps1"
$python = (Get-Command python).Source

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Python `"$python`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $Time
# StartWhenAvailable: if the PC was off at the scheduled time, run when it next starts.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName "jobhunt-weekly-collect" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Collect public job-board data into jobhunt-data (no scoring)" -Force | Out-Null
Get-ScheduledTask -TaskName "jobhunt-weekly-collect" | Get-ScheduledTaskInfo | Format-List TaskName, NextRunTime
