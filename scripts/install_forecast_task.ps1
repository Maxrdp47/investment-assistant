[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$settingsPath = Join-Path $projectRoot "config\forecast_settings.json"
$runnerPath = Join-Path $projectRoot "scripts\run_evening_pipeline.cmd"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $settingsPath)) {
    throw "Konfiguration fehlt: $settingsPath"
}
if (-not (Test-Path -LiteralPath $runnerPath)) {
    throw "Hintergrundskript fehlt: $runnerPath"
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Projekt-Python fehlt: $pythonPath"
}

$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskName = [string]$settings.task_name
$runTime = [string]$settings.local_run_time
if ($runTime -notmatch '^([01]\d|2[0-3]):[0-5]\d$') {
    throw "Ungültige lokale Uhrzeit in forecast_settings.json: $runTime"
}

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/d /c `"$runnerPath`"" `
    -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At $runTime
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
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 8)
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $taskSettings `
    -Description "Abendkette: Prognosen, danach Amerika/Global-Swing-Scan, danach Krypto; keine Orderausführung."

if ($WhatIf) {
    [pscustomobject]@{
        TaskName = $taskName
        LocalRunTime = $runTime
        User = "$env:USERDOMAIN\$env:USERNAME"
        Runner = $runnerPath
        WorkingDirectory = $projectRoot
        WakeToRun = $true
        RestartCount = 3
        RestartIntervalMinutes = 15
        MultipleInstances = "IgnoreNew"
        Mode = "Prüfung ohne Registrierung"
    }
    exit 0
}

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, TaskPath
