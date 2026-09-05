from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = PROJECT_ROOT / "scripts" / "install_multi_asset_development_v6_task.ps1"


def _script() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_v6_task_installer_repairs_the_complete_scheduler_contract() -> None:
    script = _script()

    assert "Disable-ScheduledTask" in script
    assert "Set-ScheduledTask" in script
    assert "Enable-ScheduledTask" in script
    assert "-Action $action" in script
    assert "-Trigger $trigger" in script
    assert "-Settings $settings" in script
    assert "-Principal $principal" in script
    assert "-RepetitionInterval (New-TimeSpan -Minutes 5)" in script
    assert "-RepetitionDuration (New-TimeSpan -Days 3650)" in script
    assert "-MultipleInstances IgnoreNew" in script
    assert "-StartWhenAvailable" in script
    assert "-WakeToRun" in script
    assert "-LogonType Interactive" in script
    assert "-RunLevel Limited" in script
    assert "-UserId $currentUser" in script
    assert "-Disable" in script
    assert "restart_count_three" in script
    assert "restart_interval_ten_minutes" in script
    assert "unlimited_execution_time" in script
    assert "allow_start_on_batteries" in script
    assert "dont_stop_on_batteries" in script
    assert "task_path_exact" in script
    assert "next_run_matches_automatic_boundary" in script


def test_v6_task_installer_uses_a_future_anchor_and_only_starts_after_pass_gate() -> None:
    script = _script()

    assert "-At ((Get-Date).AddMinutes(15))" in script
    assert "function Assert-StartGateReady" in script
    assert 'status -ne "PASS"' in script
    assert 'artifact_fingerprint -notmatch "^[0-9a-f]{64}$"' in script
    assert "$gate.start_authorized -ne $true" in script
    assert "@($gate.blockers).Count -ne 0" in script

    gate_check = script.index(
        "$startGateVerified = Assert-StartGateReady -Path $startGatePath"
    )
    first_scheduler_mutation = min(
        script.index("Register-ScheduledTask"), script.index("Set-ScheduledTask")
    )
    start_call = script.index("Start-ScheduledTask -TaskName $taskName")
    contract_recheck = script.index("if ($failedChecks.Count -gt 0)")
    assert gate_check < first_scheduler_mutation < contract_recheck < start_call
    assert script.count("Start-ScheduledTask -TaskName $taskName") == 1
    start_if = script.rfind("if ($StartNow)", 0, start_call)
    assert start_if > contract_recheck


def test_v6_task_installer_requires_every_exact_start_gate_group() -> None:
    script = _script()
    expected = {
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
        "RUN_ABSENT",
    }

    for group in expected:
        assert f'"{group}"' in script
    assert "$observedGroups.Count -ne $requiredStartGateGroups.Count" in script
    assert "$observedGroups -notcontains $group" in script
    assert '[string]$gate.gates.$group -ne "PASS"' in script


def test_v6_task_installer_fails_closed_on_duplicate_or_foreign_action() -> None:
    script = _script()

    assert "$matchingTasks.Count -gt 1" in script
    assert "refusing an ambiguous repair" in script
    assert "$existingActions.Count -ne 1" in script
    assert "Test-ExactText -Actual $existingActions[0].Execute" in script
    assert "Test-ExactText -Actual $existingActions[0].Arguments" in script
    assert "Existing v6 task has a different action; refusing to overwrite it." in script
    assert "Existing v6 task is currently running" in script
    assert "Existing v6 task is outside the root task path" in script
    assert "-notlike" not in script
    assert "Unregister-ScheduledTask" not in script


