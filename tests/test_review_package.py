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

    def test_install_avoids_whole_tap_validation(self):
        result, calls = self.run_script("install-review-package.sh", '''brew() {
  printf '%s\\n' "$*" >> "$CALL_LOG"
  if [[ "$1" == tap ]]; then
    echo "Cannot tap joshyorko/tools: invalid syntax in tap!" >&2
    return 1
  fi
  if [[ "$1" == list ]]; then return 1; fi
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["update",
                                 "trust --formula joshyorko/tools/review",
                                 "list --versions joshyorko/tools/review",
                                 "install joshyorko/tools/review"])

    def test_install_upgrades_existing_stable_review_formula(self):
        result, calls = self.run_script("install-review-package.sh", '''brew() {
  printf '%s\\n' "$*" >> "$CALL_LOG"
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["update", "trust --formula joshyorko/tools/review",
                                 "list --versions joshyorko/tools/review",
                                 "upgrade joshyorko/tools/review"])

    def test_source_preserves_retired_checkout_and_clones_current_upstream(self):
        result, calls = self.run_script("prepare-review-source.sh", '''
mkdir -p "$HOME/src/review/.git"
printf 'local work\\n' > "$HOME/src/review/local-file"
git() {
  printf '%s\\n' "$*" >> "$CALL_LOG"
  case "$*" in
    'remote get-url origin')
      if [ -f "$HOME/src/review/local-file" ]; then
        echo https://github.com/projectbluefin/review.git
      else
        echo https://github.com/joshyorko/review.git
      fi
      ;;
    'remote get-url upstream') return 1 ;;
    clone*) mkdir -p "${@: -1}/.git" ;;
    'show-ref --verify --quiet refs/heads/main') return 1 ;;
    'status --porcelain')
      if [ -f "$HOME/src/review/local-file" ]; then echo ' M local-file'; fi
      ;;
  esac
}
mv() {
  command mv "$@"
  if [[ "$1" == "$HOME/src/review" && -f "$2/local-file" ]]; then
    echo archived-local-file >> "$CALL_LOG"
  fi
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Preserved the previous Review checkout", result.stdout)
        self.assertIn("archived-local-file", calls)
        self.assertTrue(any(call.startswith("clone --branch main --single-branch https://github.com/joshyorko/review.git") for call in calls))
        self.assertIn("fetch upstream main", calls)
        self.assertFalse(any("reset" in call for call in calls))

    def test_source_migrates_unrelated_history_without_discarding_local_files(self):
        result, calls = self.run_script("prepare-review-source.sh", '''
mkdir -p "$HOME/src/review/.git"
printf 'uncommitted local file\\n' > "$HOME/src/review/local-file"
git() {
  printf '%s\\n' "$*" >> "$CALL_LOG"
  case "$*" in
    'remote get-url origin'|'remote get-url upstream')
      echo https://github.com/joshyorko/review.git
      ;;
    clone*) mkdir -p "${@: -1}/.git" ;;
    'merge-base HEAD upstream/main')
      if [ -f "$HOME/src/review/local-file" ]; then return 1; fi
      ;;
    'show-ref --verify --quiet refs/heads/main') return 1 ;;
    'status --porcelain')
      if [ -f "$HOME/src/review/local-file" ]; then echo ' M local-file'; fi
      ;;
  esac
}
mv() {
  command mv "$@"
  if [[ "$1" == "$HOME/src/review" && -f "$2/local-file" ]]; then
    echo archived-local-file >> "$CALL_LOG"
  fi
}
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("unrelated Git history", result.stdout)
        self.assertIn("archived-local-file", calls)
        self.assertTrue(any(call.startswith("clone --branch main --single-branch https://github.com/joshyorko/review.git") for call in calls))
        self.assertFalse(any("reset" in call for call in calls))

    def test_shared_omp_configuration_uses_current_launcher_variable(self):
        config = json.loads((ROOT / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(config["containerEnv"]["REVIEW_INHERIT_OMP_CONFIG"], "1")
        self.assertEqual(config["containerEnv"]["LUNA_FACTORY_ENABLED"], "1")
        self.assertEqual(config["containerEnv"]["LUNA_FACTORY_CAPACITY"], "3")
        self.assertNotIn("REVIEW_TEST_KVM_DEVICE", config["containerEnv"])
        self.assertFalse(any(key.startswith("BLUEFIN_") for key in config["containerEnv"]))
