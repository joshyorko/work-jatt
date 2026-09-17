# Work Jatt

## Josh Room extension

This repository runs in a dev container. Every time the container starts, the
`postStartCommand` in [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json)
runs [.vscode/install-josh-room.sh](.vscode/install-josh-room.sh), which
downloads the Josh Room VSIX from the GitHub release and installs it into the
running VS Code Insiders server via `code-insiders`.

The installer pins the exact tested release
[`v0.1.24-standalone-vsix`](https://github.com/joshyorko/josh-room/releases/tag/v0.1.24-standalone-vsix),
verifies its SHA-256 checksum before installing, and skips the install when
that version is already present. To update Josh Room later, bump `VERSION`
and `EXPECTED_SHA256` in the script to the newest release values.

Josh Room is not on the Visual Studio Marketplace, so the
`customizations.vscode.extensions` property in `devcontainer.json` cannot
reference it; a lifecycle command is the devcontainer-native way to install a
VSIX from a URL. To install or reinstall manually, run:

    sh .vscode/install-josh-room.sh
