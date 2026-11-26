# Work-Jatt Webtop

This opt-in profile runs Omarchy Webtop on a Linux Docker host with an
accessible DRM render node under `/dev/dri` and a standard clone of Work-Jatt.
It pulls the public Webtop image
if missing. The default tag is `ghcr.io/joshyorko/webtop-os:latest`.
Set `WEBTOP_IMAGE` to a specific published digest or a locally loaded candidate
tag to select another image.

On a GPU-less Linux VM, enable its `vkms` kernel module and set
`WEBTOP_RENDER_NODE` to the resulting `/dev/dri/card*` device in the private
profile `.env`, with `WEBTOP_SOFTWARE_RENDERING=1`. The VM needs a working DRM
allocator even when Mesa renders on the CPU; an HTTP response alone does not
prove that the nested Hyprland desktop started.

Harvester's `default/ubuntu-docker-webtop-v1` cloud-init template extends
`default/ubuntu-docker` with persistent `vkms` and `vgem` module loading.
It uses `bind9-dnsutils` on current Ubuntu images and fits KubeVirt's 2 KiB
inline user-data limit. The profile's `initializeCommand` creates a private
`.env` on first launch and automatically selects the VKMS card for software
rendering when present. Existing `.env` settings are preserved.
Devsy selects this template
with `HARVESTER_CLOUD_INIT_TEMPLATE=default/ubuntu-docker-webtop-v1`; cloud-init
changes apply to newly created VMs, not existing machines.

### Launch and change settings

From the Work-Jatt checkout on the Docker host:

```bash
profile=.devcontainer/webtop
checkout=$(pwd -P)
checkout_id=$(printf '%s' "$checkout" | sha256sum | cut -c1-12)
if [ ! -e "$profile/.env" ]; then
  (
    umask 077
    set -C
    {
      printf 'WEBTOP_PROJECT_NAME=work-jatt-webtop-%s\n' "$checkout_id"
      printf 'WEBTOP_WORKSPACE_DIR=%s\n' "$checkout"
      printf 'WEBTOP_PUID=%s\nWEBTOP_PGID=%s\n' "$(id -u)" "$(id -g)"
      cat "$profile/.env.example"
    } > "$profile/.env"
  )
fi
docker compose -f "$profile/compose.yaml" up -d
```

Open `http://localhost:13000` or `https://localhost:13001` on that host.
For a remote Docker host, use SSH local port forwarding to those loopback
ports. Edit the private `.env` to change the image, ports, desktop alias or
Git defaults. Run the same `up` command again to apply the changes. Pull
explicitly when you want a newer image at the same tag. Compose scopes the
`/config` volume to the project in `WEBTOP_PROJECT_NAME`. Keep that name
fixed across replacements and stop the profile before switching launchers.

For a second checkout or a disposable test, run the setup in that checkout
and set different HTTP and HTTPS ports in its `.env` before launch. If you
already made a profile `.env`, add the checkout-specific project name and
absolute workspace directory shown in the setup. Update the workspace
directory if you move the checkout.

Keep `WEBTOP_PUID` and `WEBTOP_PGID` aligned with the checkout owner and
stable for the life of the volume. Dev Containers enters as `abc`, the image's
canonical user. `WEBTOP_USER` adds an alias for the same UID, groups and
`/config` home. Git defaults apply at system scope. User and repository
settings take precedence.

### Edit tracked extensions live

Start with the extra Compose file:

```bash
docker compose -f "$profile/compose.yaml" -f "$profile/compose.extensions.yaml" up -d
git status --short -- "$profile/extensions"
```

Edit `/webtop-extensions` in the desktop or
`.devcontainer/webtop/extensions/` in the checkout. For example, add a PNG in
`backgrounds/tokyo-night/`, run `webtop-link-extensions` in the desktop terminal
and select it with `omarchy-theme-bg-switcher`. Existing filenames can be
edited in place. Reopen the picker to see new bytes. Keep the bind enabled
when the active wallpaper lives in it. Git sees these changes and the named
volume continues to hold the private desktop profile.

For the Dev Container CLI, use the standard profile or enable the extra
Compose file with a private config:

```bash
config="$PWD/$profile/devcontainer.json"
jq '.dockerComposeFile = ["compose.yaml", "compose.extensions.yaml"]' \
  "$config" > "$profile/devcontainer.local.json"
config="$PWD/$profile/devcontainer.local.json"
```

### Dev Containers and Devsy

The profile creates its private `.env` automatically on first launch and
preserves existing settings. VS Code forwards container port 3000.

In VS Code, select **Work-Jatt Webtop** from **Dev Containers: Reopen in
Container**. Compose publishes the loopback ports configured above. The
private extension config can be selected by the Dev Container CLI or Devsy.
Run from the Work-Jatt checkout and set `config` to that file when using the
live bind.

```bash
config=${config:-$PWD/$profile/devcontainer.json}
devcontainer up --workspace-folder "$PWD" --config "$config"
devcontainer exec --workspace-folder "$PWD" --config "$config" sh -ec '
  test "$(getent passwd abc | cut -d: -f6)" = /config
  test "$(id -u)" = "${PUID:-1000}"
  test "$(id -u "${WEBTOP_USER:-kdlocpanda}")" = "$(id -u)"
  test -w /config
  test "$(git config --file /etc/webtop-gitconfig user.name)" = "$WEBTOP_GIT_NAME"
  test "$(git rev-parse --show-toplevel)" = /workspaces/work-jatt
  test -w .
  ls /dev/dri/renderD*
'
```

After changing settings, use `devcontainer up --remove-existing-container`
with the same workspace and config arguments to recreate the container.
From the launch shell, probe the configured host port after startup:

```bash
endpoint=$(docker compose -f "$profile/compose.yaml" port webtop 3000)
curl -fsS -o /dev/null "http://$endpoint/"
```

Use an existing local Docker provider named `docker` for Devsy. Set a unique
workspace ID per checkout. To use the live bind, pass the private profile
path instead of `id:webtop`. Add `--recreate` to apply settings changes.

```bash
devsy --provider docker workspace up --id work-jatt-webtop \
  --devcontainer id:webtop --ide-launch skip --ssh-configure=false .
devsy --provider docker workspace ssh work-jatt-webtop \
  --workdir /workspaces/work-jatt --command '
    set -e
    test "$(id -u)" = "${PUID:-1000}"
    test "$(id -u "${WEBTOP_USER:-kdlocpanda}")" = "$(id -u)"
    test "$(getent passwd abc | cut -d: -f6)" = /config
    test -w /config
    test "$(git config --file /etc/webtop-gitconfig user.name)" = "$WEBTOP_GIT_NAME"
    test "$(git rev-parse --show-toplevel)" = /workspaces/work-jatt
    test -w .
    ls /dev/dri/renderD*
  '
```
