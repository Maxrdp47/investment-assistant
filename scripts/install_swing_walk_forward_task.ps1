[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$settingsPath = Join-Path $projectRoot "config\swing_walk_forward_settings.json"
$runnerPath = Join-Path $projectRoot "scripts\run_swing_walk_forward.cmd"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

foreach ($requiredPath in @($settingsPath, $runnerPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Erforderliche Datei fehlt: $requiredPath"
    }
}

$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskName = [string]$settings.task_name
$runTime = [string]$settings.local_run_time
$weeklyDay = [System.DayOfWeek]([string]$settings.weekly_day)
if ($runTime -notmatch '^([01]\d|2[0-3]):[0-5]\d$') {
    throw "Ungültige lokale Uhrzeit: $runTime"
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/d /c `"$runnerPath`"" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $weeklyDay -At $runTime
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $taskSettings `
    -Description "Lokaler historischer Swing-Walk-Forward-Forschungsbetrieb; keine Orders und keine automatische Regeländerung."

if (-not $WhatIf) {
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
}

[pscustomobject]@{
    TaskName = $taskName
    WeeklyDay = [string]$weeklyDay
    LocalRunTime = $runTime
    WorkingDirectory = $projectRoot
    Runner = $runnerPath
    WakeToRun = $true
    StartWhenAvailable = $true
    AutomaticRuleChange = $false
    Mode = $(if ($WhatIf) { "Prüfung ohne Registrierung" } else { "Registriert" })
}
