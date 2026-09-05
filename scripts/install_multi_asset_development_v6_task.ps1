[CmdletBinding()]
param(
    [switch]$StartNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$taskName = "InvestmentAssistant-MultiAssetDiscoveryV1-Development-v6-Chain"
$projectRoot = "C:\investment-assistent"
$taskPath = "\"
$wrapperRelative = "scripts/run_multi_asset_development_v6_chain.cmd"
$wrapper = Join-Path $projectRoot "scripts\run_multi_asset_development_v6_chain.cmd"
$startGatePath = Join-Path $projectRoot "runtime\research_exports\multi_asset_development_v6_start_gate_2026-09-05-v1.json"
$expectedExecute = "cmd.exe"
$expectedArguments = "/d /c `"`"$wrapper`"`""
$expectedWorkingDirectory = $projectRoot
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$requiredStartGateGroups = @(
    "CONTRACT_AND_DIFF",
    "IMMUTABLE_V5_PARENT",
    "INPUT_BINDING",
    "WORKER_BENCHMARK_BINDING",
    "DESCRIPTIVE_PLAN_BINDING",
    "RESOURCES",
    "PYTHON_ENVIRONMENT",
    "GIT_PROVENANCE",
    "LOCAL_VERIFICATION",
    "CI_VERIFICATION",
    "SCHEDULER_CONTRACT",
    "RUN_ABSENT"
)

function Test-ExactText {
    param(
        [AllowNull()][object]$Actual,
        [Parameter(Mandatory = $true)][string]$Expected
    )

    return [System.StringComparer]::OrdinalIgnoreCase.Equals(
        [string]$Actual,
        $Expected
    )
}

function Get-ExactNamedTasks {
    # TaskName is not globally unique across Task Scheduler folders. Query all
    # matches and require one result so a duplicate cannot be hidden elsewhere.
    return @(
        Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue |
            Where-Object { $_.TaskName -eq $taskName }
    )
}

function Assert-StartGateReady {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "StartNow requires the immutable PASS start gate: $Path"
    }
    try {
        $gate = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 |
            ConvertFrom-Json
    } catch {
        throw "StartNow requires a readable JSON start gate: $Path"
    }
    if ($null -eq $gate -or
        [string]$gate.version -ne "multi-asset-development-v6-start-gate-2026.09.05-v1" -or
        [string]$gate.status -ne "PASS") {
        throw "StartNow is blocked because the Development-v6 start gate is not PASS."
    }
    if ([string]$gate.artifact_fingerprint -notmatch "^[0-9a-f]{64}$") {
        throw "StartNow is blocked because the start-gate fingerprint is absent or malformed."
    }
    if ($null -eq $gate.gates) {
        throw "StartNow is blocked because start-gate groups are absent."
    }
    $observedGroups = @($gate.gates.PSObject.Properties.Name)
    if ($observedGroups.Count -ne $requiredStartGateGroups.Count) {
        throw "StartNow is blocked because the start-gate group set is not exact."
    }
    foreach ($group in $requiredStartGateGroups) {
        if ($observedGroups -notcontains $group -or
            [string]$gate.gates.$group -ne "PASS") {
            throw "StartNow is blocked because start-gate group '$group' is not PASS."
        }
    }
    if (@($gate.blockers).Count -ne 0) {
        throw "StartNow is blocked because the start gate contains blockers."
    }
    # The Python runner independently verifies the canonical fingerprint and
    # contract binding before it can create a run. This installer check makes
    # the operator-level StartNow ordering explicit as well.
    return $true
}

if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) {
    throw "Scheduler wrapper is missing: $wrapper"
}

$startGateVerified = $false
if ($StartNow) {
    # Check the gate before registering, repairing, enabling or starting the
    # task. A failed StartNow request therefore does not mutate scheduler
    # state. The Python runner also remains fail-closed on automatic triggers.
    $startGateVerified = Assert-StartGateReady -Path $startGatePath
}

