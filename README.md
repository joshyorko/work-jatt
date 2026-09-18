# Work Jatt

## Josh Room extension

This repository runs in a dev container. The lifecycle hooks in
[.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) install the
Review tooling after the container is created and install Josh Room every time
the container starts.

The post-create hook delegates to named scripts in
[.devcontainer/scripts](.devcontainer/scripts), which install the Review
dependencies, prepare the upstream source checkout, build `fuse2fs` when it is
missing, and verify the runtime. The post-start hook runs
[.vscode/install-josh-room.sh](.vscode/install-josh-room.sh), which downloads
the pinned Josh Room VSIX from its GitHub release, verifies its SHA-256
checksum, and installs it into the running VS Code server via `code-insiders`
or `code`.

Josh Room is not on the Visual Studio Marketplace, so the
`customizations.vscode.extensions` property in `devcontainer.json` cannot
reference it; the lifecycle hook is the devcontainer-native way to install a
VSIX from a URL. To install or reinstall it manually, run:

    sh .vscode/install-josh-room.sh
