# Registers the daily collection as a Windows scheduled task for the current user.
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\register_daily_task.ps1
# Remove:    Unregister-ScheduledTask -TaskName jobhunt-daily-collect -Confirm:$false
param(
    [string]$Time = "07:00"
)

$script = Join-Path $PSScriptRoot "daily_collect.ps1"
$python = (Get-Command python).Source

# Replace the earlier weekly task if it exists.
if (Get-ScheduledTask -TaskName "jobhunt-weekly-collect" -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName "jobhunt-weekly-collect" -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -Python `"$python`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
# StartWhenAvailable: if the PC was off at the scheduled time, run when it next starts.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName "jobhunt-daily-collect" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Collect public job-board changes into jobhunt-data (no scoring)" -Force | Out-Null
Get-ScheduledTask -TaskName "jobhunt-daily-collect" | Get-ScheduledTaskInfo | Format-List TaskName, NextRunTime
