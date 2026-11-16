# Automation VS Code integration verification

Published release: `automation-vscode-v2.20.29` (dogfood prerelease, not latest).
Release source: `69a6bb6a1ee457266e38f82208484c7891f0c8be`.

## Independently verified published bytes

The updater downloaded the public release checksum manifest
`automation-vscode-2.20.29-SHA256SUMS.txt` and Linux x64 VSIX on 2026-11-16.
The local SHA-256 matched the manifest, GitHub API asset digest, and release
owner's supplied digest:

```text
31778853e9966409a68baf03c8b14e74e7f719ed8928d0b76f19fd6a9d44dfd4  automation-vscode-2.20.29-linux-x64.vsix
```

Size: 2,229,630 bytes. ZIP inspection confirmed `extension/package.json` has
publisher `automation-control-plane`, name `automation-vscode`, version
`2.20.29`, and VS Code engine `^1.101.0`. `extension.vsixmanifest` independently
confirms that publisher/name/version and `TargetPlatform=linux-x64`.
The production staging helper successfully staged these real release bytes in
an isolated `/tmp` cache; no live editor installation was performed.

## Reproduce staging

```sh
AUTOMATION_VSCODE_CACHE_DIR="$(mktemp -d)" bash .devcontainer/scripts/stage-automation-vscode.sh
python3 -m unittest discover -s tests -p test_automation_vscode.py -v
python3 -m unittest discover -s tests -p test_josh_room.py -v
node --test tests/headroom-vscode.test.js
```

Seven Automation fixture tests cover idempotence, corrupt-cache repair,
missing/duplicate/mismatched checksums, failed downloads, private-release
fallback, unsupported architecture, both lifecycle paths, and exact editor
registration checks. Nineteen existing Josh Room tests and nine Headroom Node
tests passed. Shell syntax and `git diff --check` passed.

The full baseline suite before this change ran 63 tests: four failures, ten
errors, seven skips. Failures concern missing `yq` (three), a `/dev/kvm` fixture
assumption (one), and unavailable AF_UNIX sockets (ten). These environment
limitations were not changed or masked by this integration.

## Acceptance boundaries

No Work JATT container rebuild, deployment, Devsy installation, GUI activation,
or native backend execution was performed for this integration. Fixture editor
commands are mocks, not proof of installation. The released asset is Linux x64;
Wolfi/native-tool compatibility and GUI/debugger behavior remain unverified here.

The release owner reports qualified Windows native workloads and Linux
CLI/backend checks, with outer RCC 18.19.11, Actions Runtime 1.1.1, and Runtime's
separately bundled RCC 18.19.8. This does not establish Linux GUI qualification
or full canonical managed retry. No macOS or Marketplace assets are included.
Josh Room and the bundled Headroom extension remain independent. No user
secrets, persisted HOME volumes, runtime setup, or unrelated extensions changed.
