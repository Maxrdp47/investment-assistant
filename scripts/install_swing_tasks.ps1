[CmdletBinding()]
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$settingsPath = Join-Path $projectRoot "config\swing_background_settings.json"
$runnerPath = Join-Path $projectRoot "scripts\run_swing_scans.cmd"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

foreach ($requiredPath in @($settingsPath, $runnerPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Erforderliche Datei fehlt: $requiredPath"
    }
}

$settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$taskPrefix = [string]$settings.task_prefix
$results = @()

foreach ($scopeProperty in $settings.scopes.PSObject.Properties) {
    $scopeName = [string]$scopeProperty.Name
    $scope = $scopeProperty.Value
    $runTime = [string]$scope.local_run_time
    $scheduleMode = [string]$scope.schedule_mode
    if (-not $scheduleMode) {
        $scheduleMode = "daily"
    }
    if ($runTime -notmatch '^([01]\d|2[0-3]):[0-5]\d$') {
        throw "Ungültige lokale Uhrzeit für $scopeName`: $runTime"
    }
    $taskName = "$taskPrefix-$scopeName"
    if ($scheduleMode -ne "daily") {
        if (-not $WhatIf -and (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }
        $results += [pscustomobject]@{
            TaskName = $taskName
            Scope = $scopeName
            LocalRunTime = $runTime
            ScheduleMode = $scheduleMode
            Runner = "scripts\run_evening_pipeline.cmd"
            Mode = $(if ($WhatIf) { "Prüfung: separate Nachtaufgabe wird entfernt" } else { "In Abendkette; separate Aufgabe entfernt" })
        }
        continue
    }
    $action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/d /c `"$runnerPath $scopeName`"" `
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
        -RestartInterval (New-TimeSpan -Minutes 20) `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 4)
    $task = New-ScheduledTask `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $taskSettings `
        -Description "Lokaler objektiver Swing-Forward-Scan ($scopeName) ohne Orderausführung."

    if (-not $WhatIf) {
        Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
    }
    $results += [pscustomobject]@{
        TaskName = $taskName
        Scope = $scopeName
        LocalRunTime = $runTime
        ScheduleMode = $scheduleMode
        User = "$env:USERDOMAIN\$env:USERNAME"
        Runner = "$runnerPath $scopeName"
        WorkingDirectory = $projectRoot
        WakeToRun = $true
        RestartCount = 3
        RestartIntervalMinutes = 20
        MultipleInstances = "IgnoreNew"
        Mode = $(if ($WhatIf) { "Prüfung ohne Registrierung" } else { "Registriert" })
    }
}

$results
