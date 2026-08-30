[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$settingsPath = Join-Path $projectRoot "config\fx_pit_collector.json"
$runnerPath = Join-Path $projectRoot "scripts\run_fx_pit_collector.cmd"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

foreach ($requiredPath in @($settingsPath, $runnerPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Erforderliche Datei fehlt: $requiredPath"
    }
}

$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$settings.mode -ne "FX_PIT_OBSERVER") {
    throw "Unsicherer Collector-Modus: $($settings.mode)"
}
foreach ($field in @("strategy_signal_allowed", "trade_decision_allowed", "paper_trade_allowed", "shadow_order_allowed", "broker_order_allowed")) {
    if ($settings.safety.$field -ne $false) {
        throw "Collector-Sicherheitsfeld ist nicht false: $field"
    }
}
$taskName = [string]$settings.task_name
$runTime = [string]$settings.local_run_time
if ($runTime -notmatch '^([01]\d|2[0-3]):[0-5]\d$') {
    throw "Ungültige lokale Collector-Zeit: $runTime"
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
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$task = New-ScheduledTask `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $taskSettings `
    -Description "Reiner append-only FX-PIT-Observer; keine Strategie, keine Trades, keine Orders und kein Brokerpfad."

if ($WhatIf) {
    [pscustomobject]@{
        TaskName = $taskName
        LocalRunTime = $runTime
        Mode = "Prüfung ohne Registrierung"
        Runner = $runnerPath
        WakeToRun = $false
        StartWhenAvailable = $true
        BrokerOrderAllowed = $false
    }
    exit 0
}

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State, TaskPath
