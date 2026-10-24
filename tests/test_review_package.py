"""Offline checks for the stable Review bootstrap contract."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReviewBootstrapTests(unittest.TestCase):
    def run_script(self, name, guard_text, **extra_env):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            guard = home / "guard.sh"
            guard.write_text(guard_text)
            log = home / "calls"
            env = dict(os.environ, HOME=str(home), BASH_ENV=str(guard), CALL_LOG=str(log))
            env.update(extra_env)
            result = subprocess.run(["bash", str(ROOT / ".devcontainer/scripts" / name)],
                                    env=env, capture_output=True, text=True)
            return result, log.read_text().splitlines()

    def test_install_uses_stable_tap_and_formula(self):
        result, calls = self.run_script("install-review-package.sh", '''brew() {
  printf '%s\\n' "$*" >> "$CALL_LOG"
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["trust --tap joshyorko/tools", "tap joshyorko/tools",
                                 "update", "install joshyorko/tools/review"])

    def test_source_migrates_retired_upstream_without_resetting_local_work(self):
        result, calls = self.run_script("prepare-review-source.sh", '''git() {
  printf '%s\\n' "$*" >> "$CALL_LOG"
  case "$*" in
    clone*) mkdir -p "$HOME/src/review/.git" ;;
    'remote get-url upstream') echo https://github.com/projectbluefin/review.git ;;
    'status --porcelain') echo ' M local-file' ;;
  esac
}
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local changes", result.stderr)
        self.assertIn("remote set-url upstream https://github.com/joshyorko/review.git", calls)
        self.assertIn("fetch upstream main", calls)
        self.assertFalse(any(call.startswith(("switch", "merge", "reset")) for call in calls))

    def test_shared_omp_configuration_uses_current_launcher_variable(self):
        config = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(config["containerEnv"]["REVIEW_INHERIT_OMP_CONFIG"], "1")
        self.assertFalse(any(key.startswith("BLUEFIN_") for key in config["containerEnv"]))
