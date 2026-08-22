[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$settingsPath = Join-Path $projectRoot "config\swing_walk_forward_campaign.json"
$runnerPath = Join-Path $projectRoot "scripts\run_swing_walk_forward_campaign.cmd"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

foreach ($requiredPath in @($settingsPath, $runnerPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Erforderliche Datei fehlt: $requiredPath"
    }
}

$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskName = [string]$settings.task_name
$startTime = [string]$settings.start_time
$repeatMinutes = [int]$settings.repeat_minutes
$durationHours = [int]$settings.duration_hours
if ($startTime -notmatch '^([01]\d|2[0-3]):[0-5]\d$' -or $repeatMinutes -lt 5 -or $durationHours -lt 1 -or $durationHours -gt 24) {
    throw "Ungültiger Kampagnenzeitplan."
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/d /c `"$runnerPath`"" `
    -WorkingDirectory $projectRoot
$startClock = [datetime]::ParseExact($startTime, "HH:mm", [Globalization.CultureInfo]::InvariantCulture)
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $startClock
# Windows limits the number of CalendarTrigger nodes. Attach one supported
# repetition pattern instead of expanding a five-minute day into 133 triggers.
$repetitionTemplate = New-ScheduledTaskTrigger `
    -Once `
    -At $startClock `
    -RepetitionInterval (New-TimeSpan -Minutes $repeatMinutes) `
    -RepetitionDuration (New-TimeSpan -Hours $durationHours)
$dailyTrigger.Repetition = $repetitionTemplate.Repetition
$dailyTrigger.Repetition.StopAtDurationEnd = $false
$triggers = @($dailyTrigger)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $triggers `
    -Principal $principal `
    -Settings $taskSettings `
    -Description "Rotierende historische Swing-Forschung in Shards; keine Orders und keine automatische Regeländerung."

if (-not $WhatIf) {
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
}

[pscustomobject]@{
    TaskName = $taskName
    StartTime = $startTime
    RepeatMinutes = $repeatMinutes
    DurationHours = $durationHours
    TriggerCount = $triggers.Count
    TriggerMode = "DailyWithRepetition"
    WorkingDirectory = $projectRoot
    Runner = $runnerPath
    WakeToRun = $true
    ExecutionTimeLimit = "Unlimited"
    AutomaticRuleChange = $false
    Mode = $(if ($WhatIf) { "Prüfung ohne Registrierung" } else { "Registriert" })
}
