"""Offline setup checks; never install tools or change the operator's home."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from xml.etree import ElementTree
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class HeadroomExtensionPackageTests(unittest.TestCase):
    def test_staging_produces_installable_deterministic_vsix_and_refreshes_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / ".vscode/headroom", root / ".vscode/headroom")
            scripts = root / ".devcontainer/scripts"
            scripts.mkdir(parents=True)
            shutil.copy2(ROOT / ".devcontainer/scripts/stage-headroom-extension.py", scripts)
            cache = root / "cache"
            env = dict(os.environ, HOME=str(root), HEADROOM_VSIX_CACHE_DIR=str(cache))

            def stage():
                subprocess.run(["python3", str(scripts / "stage-headroom-extension.py")],
                               env=env, check=True, capture_output=True)

            stage()
            target = cache / "work-jatt-headroom.vsix"
            original = target.read_bytes()
            modified_at = target.stat().st_mtime_ns
            with zipfile.ZipFile(target) as archive:
                package = json.loads(archive.read("extension/package.json"))
                self.assertEqual(package["extensionKind"], ["workspace"])
                self.assertFalse(package["capabilities"]["untrustedWorkspaces"]["supported"])
                self.assertEqual(archive.read("extension/extension.js"), (root / ".vscode/headroom/extension.js").read_bytes())
                ElementTree.fromstring(archive.read("extension.vsixmanifest"))
                ElementTree.fromstring(archive.read("[Content_Types].xml"))
            stage()
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(target.stat().st_mtime_ns, modified_at)
            source = root / ".vscode/headroom/extension.js"
            source.write_text(source.read_text() + "\n// fixture source change\n")
            stage()
            self.assertNotEqual(target.read_bytes(), original)


@unittest.skipUnless(shutil.which("yq"), "Mike Farah yq is required")
class HeadroomSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home with spaces"
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("HEADROOM_", "CODEX_")) and k != "BASH_ENV"}
        self.env.update(HOME=str(self.home), HEADROOM_BASE_URL="http://proxy.test/v1")
        self.codex = self.home / ".codex/config.toml"
        self.omp = self.home / ".omp/profiles/review/agent/models.yml"

    def run_setup(self, *args, token=None, input=None):
        env = dict(self.env)
        if token is not None:
            env["HEADROOM_PROXY_TOKEN"] = token
        return subprocess.run(["bash", str(ROOT / ".devcontainer/scripts/configure-headroom.sh"), *args],
                              env=env, input=input, capture_output=True, text=True)

    def read_omp(self):
        result = subprocess.run(["yq", "-o=json", ".", str(self.omp)],
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_environment_token_configures_both_clients_privately(self):
        token = "fixture-proxy-token"
        result = self.run_setup(token=token)
        self.assertEqual(result.returncode, 0, result.stderr)
        config = tomllib.loads(self.codex.read_text())
        self.assertEqual(config["model_provider"], "headroom")
        provider = config["model_providers"]["headroom"]
        self.assertEqual(provider["base_url"], self.env["HEADROOM_BASE_URL"])
        self.assertTrue(provider["requires_openai_auth"])
        self.assertEqual(provider["wire_api"], "responses")
        self.assertEqual(provider["http_headers"]["X-Headroom-Proxy-Token"], token)
        omp = self.read_omp()["providers"]["openai-codex"]
        self.assertEqual(omp["headers"]["X-Headroom-Proxy-Token"], token)
        self.assertEqual(omp["baseUrl"], self.env["HEADROOM_BASE_URL"])
        for path in (self.codex, self.omp):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(token, result.stdout + result.stderr)

    def test_rerun_reuses_saved_token_and_preserves_other_settings_and_auth(self):
        self.codex.parent.mkdir()
        self.codex.write_text('model = "chosen-model"\n[model_providers.other]\nname = "Other"\n')
        auth = self.codex.parent / "auth.json"
        auth.write_text('{"fixture": "unchanged"}')
        self.omp.parent.mkdir(parents=True)
        self.omp.write_text('providers:\n  other:\n    baseUrl: https://other.test\n')
        self.assertEqual(self.run_setup(token="saved-token").returncode, 0)
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = tomllib.loads(self.codex.read_text())
        self.assertEqual(config["model"], "chosen-model")
        self.assertEqual(config["model_providers"]["other"]["name"], "Other")
        self.assertEqual(config["model_providers"]["headroom"]["http_headers"]["X-Headroom-Proxy-Token"], "saved-token")
        self.assertEqual(self.read_omp()["providers"]["other"]["baseUrl"], "https://other.test")
        self.assertEqual(auth.read_text(), '{"fixture": "unchanged"}')

    def test_missing_token_leaves_configuration_untouched_and_explains_setup(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VS Code", result.stdout + result.stderr)
        self.assertIn("not configured", (result.stdout + result.stderr).lower())
        self.assertFalse(self.codex.exists())
        self.assertFalse(self.omp.exists())

    def test_prompt_rotates_saved_token_without_echoing_it(self):
        self.assertEqual(self.run_setup(token="previous-token").returncode, 0)
        result = self.run_setup("--prompt", input="replacement-token\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("replacement-token", result.stdout + result.stderr)
        self.assertEqual(self.read_omp()["providers"]["openai-codex"]["headers"]["X-Headroom-Proxy-Token"], "replacement-token")

    def test_injected_token_overrides_saved_token_without_evaluating_shell_text(self):
        self.assertEqual(self.run_setup(token="previous-token").returncode, 0)
        token = "literal-'\"$(touch should-not-exist)"
        result = self.run_setup(token=token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_omp()["providers"]["openai-codex"]["headers"]["X-Headroom-Proxy-Token"], token)
        self.assertFalse((ROOT / "should-not-exist").exists())
        self.assertNotIn(token, result.stdout + result.stderr)

    def test_bad_configs_and_invalid_tokens_preserve_existing_files(self):
        self.assertEqual(self.run_setup(token="saved-token").returncode, 0)
        for bad_token in ("", "line\rbreak", "!unsafe-command"):
            with self.subTest(token_kind=repr(bad_token)):
                before = (self.codex.read_bytes(), self.omp.read_bytes())
                result = self.run_setup("--prompt", input=bad_token + "\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.codex.read_bytes(), self.omp.read_bytes()), before)
        for path in (self.codex, self.omp):
            with self.subTest(config=path.name):
                original = path.read_bytes()
                path.write_text('broken = [\n' if path == self.codex else 'providers: [\n')
                before = (self.codex.read_bytes(), self.omp.read_bytes())
                result = self.run_setup(token="replacement-token")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.codex.read_bytes(), self.omp.read_bytes()), before)
                self.assertNotIn("replacement-token", result.stdout + result.stderr)
                path.write_bytes(original)


class CodexInstallerTests(unittest.TestCase):
    def test_tool_setup_runs_noninteractive_official_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guard = root / "guard.sh"
            guard.write_text('''brew() { return 0; }
curl() {
  test "$*" = '-fsSL https://chatgpt.com/codex/install.sh' || return 94
  printf '%s\\n' 'test "$CODEX_NON_INTERACTIVE" = 1' 'touch "$HOME/installer-ran"'
}
''')
            env = dict(os.environ, HOME=str(root), BASH_ENV=str(guard))
            result = subprocess.run(["bash", str(ROOT / ".devcontainer/scripts/install-review-tools.sh")],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "installer-ran").exists())

    def test_failed_installer_download_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guard = root / "guard.sh"
            guard.write_text('brew() { return 0; }\ncurl() { return 22; }\n')
            env = dict(os.environ, HOME=str(root), BASH_ENV=str(guard))
            result = subprocess.run(["bash", str(ROOT / ".devcontainer/scripts/install-review-tools.sh")],
                                    env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


class RuntimeChecksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        guard = self.home / "guard.sh"
        guard.write_text('''git() { echo 'unexpected Git dependency' >&2; return 99; }
brew() { test "$*" = "list --versions joshyorko/tools/review"; }
apptainer() { return 0; }
squashfuse() { return 0; }
gocryptfs() { return 0; }
fuse2fs() { return 0; }
review() { return 0; }
gh() { return 0; }
''')
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("HEADROOM_", "CODEX_"))}
        self.env.update(HOME=str(self.home), BASH_ENV=str(guard),
                        DEV_CONTAINERS_SKIP_GCOMPAT_INSTALL="true", HOMEBREW_NO_ANALYTICS="1",
                        REVIEW_INHERIT_OMP_CONFIG="1",
                        HEADROOM_BASE_URL="http://proxy.test/v1", LUNA_FACTORY_ENABLED="0",
                        LUNA_FACTORY_CAPACITY="3")
        self.managed = self.home / ".codex/packages/standalone/current/bin/codex"
        self.launcher = self.home / ".local/bin/codex"
        self.managed.parent.mkdir(parents=True)
        self.launcher.parent.mkdir(parents=True)
        self.managed.write_text('#!/bin/sh\necho "codex fixture"\n')
        self.managed.chmod(0o755)
        self.launcher.symlink_to(self.managed)

    def run_check(self):
        return subprocess.run(["bash", str(ROOT / ".devcontainer/scripts/check-review-runtime.sh")],
                              env=self.env, capture_output=True, text=True)

    def test_missing_token_keeps_ide_available_without_claiming_headroom_ready(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not configured", result.stdout)
        self.assertIn("Run: review owner/repo", result.stdout)
        self.assertNotIn("Headroom headers: configured", result.stdout)

    def test_runtime_passes_without_review_source_checkout(self):
        self.assertFalse((self.home / "src/review").exists())
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Review source", result.stdout)

    def test_unmanaged_codex_does_not_pass_runtime_check(self):
        self.launcher.unlink()
        self.launcher.write_text('#!/bin/sh\necho "unmanaged fixture"\n')
        self.launcher.chmod(0o755)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("standalone installation is missing", result.stderr)

    @unittest.skipUnless(shutil.which("yq"), "Mike Farah yq is required")
    def test_configured_headers_are_reported_without_values_or_connectivity_claim(self):
        env = dict(self.env, HEADROOM_PROXY_TOKEN="runtime-fixture-token")
        setup = subprocess.run(["bash", str(ROOT / ".devcontainer/scripts/configure-headroom.sh")],
                               env=env, capture_output=True, text=True)
        self.assertEqual(setup.returncode, 0, setup.stderr)
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Headroom headers: configured", result.stdout)
        self.assertIn("connectivity not tested", result.stdout)
        self.assertNotIn("runtime-fixture-token", result.stdout + result.stderr)