$action = New-ScheduledTaskAction `
    -Execute $expectedExecute `
    -Argument $expectedArguments `
    -WorkingDirectory $expectedWorkingDirectory
# Keep the first automatic fire safely in the future so the fail-closed start
# gate can bind the installed task before `-StartNow` launches the real run.
# Every subsequent trigger remains exactly five minutes apart.
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(15)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -WakeToRun `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Limited

$matchingTasks = @(Get-ExactNamedTasks)
if ($matchingTasks.Count -gt 1) {
    throw "More than one task uses the v6 task name; refusing an ambiguous repair."
}

if ($matchingTasks.Count -eq 1) {
    $existing = $matchingTasks[0]
    $existingActions = @($existing.Actions)
    if ($existingActions.Count -ne 1 -or
        -not (Test-ExactText -Actual $existingActions[0].Execute -Expected $expectedExecute) -or
        -not (Test-ExactText -Actual $existingActions[0].Arguments -Expected $expectedArguments)) {
        throw "Existing v6 task has a different action; refusing to overwrite it."
    }
    if ([string]$existing.State -eq "Running") {
        throw "Existing v6 task is currently running; refusing to repair or duplicate it."
    }
    $existingTaskPath = [string]$existing.TaskPath
    if ([string]::IsNullOrWhiteSpace($existingTaskPath)) {
        $existingTaskPath = $taskPath
    }
    # Disable the known-safe action while its complete trigger/settings/user
    # contract is replaced, eliminating a stale-trigger race during repair.
    if ([string]$existing.State -ne "Disabled") {
        Disable-ScheduledTask `
            -TaskName $taskName `
            -TaskPath $existingTaskPath | Out-Null
    }
    Set-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $existingTaskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal | Out-Null
    Enable-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $existingTaskPath | Out-Null
} else {
    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Closed Development-v6 reprocessing chain; no Validation, trading or broker path." | Out-Null
    Enable-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath | Out-Null
}

# Re-read the operating-system state. The emitted JSON is evidence from the
# installed task, never merely a copy of the requested values.
$matchingTasks = @(Get-ExactNamedTasks)
if ($matchingTasks.Count -ne 1) {
    throw "The Development-v6 scheduler task is not uniquely installed."
}
$task = $matchingTasks[0]
$taskActions = @($task.Actions)
$taskTriggers = @($task.Triggers)
if ($taskActions.Count -ne 1) {
    throw "The installed Development-v6 task does not have exactly one action."
}
if ($taskTriggers.Count -ne 1) {
    throw "The installed Development-v6 task does not have exactly one trigger."
}

