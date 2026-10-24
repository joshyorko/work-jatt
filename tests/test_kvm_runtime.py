"""Offline KVM contracts; these do not establish real VM availability."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class KvmRuntimeTests(unittest.TestCase):
    def test_devsy_requests_device_without_host_specific_gid(self):
        config = json.loads((ROOT / '.devcontainer/devcontainer.json').read_text())
        self.assertIn('--device=/dev/kvm', config['runArgs'])
        self.assertFalse(any(arg.startswith('--group-add=') for arg in config['runArgs']))
        self.assertTrue(config['privileged'])

    def probe(self, device='ready', runtime='krun'):
        with tempfile.TemporaryDirectory() as directory:
            guard = Path(directory) / 'guard.sh'
            guard.write_text('''[() {
  if [[ "$1" == '!' ]]; then shift; ! [ "$@"; return; fi
  if [[ "${2:-}" == /dev/kvm ]]; then
    case "$1:$DEVICE" in
      -c:missing|-c:regular|-r:denied|-w:denied) return 1 ;;
      *) return 0 ;;
    esac
  fi
  builtin [ "$@"
}
podman() {
  if [[ "$1" == info && "$*" != *--runtime=krun* ]]; then
    [[ "$RUNTIME" != unreachable ]]
  elif [[ "$RUNTIME" == missing ]]; then return 1
  else printf '%s\\n' "$RUNTIME"; fi
}
''')
            return subprocess.run(['bash', str(ROOT / '.devcontainer/scripts/check-kvm-runtime.sh')],
                                  env=dict(os.environ, BASH_ENV=str(guard), DEVICE=device, RUNTIME=runtime),
                                  text=True, capture_output=True)

    def test_ready_does_not_claim_vm_verified(self):
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('readable/writable character device', result.stdout)
        self.assertIn('krun: registered', result.stdout)
        self.assertIn('VM launch remains unverified', result.stdout)

    def test_device_failures_are_actionable_and_allow_fallback(self):
        for device, diagnostic in [('missing', '--device=/dev/kvm'),
                                   ('regular', '--device=/dev/kvm'), ('denied', 'group')]:
            with self.subTest(device=device):
                result = self.probe(device=device)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(diagnostic, result.stdout)
                self.assertNotIn('/dev/kvm: readable/writable', result.stdout)

    def test_runtime_failures_allow_fallback_without_claiming_ready(self):
        for runtime in ('missing', 'crun', 'unreachable'):
            with self.subTest(runtime=runtime):
                result = self.probe(runtime=runtime)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('WARNING', result.stdout)
                self.assertNotIn('krun: registered', result.stdout)

    def test_startup_calls_diagnostics(self):
        script = (ROOT / '.devcontainer/scripts/check-review-runtime.sh').read_text()
        self.assertIn('check-kvm-runtime.sh', script)
        self.assertNotIn("echo '/dev/kvm: READY'", script)