def test_v6_task_installer_rechecks_and_reports_observed_operating_system_state() -> None:
    script = _script()

    assert script.count("$matchingTasks = @(Get-ExactNamedTasks)") >= 2
    assert 'status = "INSTALLED"' in script
    for field in (
        "task_exists",
        "task_count",
        "state",
        "enabled",
        "next_run_time",
        "repetition_interval_minutes",
        "repetition_duration_days",
        "multiple_instances",
        "start_when_available",
        "wake_to_run",
        "run_level",
        "restart_count",
        "restart_interval_minutes",
        "execution_time_limit_seconds",
        "allow_start_if_on_batteries",
        "dont_stop_if_going_on_batteries",
        "logon_type",
        "user_context",
        "current_user",
        "user_context_sid",
        "current_user_sid",
        "user_context_matches_current_user",
        "action_execute",
        "action_arguments",
        "action_working_directory",
        "automatic_start_boundary",
        "contract_checks",
        "start_gate_verified",
        "observed_at",
    ):
        assert f"{field} =" in script
    assert 'wrapper = $wrapperRelative' in script
    assert '"scripts/run_multi_asset_development_v6_chain.cmd"' in script


def test_v6_task_installer_enables_only_after_disabled_contract_pass_and_cleans_up() -> None:
    script = _script()

    mutation = min(
        script.index("Register-ScheduledTask"), script.index("Set-ScheduledTask")
    )
    staging_observation = script.index(
        "$stagingObservation = Get-InstalledTaskObservation"
    )
    staging_failure = script.index("if ($failedStagingChecks.Count -gt 0)")
    enable = script.index("Enable-ScheduledTask", staging_failure)
    final_observation = script.index("$finalObservation = Get-InstalledTaskObservation")
    final_failure = script.index("if ($failedChecks.Count -gt 0)")
    start = script.index("Start-ScheduledTask -TaskName $taskName")

    assert mutation < staging_observation < staging_failure < enable
    assert enable < final_observation < final_failure < start
    assert "function Disable-TaskAfterFailedVerification" in script
    assert "if ($schedulerMutationAttempted)" in script
    cleanup_definition = script.index("function Disable-TaskAfterFailedVerification")
    cleanup_disable = script.index("Disable-ScheduledTask", cleanup_definition)
    cleanup_call = script.index("Disable-TaskAfterFailedVerification", final_failure)
    assert cleanup_definition < cleanup_disable < mutation
    assert final_failure < cleanup_call
    cleanup_body = script[cleanup_definition:mutation]
    assert "$rootTasks.Count -ne 1" in cleanup_body
    assert "$disabledTask.State -ne \"Disabled\"" in cleanup_body
    assert "$disabledTask.Settings.Enabled" in cleanup_body
    assert "cleanupActions" not in cleanup_body
    assert "Cleanup also failed" in script


def test_v6_task_installer_compares_equivalent_users_by_sid() -> None:
    script = _script()

    assert "function Resolve-AccountSid" in script
    assert "function Test-EquivalentUser" in script
    assert "$account.Translate(" in script
    assert "[System.Security.Principal.SecurityIdentifier]" in script
    assert "SecurityIdentifier]::new($name).Value" in script
    assert "current_user_context = Test-EquivalentUser" in script


@pytest.mark.skipif(os.name != "nt", reason="Windows account identity regression")
def test_v6_task_installer_round_trips_account_name_and_sid_without_mutation() -> None:
    executable = shutil.which("powershell.exe")
    assert executable is not None
    completed = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(INSTALLER),
            "-SelfTestUserIdentity",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8-sig",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["account_sid"] == result["sid_round_trip"]
    assert result["equivalent"] is True
    assert result["scheduler_mutated"] is False


def test_v6_task_installer_has_valid_powershell_syntax() -> None:
    executable = shutil.which("pwsh") or shutil.which("powershell.exe")
    if executable is None:
        pytest.skip("PowerShell parser is not available on this test host.")
    escaped_path = str(INSTALLER).replace("'", "''")
    parser_command = (
        "$tokens = $null; $errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped_path}', "
        "[ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { "
        "$errors | ForEach-Object { Write-Error $_.Message }; exit 1 }; exit 0"
    )
    completed = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-Command", parser_command],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
