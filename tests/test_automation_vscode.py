"""Offline fixture coverage; no live extension installation or host bootstrap."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b'fixture automation VSIX'
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
TAG = 'automation-vscode-v9.8.7'
ASSET = 'automation-vscode-9.8.7-linux-x64.vsix'


class AutomationTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest('Extension preparation must not run as root on the host.')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace with spaces'
        for folder in ('.devcontainer', '.vscode'):
            shutil.copytree(ROOT / folder, self.root / folder)
        self.scripts = self.root / '.devcontainer/scripts'
        self.pin = self.root / '.devcontainer/automation-vscode.env'
        self.original = self.pin.read_bytes()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.cache = self.home / '.cache/automation-vscode'
        self.cache.mkdir(parents=True)
        self.stable = self.cache / 'automation-vscode.vsix'
        self.versioned = self.cache / ASSET
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # Replace every unrelated lifecycle child before any lifecycle invocation.
        for name in ('install-review-tools', 'install-review-package', 'build-fuse2fs',
                     'configure-headroom', 'check-review-runtime', 'stage-josh-room'):
            (self.scripts / (name + '.sh')).write_text('#!/bin/bash\nexit 0\n')
        guard = self.root / 'guard.sh'
        guard.write_text('''brew() { echo 'Host brew forbidden' >&2; return 97; }
curl() { "$FIXTURE_BIN/curl" "$@"; }
gh() { "$FIXTURE_BIN/gh" "$@"; }
uname() { if [[ "$1" == -s ]]; then echo Linux; else echo "${TEST_ARCH:-x86_64}"; fi; }
''')
        self.env = dict(PATH=f'{self.bin}:/usr/bin:/bin', HOME=str(self.home),
                        BASH_ENV=str(guard), FIXTURE_BIN=str(self.bin),
                        TEST_DIGEST=DIGEST, TEST_ASSET=ASSET,
                        TEST_PAYLOAD=PAYLOAD.decode())
        self.fixture('curl', '''[[ "${TEST_CURL_FAIL:-0}" != 1 ]] || exit 22
for arg in "$@"; do url="$arg"; done
while [[ "$1" != --output ]]; do shift; done
output="$2"
if [[ "$url" == */CHECKSUMS.txt ]]; then
  printf '%s  %s\\n' "$TEST_DIGEST" "$TEST_ASSET" > "$output"
else
  [[ "${TEST_DOWNLOAD_FAIL:-0}" != 1 ]] || exit 22
  printf '%s' "$TEST_PAYLOAD" > "$output"
fi
''')
        self.fixture('gh', 'exit 99')
        for name in ('code', 'code-insiders'):
            self.fixture(name, 'exit 1')

    def fixture(self, name, body):
        p = self.bin / name
        p.write_text('#!/bin/bash\nset -euo pipefail\n' + body + '\n')
        p.chmod(0o755)

    def run_script(self, relative, *args):
        return subprocess.run(['/bin/bash', str(self.root / relative), *args],
                              env=self.env, text=True, capture_output=True)

    def update(self):
        return self.run_script('.vscode/update-automation-vscode.sh', TAG, 'CHECKSUMS.txt')

    def stage(self):
        return self.run_script('.devcontainer/scripts/stage-automation-vscode.sh')

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_verified_stage_idempotent_and_repair(self):
        self.assert_ok(self.update())
        self.assertEqual(self.stable.read_bytes(), PAYLOAD)
        self.assertIn(DIGEST, self.pin.read_text())
        before = self.stable.stat().st_mtime_ns
        self.env['TEST_CURL_FAIL'] = '1'
        self.assert_ok(self.stage())
        self.assertEqual(before, self.stable.stat().st_mtime_ns)
        self.stable.write_bytes(b'corrupt stable')
        self.assert_ok(self.stage())
        self.assertEqual(self.stable.read_bytes(), PAYLOAD)
        self.env.pop('TEST_CURL_FAIL')
        self.versioned.write_bytes(b'corrupt version')
        self.assert_ok(self.stage())
        self.assertEqual(self.versioned.read_bytes(), PAYLOAD)

    def test_failures_preserve_pin_and_both_caches(self):
        for env in ({'TEST_DIGEST': ''}, {'TEST_ASSET': 'other.vsix'},
                    {'TEST_DIGEST': '0' * 64}, {'TEST_DOWNLOAD_FAIL': '1'},
                    {'TEST_CURL_FAIL': '1'}, {'TEST_ARCH': 'aarch64'},
                    {'TEST_DIGEST': DIGEST + '  ' + ASSET + '\n' + DIGEST}):
            with self.subTest(env=env):
                previous = self.env.copy()
                self.env.update(env)
                self.stable.write_bytes(b'previous stable')
                self.versioned.write_bytes(b'previous cache')
                result = self.update()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.pin.read_bytes(), self.original)
                self.assertEqual(self.stable.read_bytes(), b'previous stable')
                self.assertEqual(self.versioned.read_bytes(), b'previous cache')
                self.assertFalse(list(self.cache.glob('.automation-*')))
                self.assertFalse(list(self.pin.parent.glob('automation-vscode.env.*')))
                self.env = previous

    def test_private_release_uses_existing_gh_auth(self):
        self.env['TEST_CURL_FAIL'] = '1'
        self.fixture('gh', '''test "$GH_PROMPT_DISABLED" = 1
test "$1 $2 $3" = "release download automation-vscode-v9.8.7"
test "$4 $5" = "--repo automation-control-plane/automation-vscode"
test "$6" = --pattern
test "$8" = --dir
if [[ "$7" == CHECKSUMS.txt ]]; then
  printf '%s  %s\\n' "$TEST_DIGEST" "$TEST_ASSET" > "$9/$7"
else
  printf '%s' "$TEST_PAYLOAD" > "$9/$7"
fi''')
        self.assert_ok(self.update())
        self.assertEqual(self.stable.read_bytes(), PAYLOAD)

    def test_unpublished_pin_fails_without_touching_cache(self):
        self.pin.write_text('VERSION=\"\"\nTAG=\"\"\nASSET=\"\"\nEXPECTED_SHA256=\"\"\n')
        self.stable.write_bytes(b'previous')
        result = self.stage()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('verified published', result.stderr)
        self.assertEqual(self.stable.read_bytes(), b'previous')

    def test_both_lifecycle_paths_stage_and_preserve_headroom(self):
        self.assert_ok(self.update())
        for name in ('bootstrap-review.sh', 'ensure-review-runtime.sh'):
            with self.subTest(path=name):
                self.stable.unlink()
                self.assert_ok(self.run_script('.devcontainer/scripts/' + name))
                self.assertEqual(self.stable.read_bytes(), PAYLOAD)
                self.assertTrue((self.home / '.cache/headroom/work-jatt-headroom.vsix').is_file())
        config = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
        self.assertIn('/home/vscode/.cache/automation-vscode/automation-vscode.vsix',
                      config['customizations']['vscode']['extensions'])
        self.assertIn('/home/vscode/.cache/josh-room/josh-room.vsix',
                      config['customizations']['vscode']['extensions'])

    def test_installer_requires_exact_registered_version_and_falls_back(self):
        self.assert_ok(self.update())
        self.fixture('code-insiders', 'echo "automation-control-plane.automation-vscode@0.0.1"')
        result = self.run_script('.vscode/install-automation-vscode.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Installed Automation', result.stdout)
        self.fixture('code', '''if [[ "$1" == --list-extensions ]]; then
  cat "$HOME/registry" 2>/dev/null || true
else
  test "$1" = --install-extension
  test "$2" = "$HOME/.cache/automation-vscode/$TEST_ASSET"
  test "$3" = --force
  echo 'automation-control-plane.automation-vscode@9.8.7' > "$HOME/registry"
fi''')
        result = self.run_script('.vscode/install-automation-vscode.sh')
        self.assert_ok(result)
        self.assertIn('using code.', result.stdout)
        result = self.run_script('.vscode/install-automation-vscode.sh')
        self.assert_ok(result)
        self.assertIn('already installed', result.stdout)

    def test_installer_rejects_failed_listing_with_matching_output(self):
        self.assert_ok(self.update())
        for name in ('code', 'code-insiders'):
            self.fixture(name, '''if [[ "$1" == --list-extensions ]]; then
  echo 'automation-control-plane.automation-vscode@9.8.7'; exit 1
fi''')
        self.assertNotEqual(self.run_script('.vscode/install-automation-vscode.sh').returncode, 0)
