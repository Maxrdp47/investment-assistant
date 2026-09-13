[CmdletBinding()]
param(
    [switch]$Pilot,
    [switch]$InstallAndStart,
    [switch]$Inspect
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = "C:\investment-assistent"
$taskPath = "\"
$taskName = "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v7-Recovery-r2"
$pilotTaskName = "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v7-Recovery-r2-Pilot"
$v6TaskName = "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain"
$wrapper = Join-Path $projectRoot "scripts\run_multi_asset_development_v7_recovery.cmd"
$gatePath = Join-Path $projectRoot "runtime\research_exports\multi_asset_development_v7_start_gate_2026-09-13-v2.json"
$smokePath = Join-Path $projectRoot "runtime\research_exports\multi_asset_development_v7_scheduler_smoke_2026-09-13-v3.json"
$pilotPath = Join-Path $projectRoot "runtime\research_exports\multi_asset_development_v7_pilot_2026-09-13-v3.json"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (@(@($Pilot, $InstallAndStart, $Inspect) | Where-Object { $_ }).Count -ne 1) {
    throw "Select exactly one of -Pilot, -InstallAndStart, or -Inspect."
}
if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) {
    throw "v7 scheduler wrapper is missing: $wrapper"
}

function Get-ExactTask {
    param([Parameter(Mandatory = $true)][string]$Name)
    $matches = @(Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue |
        Where-Object { $_.TaskName -eq $Name })
    if ($matches.Count -gt 1) {
        throw "Task name is ambiguous across scheduler folders: $Name"
    }
    if ($matches.Count -eq 0) { return $null }
    if ([string]$matches[0].TaskPath -ne $taskPath) {
        throw "Task exists outside the expected root folder: $Name"
    }
    return $matches[0]
}

function Resolve-AccountSid {
    param([AllowNull()][object]$Identity)
    $name = [string]$Identity
    if ([string]::IsNullOrWhiteSpace($name)) { return $null }
    try {
        return [System.Security.Principal.SecurityIdentifier]::new($name).Value
    } catch {
        try {
            return [System.Security.Principal.NTAccount]::new($name).Translate(
                [System.Security.Principal.SecurityIdentifier]
            ).Value
        } catch {
            return $null
        }
    }
}

function Test-EquivalentUser {
    param(
        [AllowNull()][object]$Actual,
        [AllowNull()][object]$Expected
    )
    if ([string]$Actual -ieq [string]$Expected) { return $true }
    $actualSid = Resolve-AccountSid -Identity $Actual
    $expectedSid = Resolve-AccountSid -Identity $Expected
    return (-not [string]::IsNullOrWhiteSpace($actualSid) -and
        $actualSid -eq $expectedSid)
}

function New-V7Action {
    param([Parameter(Mandatory = $true)][string]$Arguments)
    return New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/d /c `"`"$wrapper`" $Arguments`"" `
        -WorkingDirectory $projectRoot
}

function New-V7Settings {
    return New-ScheduledTaskSettingsSet `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -WakeToRun `
        -RestartCount 3 `
        -RestartInterval (New-TimeSpan -Minutes 10) `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries
}

function New-V7Principal {
    return New-ScheduledTaskPrincipal `
        -UserId $currentUser `
        -LogonType Interactive `
        -RunLevel Limited
}

function Assert-TaskContract {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Arguments,
        [Parameter(Mandatory = $true)][bool]$Repeating
    )
    $task = Get-ExactTask -Name $Name
    if ($null -eq $task) { throw "Scheduled task is absent: $Name" }
    $actions = @($task.Actions)
    $triggers = @($task.Triggers)
    $expectedArguments = "/d /c `"`"$wrapper`" $Arguments`""
    $checks = [ordered]@{
        exact_task = $true
        exactly_one_action = $actions.Count -eq 1
        exactly_one_trigger = $triggers.Count -eq 1
        execute = $actions.Count -eq 1 -and [string]$actions[0].Execute -ieq "cmd.exe"
        arguments = $actions.Count -eq 1 -and [string]$actions[0].Arguments -ieq $expectedArguments
        working_directory = $actions.Count -eq 1 -and [string]$actions[0].WorkingDirectory -ieq $projectRoot
        current_user = Test-EquivalentUser `
            -Actual $task.Principal.UserId `
            -Expected $currentUser
        interactive = [string]$task.Principal.LogonType -eq "Interactive"
        limited = [string]$task.Principal.RunLevel -eq "Limited"
        ignore_new = [string]$task.Settings.MultipleInstances -eq "IgnoreNew"
        start_when_available = [bool]$task.Settings.StartWhenAvailable
        wake_to_run = [bool]$task.Settings.WakeToRun
        enabled = [bool]$task.Settings.Enabled
    }
    if ($Repeating -and $triggers.Count -eq 1) {
        $checks["five_minute_repetition"] = [string]$triggers[0].Repetition.Interval -eq "PT5M"
    }
    if (@($checks.Values | Where-Object { -not $_ }).Count -ne 0) {
        throw "Scheduled task contract failed: $($checks | ConvertTo-Json -Compress)"
    }
    $info = Get-ScheduledTaskInfo -TaskName $Name -TaskPath $taskPath
    return [ordered]@{
        task_name = $Name
        checks = $checks
        state = [string]$task.State
        last_run_time = $info.LastRunTime.ToString("o")
        next_run_time = $info.NextRunTime.ToString("o")
        last_task_result = [int]$info.LastTaskResult
        observed_at = (Get-Date).ToString("o")
    }
}

