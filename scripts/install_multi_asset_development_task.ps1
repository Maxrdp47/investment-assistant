[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$contractPath = Join-Path $projectRoot "config\multi_asset_discovery_development_v5.json"
$runnerPath = Join-Path $projectRoot "scripts\run_multi_asset_development.cmd"
$runnerScriptPath = Join-Path $projectRoot "scripts\run_multi_asset_development.py"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

foreach ($requiredPath in @($contractPath, $runnerPath, $runnerScriptPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Erforderliche Datei fehlt: $requiredPath"
    }
}

$contract = Get-Content -LiteralPath $contractPath -Raw -Encoding UTF8 | ConvertFrom-Json
$execution = $contract.development_execution
$taskName = [string]$execution.scheduler_task_name
$repeatMinutes = [int]$execution.scheduler_repeat_minutes
$logonType = [string]$execution.scheduler_logon_type
if ($repeatMinutes -lt 5) {
    throw "Der Scheduler-Abstand darf nicht unter fünf Minuten liegen."
}
if ($logonType -ne "Interactive") {
    throw "Unerwarteter Scheduler-Logon-Typ: $logonType"
}

$matching = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
    $_.TaskName -eq $taskName
})
if ($matching.Count -gt 1) {
    throw "Mehr als eine kanonische Development-Aufgabe gefunden."
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/d /c `"$runnerPath`"" `
    -WorkingDirectory $projectRoot
$startClock = [datetime]::Today
$dailyTrigger = New-ScheduledTaskTrigger -Daily -At $startClock
$repetitionTemplate = New-ScheduledTaskTrigger `
    -Once `
    -At $startClock `
    -RepetitionInterval (New-TimeSpan -Minutes $repeatMinutes) `
    -RepetitionDuration (New-TimeSpan -Hours 24)
$dailyTrigger.Repetition = $repetitionTemplate.Repetition
$dailyTrigger.Repetition.StopAtDurationEnd = $false
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount ([int]$execution.scheduler_restart_count) `
    -RestartInterval (New-TimeSpan -Minutes ([int]$execution.scheduler_restart_interval_minutes)) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
$task = New-ScheduledTask `
    -Action $action `
    -Trigger @($dailyTrigger) `
    -Principal $principal `
    -Settings $settings `
    -Description "Persistenter Multi-Asset Discovery v1 Development-Research-Run; keine Validation, Trades oder Orders."

if (-not $WhatIf) {
    & $pythonPath $runnerScriptPath --prepare-run | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Das finale Readiness-Gate hat die Run-Vorbereitung abgelehnt."
    }
    Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
}

[pscustomobject]@{
    TaskName = $taskName
    ExistingMatchingTasks = $matching.Count
    RepeatMinutes = $repeatMinutes
    WorkingDirectory = $projectRoot
    Runner = $runnerPath
    LogonType = "Interactive"
    StartWhenAvailable = $true
    WakeToRun = $true
    MultipleInstances = "IgnoreNew"
    ExecutionTimeLimit = "Unlimited"
    ValidationAllowed = $false
    HoldoutAllowed = $false
    BrokerAllowed = $false
    Mode = $(if ($WhatIf) { "Prüfung ohne Registrierung" } else { "Registriert" })
}
