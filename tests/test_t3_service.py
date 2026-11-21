"""Run the task with isolated HOME and upstream/systemd command boundaries."""

import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

GUARD = r'''
set -E
id() { case "$1" in -un) echo "${TEST_USER:-vscode}";; -u) echo 1000;; esac; }
cat() { if [[ "$1" == /proc/1/comm ]]; then echo "${TEST_INIT:-systemd}"; else command cat "$@"; fi; }
loginctl() { echo yes; }
busctl() { [[ "${TEST_BUS:-healthy}" == healthy ]]; }
systemctl() {
    printf 'systemctl %s\n' "$*" >> "$CALL_LOG"
    case "$*" in
        is-system-running) echo "${TEST_STATE:-running}";;
        *is-active*sh.brew.t3code-cli-main.service) [[ "${TEST_LEGACY:-no}" == yes ]];;
        *is-active*t3code.service) [[ "${TEST_ACTIVE:-yes}" == yes ]];;
        *is-active*) [[ "${TEST_MANAGER:-healthy}" == healthy ]];;
    esac
}
curl() {
    printf 'curl %s\n' "$*" >> "$CALL_LOG"
    [[ "${TEST_DOWNLOAD:-healthy}" == healthy ]] || return 1
    while (( $# )); do
        if [[ "$1" == --output ]]; then cp "$FAKE_INSTALLER" "$2"; return; fi
        shift
    done
    return 1
}
sleep() { SECONDS=$((SECONDS + 1)); }
'''