if ($Inspect) {
    $main = Get-ExactTask -Name $taskName
    $pilotTask = Get-ExactTask -Name $pilotTaskName
    $v6 = Get-ExactTask -Name $v6TaskName
    [ordered]@{
        status = "OBSERVED"
        current_user = $currentUser
        v7_task_state = if ($null -eq $main) { "ABSENT" } else { [string]$main.State }
        pilot_task_state = if ($null -eq $pilotTask) { "ABSENT" } else { [string]$pilotTask.State }
        v6_task_state = if ($null -eq $v6) { "ABSENT" } else { [string]$v6.State }
    } | ConvertTo-Json -Depth 5
    exit 0
}

if ($Pilot) {
    if ($null -ne (Get-ExactTask -Name $pilotTaskName)) {
        throw "Pilot task already exists; refusing an ambiguous overwrite."
    }
    $definition = New-ScheduledTask `
        -Action (New-V7Action -Arguments "--scheduler-bootstrap") `
        -Trigger (New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(2))) `
        -Settings (New-V7Settings) `
        -Principal (New-V7Principal)
    Register-ScheduledTask `
        -TaskName $pilotTaskName `
        -TaskPath $taskPath `
        -InputObject $definition | Out-Null
    $installed = Assert-TaskContract `
        -Name $pilotTaskName `
        -Arguments "--scheduler-bootstrap" `
        -Repeating $false
    Start-ScheduledTask -TaskName $pilotTaskName -TaskPath $taskPath
    $deadline = (Get-Date).AddMinutes(60)
    do {
        Start-Sleep -Seconds 2
        $task = Get-ScheduledTask -TaskName $pilotTaskName -TaskPath $taskPath
        $info = Get-ScheduledTaskInfo -TaskName $pilotTaskName -TaskPath $taskPath
    } while ([string]$task.State -eq "Running" -and (Get-Date) -lt $deadline)
    if ([string]$task.State -eq "Running") {
        throw "Scheduler-context pilot is still running after the bounded observation period."
    }
    if ([int]$info.LastTaskResult -ne 0) {
        throw "Scheduler-context pilot failed with result $([int]$info.LastTaskResult)."
    }
    if (-not (Test-Path -LiteralPath $smokePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $pilotPath -PathType Leaf)) {
        throw "Scheduler-context pilot did not create both evidence artifacts."
    }
    $smoke = Get-Content -LiteralPath $smokePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $pilotEvidence = Get-Content -LiteralPath $pilotPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$smoke.status -ne "PASS" -or [string]$pilotEvidence.status -ne "PASS") {
        throw "Scheduler-context smoke or pilot is not PASS."
    }
    Unregister-ScheduledTask -TaskName $pilotTaskName -TaskPath $taskPath -Confirm:$false
    [ordered]@{
        status = "PASS"
        scheduler_context = $installed
        last_task_result = [int]$info.LastTaskResult
        smoke_report = $smokePath
        pilot_report = $pilotPath
        pilot_task_removed = $null -eq (Get-ExactTask -Name $pilotTaskName)
    } | ConvertTo-Json -Depth 8
    exit 0
}

$gate = Get-Content -LiteralPath $gatePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$gate.status -ne "PASS" -or $gate.start_authorized -ne $true -or
    @($gate.blockers).Count -ne 0) {
    throw "InstallAndStart requires the immutable PASS v7 start gate."
}
$existing = Get-ExactTask -Name $taskName
if ($null -ne $existing) {
    throw "v7 recovery task already exists; inspect it instead of overwriting it."
}
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At ((Get-Date).AddMinutes(15)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$definition = New-ScheduledTask `
    -Action (New-V7Action -Arguments "--advance") `
    -Trigger $trigger `
    -Settings (New-V7Settings) `
    -Principal (New-V7Principal)
Register-ScheduledTask `
    -TaskName $taskName `
    -TaskPath $taskPath `
    -InputObject $definition | Out-Null
$installed = Assert-TaskContract -Name $taskName -Arguments "--advance" -Repeating $true
$v6 = Get-ExactTask -Name $v6TaskName
$v6Disabled = $false
if ($null -ne $v6 -and [string]$v6.State -ne "Disabled") {
    Disable-ScheduledTask -TaskName $v6TaskName -TaskPath $taskPath | Out-Null
    $v6Disabled = [string](Get-ScheduledTask -TaskName $v6TaskName -TaskPath $taskPath).State -eq "Disabled"
}
if ($null -ne $v6 -and -not $v6Disabled -and [string]$v6.State -ne "Disabled") {
    throw "v6 task could not be disabled after v7 installation."
}
Start-ScheduledTask -TaskName $taskName -TaskPath $taskPath
[ordered]@{
    status = "V7_RECOVERY_RUNNING"
    scheduler_contract = $installed
    v6_task_disabled = if ($null -eq $v6) { "ABSENT" } else { $true }
    start_requested_at = (Get-Date).ToString("o")
} | ConvertTo-Json -Depth 8
