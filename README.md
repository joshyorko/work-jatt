# Work Jatt

## Josh Room extension

This repository runs in a dev container. The lifecycle hooks in
[.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) install the
Review tooling after the container is created, verify or repair the runtime each
time the container starts, and stage Josh Room before Devsy configures the IDE.
Devsy then installs the staged VSIX through its VS Code customization lifecycle.

The post-create hook delegates to named scripts in
[.devcontainer/scripts](.devcontainer/scripts), which install the Review
dependencies, prepare the upstream source checkout, build `fuse2fs` when it is
missing, and verify the runtime. The post-start hook runs
[.devcontainer/scripts/ensure-review-runtime.sh](.devcontainer/scripts/ensure-review-runtime.sh),
which verifies the runtime and reruns the bootstrap only when required state is
missing. The bootstrap also runs
[.devcontainer/scripts/stage-josh-room.sh](.devcontainer/scripts/stage-josh-room.sh),
which downloads the pinned Josh Room VSIX from its GitHub release, verifies its
SHA-256 checksum, and stores it at
`/home/vscode/.cache/josh-room/josh-room.vsix`. The
`customizations.vscode.extensions` entry points Devsy at that stable path, so
extension installation happens only after the VS Code server is available.

The version and SHA-256 checksum live in
[.devcontainer/josh-room.env](.devcontainer/josh-room.env). To update to the
latest published release, run from the repository root on the host or inside
the devcontainer:

    bash .vscode/update-josh-room.sh

To pin a specific release instead, pass its version:

    bash .vscode/update-josh-room.sh 0.1.35

The updater reads the release's `SHA256SUMS`, downloads and verifies the VSIX,
and only then changes the pin. You can also pass a known SHA-256 as the second
argument. The devcontainer extension path stays the same across releases. The
current pin is Josh Room 0.1.35.
Staging uses the current user's `~/.cache/josh-room`; set
`JOSH_ROOM_CACHE_DIR` to override it.

The bootstrap invokes each setup script through `/bin/bash`, so the lifecycle
does not depend on executable bits being preserved by the workspace checkout.
The runtime setup installs `gh`, `apptainer`, `squashfuse`, `gocryptfs`, `yq`, and Python 3, and
the final check reports a clear error if a required command is still missing.
The stable Review package is installed or upgraded from the
`joshyorko/tools/review` Homebrew formula.
Run `review owner/repo` with an explicit GitHub repository scope, or
`review org:your-org` for an organization. The source checkout tracks
[`joshyorko/review`](https://github.com/joshyorko/review) on `main`.
Review inherits the shared OMP configuration and configures the Headroom provider
through `configure-headroom.sh`. The bootstrap also installs Codex using
[OpenAI's standalone installer](https://learn.chatgpt.com/docs/codex/cli),
noninteractively, into the persistent home volume. Startup verifies the managed
binary and launcher, so a preinstalled Homebrew or npm Codex does not satisfy
that check. New IDE terminals prefer `~/.local/bin`.

The source updater is safe to rerun: compatible checkouts with local changes or
diverged branches are left untouched. A checkout with an incompatible remote
or unrelated Git history is preserved beside the source directory before a
clean checkout of `joshyorko/review` is installed. It never force-resets or
discards local work. The Homebrew prefix remains part of the image rather than
the persistent `/home/vscode` volume, so a container rebuild may reinstall
Homebrew packages.

Josh Room is not on the Visual Studio Marketplace, so the
extension is staged locally rather than referenced by a Marketplace ID. To
install or reinstall it manually after attaching to VS Code, run:

    sh .vscode/install-josh-room.sh

Run the install command inside the attached devcontainer to update its
extension, or on the host to update the host's VS Code installation.
Reload the VS Code window after installation to load the new version.

The `$schema` entry in `devcontainer.json` points to
`.vscode/devsy-devcontainer.schema.json`. The standard Dev Container schema
only accepts Marketplace extension IDs, while Devsy also accepts the staged
VSIX filesystem path used here.

## Headroom authentication

Headroom now requires `X-Headroom-Proxy-Token` in addition to each client's
OpenAI login. Setup configures the existing `HEADROOM_BASE_URL` for both Codex
and Review's shared OMP profile. It does not log in to OpenAI for you.

Connect to the workspace with VS Code. The bundled Headroom setup extension
opens a masked input box the first time; paste the proxy token there. It saves
the token in [VS Code SecretStorage](https://code.visualstudio.com/api/references/vscode-api#SecretStorage)
and passes it directly to the setup helper running inside the connected
container. No host terminal or Devsy secret commands are needed.

When the token changes, open the Command Palette (`Ctrl+Shift+P`), choose
**Headroom: Update Proxy Token**, and paste the replacement. Restart running
Codex and Review sessions after applying a token. Cancelling the prompt leaves
the previous configuration untouched; the command remains available later.

VS Code reuses its saved token on subsequent connections. SecretStorage does
not sync secrets between devices: when you connect from a different VS Code
client, enter the current token in that client's prompt. Tokens are scoped to
the Headroom endpoint so different proxies do not share credentials.

The existing helper applies the header to `~/.codex/config.toml` and
`~/.omp/profiles/review/agent/models.yml`, with mode `0600`. These runtime copies
remain in the container's persisted home volume so CLI clients can use them.
Existing model settings, other providers, and login files are preserved;
Codex's active provider becomes `headroom`. The extension never puts the token
in workspace settings, terminal commands, process arguments, or output logs.

The bootstrap packages the dependency-free extension from `.vscode/headroom`
into `~/.cache/headroom/work-jatt-headroom.vsix`; Devsy installs it alongside
Josh Room through the existing VSIX lifecycle. It activates only in a trusted
remote workspace. Python 3 installed by the bootstrap packages the VSIX; no npm
installation or Marketplace publication is needed.

Existing `HEADROOM_PROXY_TOKEN` environment injection and the helper's terminal
prompt remain available for automation. If no token is available during
bootstrap, the IDE still starts so VS Code can ask for it after connecting.
Runtime checks report configuration only, not an authenticated request.
