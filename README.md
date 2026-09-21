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

The bootstrap invokes each setup script through `/bin/bash`, so the lifecycle
does not depend on executable bits being preserved by the workspace checkout.
The runtime setup installs `gh`, `apptainer`, `squashfuse`, and `gocryptfs`, and
the final check reports a clear error if a required command is still missing.
Review inherits the shared OMP configuration, while the optional Headroom
provider setup remains documented in `configure-omp-headroom.sh` and disabled.

The source updater is safe to rerun: it refuses to touch a checkout with local
changes or a branch that has diverged from upstream instead of force-resetting
it. The Homebrew prefix remains part of the image rather than the persistent
`/home/vscode` volume, so a container rebuild may reinstall Homebrew packages.

Josh Room is not on the Visual Studio Marketplace, so the
`customizations.vscode.extensions` property in `devcontainer.json` cannot
reference it; the lifecycle hook is the devcontainer-native way to install a
VSIX from a URL. To install or reinstall it manually, run:

    sh .vscode/install-josh-room.sh