try {
    $repetitionInterval = [System.Xml.XmlConvert]::ToTimeSpan(
        [string]$taskTriggers[0].Repetition.Interval
    )
    $repetitionDuration = [System.Xml.XmlConvert]::ToTimeSpan(
        [string]$taskTriggers[0].Repetition.Duration
    )
    $automaticStartBoundary = [DateTime]::Parse(
        [string]$taskTriggers[0].StartBoundary,
        [System.Globalization.CultureInfo]::InvariantCulture
    )
} catch {
    throw "The installed Development-v6 trigger cannot be verified."
}
$automaticAnchorDelayMinutes = ($automaticStartBoundary - (Get-Date)).TotalMinutes
$taskEnabled = (
    [bool]$task.Settings.Enabled -and [string]$task.State -ne "Disabled"
)
$contractChecks = [ordered]@{
    exact_task_count = $matchingTasks.Count -eq 1
    task_enabled = $taskEnabled
    exactly_one_action = $taskActions.Count -eq 1
    action_execute_exact = Test-ExactText `
        -Actual $taskActions[0].Execute `
        -Expected $expectedExecute
    action_arguments_exact = Test-ExactText `
        -Actual $taskActions[0].Arguments `
        -Expected $expectedArguments
    action_working_directory_exact = Test-ExactText `
        -Actual $taskActions[0].WorkingDirectory `
        -Expected $expectedWorkingDirectory
    exactly_one_trigger = $taskTriggers.Count -eq 1
    five_minute_repetition = [int]$repetitionInterval.TotalMinutes -eq 5
    repetition_duration_at_least_3650_days = `
        [int]$repetitionDuration.TotalDays -ge 3650
    automatic_anchor_safely_in_future = $automaticAnchorDelayMinutes -ge 14
    multiple_instances_ignore_new = `
        [string]$task.Settings.MultipleInstances -eq "IgnoreNew"
    start_when_available = [bool]$task.Settings.StartWhenAvailable
    wake_to_run = [bool]$task.Settings.WakeToRun
    limited_run_level = [string]$task.Principal.RunLevel -eq "Limited"
    interactive_logon = [string]$task.Principal.LogonType -eq "Interactive"
    current_user_context = Test-ExactText `
        -Actual $task.Principal.UserId `
        -Expected $currentUser
    start_now_gate_verified = (-not $StartNow) -or $startGateVerified
}
$failedChecks = @(
    $contractChecks.GetEnumerator() |
        Where-Object { -not [bool]$_.Value } |
        ForEach-Object { [string]$_.Key }
)
if ($failedChecks.Count -gt 0) {
    throw "Installed Development-v6 scheduler contract failed: $($failedChecks -join ', ')"
}

if ($StartNow) {
    # Assert-StartGateReady ran before any scheduler mutation. Starting here,
    # after the installed contract re-check, preserves Gate -> Start ordering.
    Start-ScheduledTask -TaskName $taskName -TaskPath ([string]$task.TaskPath)
}

$task = @(Get-ExactNamedTasks)[0]
$info = Get-ScheduledTaskInfo `
    -TaskName $taskName `
    -TaskPath ([string]$task.TaskPath)
[ordered]@{
    status = "INSTALLED"
    task_exists = $true
    task_count = $matchingTasks.Count
    task_name = $taskName
    task_path = [string]$task.TaskPath
    state = [string]$task.State
    enabled = [bool]$task.Settings.Enabled -and [string]$task.State -ne "Disabled"
    last_run_time = $info.LastRunTime.ToString("o")
    last_task_result = $info.LastTaskResult
    next_run_time = $info.NextRunTime.ToString("o")
    wake_to_run = [bool]$task.Settings.WakeToRun
    start_when_available = [bool]$task.Settings.StartWhenAvailable
    multiple_instances = [string]$task.Settings.MultipleInstances
    logon_type = [string]$task.Principal.LogonType
    run_level = [string]$task.Principal.RunLevel
    user_context = [string]$task.Principal.UserId
    current_user = $currentUser
    user_context_matches_current_user = [bool]$contractChecks.current_user_context
    repetition_interval = [string]$taskTriggers[0].Repetition.Interval
    repetition_duration = [string]$taskTriggers[0].Repetition.Duration
    repetition_interval_minutes = [int]$repetitionInterval.TotalMinutes
    repetition_duration_days = [int]$repetitionDuration.TotalDays
    automatic_start_boundary = $automaticStartBoundary.ToString("o")
    automatic_anchor_delay_minutes = [Math]::Round($automaticAnchorDelayMinutes, 3)
    wrapper = $wrapperRelative
    wrapper_absolute = $wrapper
    action_execute = [string]$taskActions[0].Execute
    action_arguments = [string]$taskActions[0].Arguments
    action_working_directory = [string]$taskActions[0].WorkingDirectory
    action = "$($taskActions[0].Execute) $($taskActions[0].Arguments)"
    contract_checks = $contractChecks
    start_requested = [bool]$StartNow
    start_gate_path = $startGatePath
    start_gate_verified = $startGateVerified
    observed_at = (Get-Date).ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 6