CLI = r'''#!/bin/bash
printf 't3 %s\n' "$*" >> "$CALL_LOG"
[[ "${TEST_START:-healthy}" == healthy ]]
'''
INSTALLER = r'''#!/bin/sh
set -eu
printf 'installer channel=%s\n' "$T3CODE_CHANNEL" >> "$CALL_LOG"
mkdir -p "$T3CODE_INSTALL_BIN_DIR"
cp "$FAKE_T3" "$T3CODE_INSTALL_BIN_DIR/t3"
chmod +x "$T3CODE_INSTALL_BIN_DIR/t3"
'''


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.home = self.directory / "home"
        self.home.mkdir()
        self.bus = socket.socket(socket.AF_UNIX)
        self.addCleanup(self.bus.close)
        self.bus.bind(str(self.directory / "bus"))
        self.guard = self.directory / "guard.sh"
        self.guard.write_text(GUARD)
        self.cli = self.directory / "t3"
        self.cli.write_text(CLI)
        self.cli.chmod(0o755)
        self.installer = self.directory / "installer"
        self.installer.write_text(INSTALLER)
        self.log = self.directory / "calls"

    def run_task(self, **overrides):
        environment = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR=str(self.directory),
                           T3CODE_HOME=str(self.home / ".t3"), T3CODE_CHANNEL="nightly",
                           BASH_ENV=str(self.guard), CALL_LOG=str(self.log),
                           FAKE_T3=str(self.cli), FAKE_INSTALLER=str(self.installer),
                           TMPDIR=str(self.directory))
        environment.update(overrides)
        result = subprocess.run(["/bin/bash", str(ROOT / ".vscode/install-t3-service.sh")],
                                env=environment, text=True, capture_output=True, timeout=5)
        calls = self.log.read_text().splitlines() if self.log.exists() else []
        return result, calls

    def test_task_is_a_finite_manual_process(self):
        tasks = json.loads((ROOT / ".vscode/tasks.json").read_text())["tasks"]
        task = next(task for task in tasks if task["label"] == "T3: Install and start service")
        self.assertEqual(task["type"], "process")
        self.assertEqual(task["command"], "/bin/bash")
        self.assertEqual(task["args"], ["${workspaceFolder}/.vscode/install-t3-service.sh"])
        self.assertEqual(task["problemMatcher"], [])
        self.assertEqual(task["runOptions"].get("instanceLimit"), 1)
        self.assertNotIn("runOn", task["runOptions"])
        self.assertFalse(task.get("isBackground", False))

    def test_fresh_official_install_starts_native_service_and_persists_telemetry(self):
        result, calls = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(any("https://t3.codes/install.sh" in call for call in calls))
        self.assertIn("installer channel=nightly", calls)
        self.assertIn("t3 service install", calls)
        self.assertIn("t3 service status", calls)
        settings = self.home / ".t3/service.env"
        self.assertEqual(settings.read_text(), "T3CODE_TELEMETRY_ENABLED=false\n")
        self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
        self.assertIn("PASS:", result.stdout)
        self.assertFalse(list(self.directory.glob("work-jatt-t3-install.*")))

    def test_existing_install_and_settings_are_retained_across_runs(self):
        result, _ = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = self.home / ".t3/service.env"
        settings.write_text("# custom\nT3CODE_TELEMETRY_ENABLED=true\nT3CODE_PORT=4000\n")
        expected = settings.read_bytes()
        self.log.unlink()
        result, calls = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(any(call.startswith(("installer ", "curl ")) for call in calls))
        self.assertFalse(any("restart" in call or "stop" in call for call in calls))
        self.assertEqual(settings.read_bytes(), expected)

    def test_explicit_new_install_channel_is_passed_to_official_installer(self):
        result, calls = self.run_task(T3CODE_CHANNEL="stable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("installer channel=stable", calls)

    def test_user_cli_link_to_retired_formula_is_rejected(self):
        retired = self.directory / "Cellar/t3code-cli-main/1/bin/t3"
        retired.parent.mkdir(parents=True)
        retired.write_text(CLI)
        retired.chmod(0o755)
        launcher = self.home / ".local/bin/t3"
        launcher.parent.mkdir(parents=True)
        launcher.symlink_to(retired)
        result, calls = self.run_task()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still points to the retired Homebrew", result.stderr)
        self.assertFalse(any(call.startswith(("curl ", "t3 ")) for call in calls))
        self.assertEqual(launcher.resolve(), retired)

    def test_custom_t3_home_is_used_without_losing_existing_configuration(self):
        home = self.directory / "custom-t3"
        home.mkdir()
        settings = home / "service.env"
        settings.write_text("T3CODE_PORT=4000")
        result, _ = self.run_task(T3CODE_HOME=str(home))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(settings.read_text(), "T3CODE_PORT=4000\nT3CODE_TELEMETRY_ENABLED=false\n")

    def test_prerequisite_failures_happen_before_download(self):
        for overrides, message in [
            ({"TEST_INIT": "tini"}, "issues/5"),
            ({"TEST_BUS": "broken"}, "user bus"),
            ({"TEST_MANAGER": "broken"}, "user manager"),
            ({"TEST_USER": "root"}, "non-root vscode"),
            ({"TEST_LEGACY": "yes"}, "retired Homebrew"),
        ]:
            with self.subTest(overrides=overrides):
                self.log.unlink(missing_ok=True)
                result, calls = self.run_task(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(any(call.startswith(("curl ", "t3 ", "installer ")) for call in calls))

    def test_missing_bus_socket_fails_before_download(self):
        (self.directory / "bus").unlink()
        result, calls = self.run_task()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("user bus is missing", result.stderr)
        self.assertFalse(any(call.startswith("curl ") for call in calls))

    def test_degraded_system_is_visible_but_required_managers_suffice(self):
        result, calls = self.run_task(TEST_STATE="degraded")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING:", result.stderr)
        self.assertIn("systemctl --failed --no-pager --plain", calls)

    def test_overlapping_setup_is_rejected(self):
        with (self.directory / "work-jatt-t3-service.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result, calls = self.run_task()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Another T3 service setup", result.stderr)
        self.assertFalse(any(call.startswith("curl ") for call in calls))

    def test_inactive_unit_is_a_bounded_failure(self):
        result, calls = self.run_task(TEST_ACTIVE="no")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("within 30 seconds", result.stderr)
        self.assertNotIn("PASS:", result.stdout)
        self.assertLessEqual(calls.count("systemctl --user is-active --quiet t3code.service"), 30)

    def test_failed_download_does_not_install_or_start(self):
        result, calls = self.run_task(TEST_DOWNLOAD="broken")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("installer channel=nightly", calls)
        self.assertNotIn("t3 service install", calls)
        self.assertFalse(list(self.directory.glob("work-jatt-t3-install.*")))

    def test_failed_upstream_service_setup_returns_diagnostics(self):
        result, calls = self.run_task(TEST_START="broken")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any("--property=ActiveState,SubState,Result,MainPID,ExecMainStatus,NRestarts" in call
                            for call in calls))
        self.assertNotIn("PASS:", result.stdout)


if __name__ == "__main__":
    unittest.main()
