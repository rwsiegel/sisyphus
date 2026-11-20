# Daily collection. Reads public job boards and pushes the day's changes to jobhunt-data.
# No scoring, no resumes, no config.json. Scoring stays local and is run by hand.
# Scheduled by scripts/register_daily_task.ps1.
param([string]$Python = "python")

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$data = Join-Path (Split-Path -Parent $repo) "jobhunt-data"
$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("collect_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
Start-Transcript -Path $log -Append | Out-Null

try {
    git -C $repo pull --ff-only
    git -C $data pull --ff-only

    # Each step runs even if the other fails, so a broken investor search does not lose the postings.
    & $Python (Join-Path $repo "src\collect.py")
    $collectExit = $LASTEXITCODE
    & $Python (Join-Path $repo "src\vc_search.py")
    $searchExit = $LASTEXITCODE
    & $Python (Join-Path $repo "src\a16z_feed.py")
    $feedExit = $LASTEXITCODE

    # Only the data folder is ever staged. Unchanged boards write no file, so the commit holds just the day's changes.
    git -C $data add data
    git -C $data diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git -C $data commit -m ("Daily collection {0}" -f (Get-Date -Format "yyyy-MM-dd"))
        git -C $data push
    } else {
        Write-Output "Nothing new to commit."
    }

    if ($collectExit -ne 0 -or $searchExit -ne 0 -or $feedExit -ne 0) {
        throw "collect.py exit $collectExit, vc_search.py exit $searchExit, a16z_feed.py exit $feedExit. See $log"
    }
}
finally {
    Stop-Transcript | Out-Null
}
