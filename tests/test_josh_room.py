"""Offline release-update checks. Run: python3 -m unittest discover -s tests -v."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b"test release VSIX"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


class JoshRoomUpdateTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest("Root uses the separate disposable-container ownership fixture; HOME alone cannot isolate root preparation.")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workspace with spaces"
        for folder in (".devcontainer", ".vscode"):
            shutil.copytree(ROOT / folder, self.root / folder)
        # Fixture checks must never bootstrap tools on the workstation.
        (self.root / ".devcontainer/scripts/bootstrap-review.sh").write_text(
            "#!/usr/bin/env bash\nexit 97\n")
        self.pin = self.root / ".devcontainer/josh-room.env"
        self.original_pin = self.pin.read_bytes()
        self.cache = self.root / "cache"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        guard = self.root / "shell-guard.sh"
        # Bootstrap sets its own PATH; a Bash function still blocks host brew.
        guard.write_text('''brew() {
  echo 'ERROR: fixture refused host Homebrew execution.' >&2
  return 97
}
''')
        self.env = dict(os.environ, JOSH_ROOM_CACHE_DIR=str(self.cache),
                HOME=str(self.home), BASH_ENV=str(guard),
                PATH=f"{self.bin}:{os.environ['PATH']}",
                TEST_DIGEST=DIGEST, TEST_PAYLOAD=PAYLOAD.decode(),
                TEST_VERSION="0.1.99", TEST_LATEST_VERSION="0.1.99")
        # Never fall through to a real host editor when a fixture CLI fails.
        for name in ("code-insiders", "code"):
            self.install_fixture(name, "exit 1")
        curl = self.bin / "curl"
        curl.write_text('''#!/usr/bin/env bash
set -euo pipefail
for arg in "$@"; do
  if [[ "$arg" == */releases/latest ]]; then
    printf 'https://github.com/joshyorko/josh-room/releases/tag/v%s-standalone-vsix' "$TEST_LATEST_VERSION"
    exit 0
  fi
  if [[ "$arg" == */SHA256SUMS ]]; then
    printf '%s  josh-room-%s.vsix\\n' "$TEST_DIGEST" "$TEST_VERSION"
    exit 0
  fi
done
while [ "$#" -gt 0 ]; do
  if [ "$1" = --output ]; then
    printf '%s' "$TEST_PAYLOAD" > "$2"
    exit 0
  fi
  shift
done
exit 22
''')
        curl.chmod(0o755)

    def run_script(self, script, *args):
        return subprocess.run(["bash", str(self.root / script), *args],
                              env=self.env, capture_output=True, text=True)

    def update(self, *args):
        return self.run_script(".vscode/update-josh-room.sh", *args)

    def test_release_checksum_discovery_and_idempotent_staging(self):
        result = self.update("v0.1.99-standalone-vsix")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('VERSION="0.1.99"', self.pin.read_text())
        stable = self.cache / "josh-room.vsix"
        self.assertEqual(stable.read_bytes(), PAYLOAD)
        # A valid version cache must repair the stable file without downloading.
        stable.write_bytes(b"corrupt")
        (self.bin / "curl").write_text("#!/usr/bin/env bash\nexit 99\n")
        result = self.run_script(".devcontainer/scripts/stage-josh-room.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stable.read_bytes(), PAYLOAD)

    def test_no_version_selects_latest_release(self):
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('VERSION="0.1.99"', self.pin.read_text())
        self.assertEqual((self.cache / "josh-room-0.1.99.vsix").read_bytes(), PAYLOAD)

    def test_explicit_checksum_and_corrupt_cache_repair(self):
        self.cache.mkdir()
        (self.cache / "josh-room-0.1.99.vsix").write_bytes(b"corrupt")
        result = self.update("0.1.99", DIGEST)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.cache / "josh-room-0.1.99.vsix").read_bytes(), PAYLOAD)

    def test_checksum_mismatch_preserves_pin_and_staged_extension(self):
        self.cache.mkdir()
        stable = self.cache / "josh-room.vsix"
        stable.write_bytes(b"previous release")
        result = self.update("0.1.99", "0" * 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checksum verification failed", result.stderr)
        self.assertEqual(self.pin.read_bytes(), self.original_pin)
        self.assertEqual(stable.read_bytes(), b"previous release")
        self.assertFalse((self.cache / "josh-room-0.1.99.vsix").exists())
        self.assertFalse(list(self.pin.parent.glob("josh-room.env.*")))
        self.assertFalse(list(self.cache.glob(".josh-room-*")))

    def test_missing_release_checksum_preserves_pin(self):
        self.env["TEST_DIGEST"] = ""
        result = self.update("0.1.99")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.pin.read_bytes(), self.original_pin)

    def test_invalid_version_preserves_pin(self):
        result = self.update("../../invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.pin.read_bytes(), self.original_pin)

    def test_ready_runtime_stages_extension_on_start(self):
        result = self.update("0.1.99", DIGEST)
        self.assertEqual(result.returncode, 0, result.stderr)
        stable = self.cache / "josh-room.vsix"
        stable.unlink()
        check = self.root / ".devcontainer/scripts/check-review-runtime.sh"
        check.write_text("#!/usr/bin/env bash\nexit 0\n")
        result = self.run_script(".devcontainer/scripts/ensure-review-runtime.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".vscode-server/extensions").is_dir())
        self.assertTrue((self.home / ".vscode-server-insiders/extensions").is_dir())
        self.assertEqual(stable.read_bytes(), PAYLOAD)

    def test_missing_devcontainer_environment_leaves_home_untouched(self):
        self.env.pop("DEV_CONTAINERS_SKIP_GCOMPAT_INSTALL", None)
        token = self.home / ".token"
        token.write_text("existing token")
        before = token.stat()
        (self.root / ".devcontainer/scripts/bootstrap-review.sh").write_text('''#!/usr/bin/env bash
touch "$HOME/bootstrap-called"
exit 97
''')
        result = self.run_script(".devcontainer/scripts/ensure-review-runtime.sh")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(list(self.home.iterdir()), [token])
        self.assertEqual(token.stat(), before)
        self.assertEqual(token.read_text(), "existing token")

    def test_installer_uses_shared_pin_and_verified_asset(self):
        result = self.update("0.1.99", DIGEST)
        self.assertEqual(result.returncode, 0, result.stderr)
        code = self.bin / "code-insiders"
        code.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [ "$1" = --list-extensions ]; then
  cat "$HOME/installed-extension" 2>/dev/null || true
else
  test "$1" = --install-extension
  test "$2" = "$JOSH_ROOM_CACHE_DIR/josh-room-0.1.99.vsix"
  test "$3" = --force
  test -f "$2"
  echo 'joshyorko.josh-room@0.1.99' > "$HOME/installed-extension"
fi
''')
        code.chmod(0o755)
        shutil.copy2(code, self.bin / "code")
        result = self.run_script(".vscode/install-josh-room.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Installed Josh Room 0.1.99", result.stdout)

    def install_fixture(self, name, install_body):
        code = self.bin / name
        code.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [ "$1" = --list-extensions ]; then
  cat "$HOME/registry-''' + name + '''" 2>/dev/null || true
else
''' + install_body + '\nfi\n')
        code.chmod(0o755)

    def test_installer_rejects_exit_zero_without_registered_version(self):
        self.assertEqual(self.update("0.1.99", DIGEST).returncode, 0)
        for name in ("code-insiders", "code"):
            self.install_fixture(name, "echo 'EACCES: permission denied, stat extensions.json' >&2")
        result = self.run_script(".vscode/install-josh-room.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Installed Josh Room", result.stdout)

    def test_installer_falls_back_after_unverified_success(self):
        self.assertEqual(self.update("0.1.99", DIGEST).returncode, 0)
        self.install_fixture("code-insiders", "echo 'EACCES' >&2")
        self.install_fixture("code", "echo 'joshyorko.josh-room@0.1.99' > \"$HOME/registry-code\"")
        result = self.run_script(".vscode/install-josh-room.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("using code.", result.stdout)
        self.assertNotIn("using code-insiders.", result.stdout)

    def test_installer_rejects_wrong_registered_version(self):
        self.assertEqual(self.update("0.1.99", DIGEST).returncode, 0)
        for name in ("code-insiders", "code"):
            self.install_fixture(name, "echo 'joshyorko.josh-room@0.1.98' > \"$HOME/registry-" + name + "\"")
        result = self.run_script(".vscode/install-josh-room.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Installed Josh Room", result.stdout)

    def test_installer_rejects_failed_list_even_with_matching_output(self):
        self.assertEqual(self.update("0.1.99", DIGEST).returncode, 0)
        for name in ("code-insiders", "code"):
            code = self.bin / name
            code.write_text('''#!/usr/bin/env bash
if [ "$1" = --list-extensions ]; then
  echo 'joshyorko.josh-room@0.1.99'
  exit 1
fi
exit 0
''')
        result = self.run_script(".vscode/install-josh-room.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("already installed", result.stdout)
        self.assertNotIn("Installed Josh Room", result.stdout)

    def test_extension_preparation_is_idempotent_and_preserves_private_modes(self):
        extensions = self.home / ".vscode-server-insiders/extensions"
        extensions.mkdir(parents=True, mode=0o700)
        registry = extensions / "extensions.json"
        registry.write_text("[]")
        registry.chmod(0o600)
        outside = self.home / "unrelated"
        outside.write_text("untouched")
        before = outside.stat()
        for _ in range(2):
            result = self.run_script(".devcontainer/scripts/prepare-vscode-extensions.sh")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / ".vscode-server/extensions").is_dir())
        self.assertEqual(extensions.stat().st_mode & 0o777, 0o700)
        self.assertEqual(registry.stat().st_mode & 0o777, 0o600)
        self.assertEqual(registry.read_text(), "[]")
        self.assertEqual(outside.stat(), before)

    def test_extension_preparation_refuses_symlinked_server_or_extensions(self):
        outside = self.root / "outside"
        outside.mkdir()
        for level in ("server", "extensions"):
            with self.subTest(level=level):
                server = self.home / ".vscode-server"
                if level == "server":
                    server.symlink_to(outside, target_is_directory=True)
                else:
                    server.mkdir()
                    (server / "extensions").symlink_to(outside, target_is_directory=True)
                before = outside.stat()
                result = self.run_script(".devcontainer/scripts/prepare-vscode-extensions.sh")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing symlinked", result.stderr)
                self.assertEqual(outside.stat(), before)
                self.assertEqual(list(outside.iterdir()), [])
                if level == "server":
                    server.unlink()

    def test_extension_preparation_does_not_follow_nested_symlink(self):
        extensions = self.home / ".vscode-server-insiders/extensions"
        extensions.mkdir(parents=True)
        outside = self.root / "outside"
        outside.write_text("untouched")
        (extensions / "linked").symlink_to(outside)
        before = outside.stat()
        result = self.run_script(".devcontainer/scripts/prepare-vscode-extensions.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outside.stat(), before)

    def test_installer_prepares_extension_directories(self):
        self.assertEqual(self.update("0.1.99", DIGEST).returncode, 0)
        self.install_fixture("code-insiders", '''test -d "$HOME/.vscode-server/extensions"
test -d "$HOME/.vscode-server-insiders/extensions"
echo 'joshyorko.josh-room@0.1.99' > "$HOME/registry-code-insiders"''')
        result = self.run_script(".vscode/install-josh-room.sh")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bootstrap_prepares_extension_directories_before_tool_setup(self):
        scripts = self.root / ".devcontainer/scripts"
        shutil.copy2(ROOT / ".devcontainer/scripts/bootstrap-review.sh",
                     scripts / "bootstrap-review.sh")
        for name in ("install-review-package", "prepare-review-source", "build-fuse2fs",
                     "configure-omp-headroom", "check-review-runtime"):
            (scripts / f"{name}.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
        (scripts / "install-review-tools.sh").write_text('''#!/usr/bin/env bash
test -d "$HOME/.vscode-server/extensions" &&
test -d "$HOME/.vscode-server-insiders/extensions"
''')
        self.assertEqual(self.update("0.1.99", DIGEST).returncode, 0)
        result = self.run_script(".devcontainer/scripts/bootstrap-review.sh")
        self.assertEqual(result.returncode, 0, result.stderr)


class FixtureIsolationTests(unittest.TestCase):
    def test_root_fixture_suite_skips_before_filesystem_or_subprocess_actions(self):
        case = JoshRoomUpdateTests("test_release_checksum_discovery_and_idempotent_staging")
        with mock.patch("os.geteuid", return_value=0), \
                mock.patch("tempfile.TemporaryDirectory", side_effect=AssertionError("root setup must stop")), \
                mock.patch("subprocess.run", side_effect=AssertionError("root subprocess forbidden")):
            result = case.run()
        self.assertFalse(result.errors)
        self.assertFalse(result.failures)
        self.assertEqual(len(result.skipped), 1)
