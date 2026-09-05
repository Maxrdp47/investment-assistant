[CmdletBinding()]
param(
    [switch]$StartNow,
    [switch]$SelfTestUserIdentity
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

function Resolve-AccountSid {
    param(
        [AllowNull()][object]$Identity
    )

    $name = [string]$Identity
    if ([string]::IsNullOrWhiteSpace($name)) {
        return $null
    }
    try {
        return [System.Security.Principal.SecurityIdentifier]::new($name).Value
    } catch {
        # Not already a SID; resolve an account name below.
    }
    try {
        $account = [System.Security.Principal.NTAccount]::new($name)
        return $account.Translate(
            [System.Security.Principal.SecurityIdentifier]
        ).Value
    } catch {
        return $null
    }
}

function Test-EquivalentUser {
    param(
        [AllowNull()][object]$Actual,
        [AllowNull()][object]$Expected
    )

    if (Test-ExactText -Actual $Actual -Expected ([string]$Expected)) {
        return $true
    }
    $actualSid = Resolve-AccountSid -Identity $Actual
    $expectedSid = Resolve-AccountSid -Identity $Expected
    return (
        -not [string]::IsNullOrWhiteSpace($actualSid) -and
        -not [string]::IsNullOrWhiteSpace($expectedSid) -and
        [System.StringComparer]::OrdinalIgnoreCase.Equals($actualSid, $expectedSid)
    )
}

if ($SelfTestUserIdentity) {
    if ($StartNow) {
        throw "SelfTestUserIdentity cannot be combined with StartNow."
    }
    $currentUserSid = Resolve-AccountSid -Identity $currentUser
    $roundTripSid = Resolve-AccountSid -Identity $currentUserSid
    if ([string]::IsNullOrWhiteSpace($currentUserSid) -or
        -not (Test-EquivalentUser -Actual $currentUser -Expected $currentUserSid) -or
        -not [System.StringComparer]::OrdinalIgnoreCase.Equals(
            $currentUserSid,
            $roundTripSid
        )) {
        throw "Scheduler user-identity self-test failed."
    }
    [ordered]@{
        status = "PASS"
        account_name = $currentUser
        account_sid = $currentUserSid
        sid_round_trip = $roundTripSid
        equivalent = $true
        scheduler_mutated = $false
    } | ConvertTo-Json -Depth 3
    exit 0
}

function Get-ExactNamedTasks {
    # TaskName is not globally unique across Task Scheduler folders. Query all
    # matches and require one result so a duplicate cannot be hidden elsewhere.
    return @(
        Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue |
            Where-Object { $_.TaskName -eq $taskName }
    )
}

function Get-InstalledTaskObservation {
    $matches = @(Get-ExactNamedTasks)
    if ($matches.Count -ne 1) {
        throw "The Development-v6 scheduler task is not uniquely installed."
    }
    $installedTask = $matches[0]
    $installedActions = @($installedTask.Actions)
    $installedTriggers = @($installedTask.Triggers)
    if ($installedActions.Count -ne 1) {
        throw "The installed Development-v6 task does not have exactly one action."
    }
    if ($installedTriggers.Count -ne 1) {
        throw "The installed Development-v6 task does not have exactly one trigger."
    }

    try {
        $repetitionInterval = [System.Xml.XmlConvert]::ToTimeSpan(
            [string]$installedTriggers[0].Repetition.Interval
        )
        $repetitionDuration = [System.Xml.XmlConvert]::ToTimeSpan(
            [string]$installedTriggers[0].Repetition.Duration
        )
        $restartInterval = [System.Xml.XmlConvert]::ToTimeSpan(
            [string]$installedTask.Settings.RestartInterval
        )
        $executionTimeLimit = [System.Xml.XmlConvert]::ToTimeSpan(
            [string]$installedTask.Settings.ExecutionTimeLimit
        )
        $automaticStartBoundary = [DateTime]::Parse(
            [string]$installedTriggers[0].StartBoundary,
            [System.Globalization.CultureInfo]::InvariantCulture
        )
    } catch {
        throw "The installed Development-v6 trigger or settings cannot be verified."
    }

    $taskInfo = Get-ScheduledTaskInfo `
        -TaskName $taskName `
        -TaskPath ([string]$installedTask.TaskPath)
    $observationInstant = Get-Date
    return [pscustomobject]@{
        MatchingTaskCount = $matches.Count
        Task = $installedTask
        Action = $installedActions[0]
        Trigger = $installedTriggers[0]
        RepetitionInterval = $repetitionInterval
        RepetitionDuration = $repetitionDuration
        RestartInterval = $restartInterval
        ExecutionTimeLimit = $executionTimeLimit
        AutomaticStartBoundary = $automaticStartBoundary
        AutomaticAnchorDelayMinutes = (
            $automaticStartBoundary - $observationInstant
        ).TotalMinutes
        NextRunTime = $taskInfo.NextRunTime
        LastRunTime = $taskInfo.LastRunTime
        LastTaskResult = $taskInfo.LastTaskResult
        ObservedAt = $observationInstant
        Enabled = (
            [bool]$installedTask.Settings.Enabled -and
            [string]$installedTask.State -ne "Disabled"
        )
    }
}

function Get-TaskContractChecks {
    param(
        [Parameter(Mandatory = $true)][object]$Observation,
        [Parameter(Mandatory = $true)][bool]$ExpectedEnabled,
        [Parameter(Mandatory = $true)][bool]$GateVerified
    )

    $enabledStateExact = if ($ExpectedEnabled) {
        [bool]$Observation.Enabled
    } else {
        -not [bool]$Observation.Enabled
    }
    $readyStateExact = if ($ExpectedEnabled) {
        [string]$Observation.Task.State -eq "Ready"
    } else {
        [string]$Observation.Task.State -eq "Disabled"
    }
    $nextRunMatchesBoundary = if ($ExpectedEnabled) {
        [Math]::Abs((
            $Observation.NextRunTime - $Observation.AutomaticStartBoundary
        ).TotalSeconds) -le 1
    } else {
        $true
    }

    return [ordered]@{
        exact_task_count = $Observation.MatchingTaskCount -eq 1
        task_enabled = $enabledStateExact
        exactly_one_action = $true
        action_execute_exact = Test-ExactText `
            -Actual $Observation.Action.Execute `
            -Expected $expectedExecute
        action_arguments_exact = Test-ExactText `
            -Actual $Observation.Action.Arguments `
            -Expected $expectedArguments
        action_working_directory_exact = Test-ExactText `
            -Actual $Observation.Action.WorkingDirectory `
            -Expected $expectedWorkingDirectory
        exactly_one_trigger = $true
        five_minute_repetition = `
            [int]$Observation.RepetitionInterval.TotalMinutes -eq 5
        repetition_duration_at_least_3650_days = `
            [int]$Observation.RepetitionDuration.TotalDays -ge 3650
        automatic_anchor_safely_in_future = `
            $Observation.AutomaticAnchorDelayMinutes -ge 14
        multiple_instances_ignore_new = `
            [string]$Observation.Task.Settings.MultipleInstances -eq "IgnoreNew"
        start_when_available = [bool]$Observation.Task.Settings.StartWhenAvailable
        wake_to_run = [bool]$Observation.Task.Settings.WakeToRun
        limited_run_level = [string]$Observation.Task.Principal.RunLevel -eq "Limited"
        interactive_logon = `
            [string]$Observation.Task.Principal.LogonType -eq "Interactive"
        current_user_context = Test-EquivalentUser `
            -Actual $Observation.Task.Principal.UserId `
            -Expected $currentUser
        task_path_exact = Test-ExactText `
            -Actual $Observation.Task.TaskPath `
            -Expected $taskPath
        task_ready = $readyStateExact
        next_run_matches_automatic_boundary = $nextRunMatchesBoundary
        restart_count_three = [int]$Observation.Task.Settings.RestartCount -eq 3
        restart_interval_ten_minutes = `
            [int]$Observation.RestartInterval.TotalMinutes -eq 10
        unlimited_execution_time = `
            [double]$Observation.ExecutionTimeLimit.TotalSeconds -eq 0
        allow_start_on_batteries = `
            -not [bool]$Observation.Task.Settings.DisallowStartIfOnBatteries
        dont_stop_on_batteries = `
            -not [bool]$Observation.Task.Settings.StopIfGoingOnBatteries
        start_now_gate_verified = (-not $StartNow) -or $GateVerified
    }
}

function Disable-TaskAfterFailedVerification {
    $cleanupTasks = @(Get-ExactNamedTasks)
    $rootTasks = @(
        $cleanupTasks |
            Where-Object {
                Test-ExactText -Actual $_.TaskPath -Expected $taskPath
            }
    )
    if ($rootTasks.Count -ne 1) {
        throw "Failed scheduler verification cleanup: root task is not unique."
    }

    # This invocation either registered or replaced this exact root-path task.
    # Disable it regardless of what a failed re-read reports about its action.
    Disable-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath | Out-Null
    $disabledTask = Get-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath `
        -ErrorAction Stop
    if ([string]$disabledTask.State -ne "Disabled" -or
        [bool]$disabledTask.Settings.Enabled) {
        throw "Failed scheduler verification cleanup: task is not disabled."
    }
    return $true
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
    if ($gate.start_authorized -ne $true) {
        throw "StartNow is blocked because the start gate does not authorize a start."
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
    -Disable `
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

$schedulerMutationAttempted = $false
try {
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
    if (-not (Test-ExactText -Actual $existingTaskPath -Expected $taskPath)) {
        throw "Existing v6 task is outside the root task path; refusing to move or overwrite it."
    }
    # Disable the known-safe action while its complete trigger/settings/user
    # contract is replaced, eliminating a stale-trigger race during repair.
    if ([string]$existing.State -ne "Disabled") {
        Disable-ScheduledTask `
            -TaskName $taskName `
            -TaskPath $existingTaskPath | Out-Null
    }
    $schedulerMutationAttempted = $true
    Set-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $existingTaskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal | Out-Null
} else {
    $schedulerMutationAttempted = $true
    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $taskPath `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "Closed Development-v6 reprocessing chain; no Validation, trading or broker path." | Out-Null
}

# Re-read and validate all non-enabled properties while the task is disabled.
# Only a complete staging PASS permits the recurring task to be enabled.
$stagingObservation = Get-InstalledTaskObservation
$stagingChecks = Get-TaskContractChecks `
    -Observation $stagingObservation `
    -ExpectedEnabled $false `
    -GateVerified $startGateVerified
$failedStagingChecks = @(
    $stagingChecks.GetEnumerator() |
        Where-Object { -not [bool]$_.Value } |
        ForEach-Object { [string]$_.Key }
)
if ($failedStagingChecks.Count -gt 0) {
    throw "Disabled Development-v6 scheduler staging contract failed: $($failedStagingChecks -join ', ')"
}

Enable-ScheduledTask `
    -TaskName $taskName `
    -TaskPath ([string]$stagingObservation.Task.TaskPath) | Out-Null

# Re-read the final enabled operating-system state. The emitted JSON is
# evidence from Windows, never merely a copy of the requested values.
$finalObservation = Get-InstalledTaskObservation
$contractChecks = Get-TaskContractChecks `
    -Observation $finalObservation `
    -ExpectedEnabled $true `
    -GateVerified $startGateVerified
$failedChecks = @(
    $contractChecks.GetEnumerator() |
        Where-Object { -not [bool]$_.Value } |
        ForEach-Object { [string]$_.Key }
)
if ($failedChecks.Count -gt 0) {
    throw "Enabled Development-v6 scheduler contract failed: $($failedChecks -join ', ')"
}

if ($StartNow) {
    # Assert-StartGateReady ran before any scheduler mutation. Starting here,
    # after the installed contract re-check, preserves Gate -> Start ordering.
    Start-ScheduledTask -TaskName $taskName `
        -TaskPath ([string]$finalObservation.Task.TaskPath)
}
} catch {
    $originalFailure = $_
    if ($schedulerMutationAttempted) {
        try {
            Disable-TaskAfterFailedVerification | Out-Null
        } catch {
            $cleanupFailure = $_
            throw (
                "Scheduler verification failed: {0} Cleanup also failed: {1}" -f
                $originalFailure.Exception.Message,
                $cleanupFailure.Exception.Message
            )
        }
    }
    throw $originalFailure
}

$task = $finalObservation.Task
$taskActions = @($task.Actions)
$taskTriggers = @($task.Triggers)
$matchingTasks = @(Get-ExactNamedTasks)
[ordered]@{
    status = "INSTALLED"
    task_exists = $true
    task_count = $matchingTasks.Count
    task_name = $taskName
    task_path = [string]$task.TaskPath
    state = [string]$task.State
    enabled = [bool]$task.Settings.Enabled -and [string]$task.State -ne "Disabled"
    last_run_time = $finalObservation.LastRunTime.ToUniversalTime().ToString("o")
    last_task_result = $finalObservation.LastTaskResult
    next_run_time = $finalObservation.NextRunTime.ToUniversalTime().ToString("o")
    wake_to_run = [bool]$task.Settings.WakeToRun
    start_when_available = [bool]$task.Settings.StartWhenAvailable
    multiple_instances = [string]$task.Settings.MultipleInstances
    logon_type = [string]$task.Principal.LogonType
    run_level = [string]$task.Principal.RunLevel
    restart_count = [int]$task.Settings.RestartCount
    restart_interval = [string]$task.Settings.RestartInterval
    restart_interval_minutes = [int]$finalObservation.RestartInterval.TotalMinutes
    execution_time_limit = [string]$task.Settings.ExecutionTimeLimit
    execution_time_limit_seconds = `
        [double]$finalObservation.ExecutionTimeLimit.TotalSeconds
    allow_start_if_on_batteries = `
        -not [bool]$task.Settings.DisallowStartIfOnBatteries
    dont_stop_if_going_on_batteries = `
        -not [bool]$task.Settings.StopIfGoingOnBatteries
    user_context = [string]$task.Principal.UserId
    current_user = $currentUser
    user_context_sid = Resolve-AccountSid -Identity $task.Principal.UserId
    current_user_sid = Resolve-AccountSid -Identity $currentUser
    user_context_matches_current_user = [bool]$contractChecks.current_user_context
    repetition_interval = [string]$taskTriggers[0].Repetition.Interval
    repetition_duration = [string]$taskTriggers[0].Repetition.Duration
    repetition_interval_minutes = `
        [int]$finalObservation.RepetitionInterval.TotalMinutes
    repetition_duration_days = `
        [int]$finalObservation.RepetitionDuration.TotalDays
    automatic_start_boundary = `
        $finalObservation.AutomaticStartBoundary.ToUniversalTime().ToString("o")
    automatic_anchor_delay_minutes = `
        [Math]::Round($finalObservation.AutomaticAnchorDelayMinutes, 3)
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
    observed_at = $finalObservation.ObservedAt.ToUniversalTime().ToString("o")
} | ConvertTo-Json -Depth 6
