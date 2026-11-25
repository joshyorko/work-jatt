# Work-Jatt Webtop

This opt-in profile runs Omarchy Webtop on a Linux Docker host with an
accessible DRM render node under `/dev/dri`. It pulls the public Webtop image
if missing. The default tag is `ghcr.io/joshyorko/webtop-os:work-jatt-dogfood`.
The dogfood tag is pending publication. Set `WEBTOP_IMAGE` to a locally loaded
candidate tag for prepublication testing.

### Launch and change settings

From the Work-Jatt checkout on the Docker host:

```bash
profile=.devcontainer/webtop
test -e "$profile/.env" || install -m 0600 "$profile/.env.example" "$profile/.env"
export COMPOSE_ENV_FILES="$PWD/$profile/.env"
docker compose -f "$profile/compose.yaml" up -d
```

Open `http://localhost:13000` or `https://localhost:13001` on that host.
For a remote Docker host, use SSH local port forwarding to those loopback
ports. Edit the private `.env` to change the image, ports, desktop alias or
Git defaults. Run the same `up` command again to apply the changes. Pull
explicitly when you want a newer image at the same tag. The named volume
`work-jatt-webtop-config` retains `/config` across replacements. Keep its
name fixed for a given profile and stop that profile before switching
launchers. Set `WEBTOP_CONFIG_VOLUME` to a unique name for a disposable test.

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
`backgrounds/tokyo-night/`, run `webtop-link-wallpapers` in the desktop terminal
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

In VS Code, select **Work-Jatt Webtop** from **Dev Containers: Reopen in
Container**. For the Dev Container CLI, run from the same launch shell used
above. Set `config` to the private profile when using the live bind.

```bash
config=${config:-$PWD/$profile/devcontainer.json}
devcontainer up --workspace-folder "$PWD" --config "$config"
devcontainer exec --workspace-folder "$PWD" --config "$config" sh -ec '
  test "$(getent passwd abc | cut -d: -f6)" = /config
  test "$(id -u)" = "$(id -u abc)"
  test "$(id -u "${WEBTOP_USER:-kdlocpanda}")" = "$(id -u)"
  test "$(git rev-parse --show-toplevel)" = /workspaces/work-jatt
  test -w .
  ls /dev/dri/renderD*
'
```

After changing settings, use `devcontainer up --remove-existing-container`
with the same workspace and config arguments to recreate the container.
From the launch shell, probe on the configured host port with
`curl -fsS -o /dev/null http://127.0.0.1:13000/` after startup.

Use an existing local Docker provider named `docker` for Devsy. Run these
commands from the launch shell with `COMPOSE_ENV_FILES` exported:

```bash
devsy --provider docker workspace up --id work-jatt-webtop \
  --devcontainer id:webtop --ide-launch skip --ssh-configure=false .
devsy --provider docker workspace ssh work-jatt-webtop \
  --workdir /workspaces/work-jatt --command '
    set -e
    test "$(id -u)" = "$(id -u abc)"
    test "$(getent passwd abc | cut -d: -f6)" = /config
    test "$(git rev-parse --show-toplevel)" = /workspaces/work-jatt
    test -w .
    ls /dev/dri/renderD*
  '
```
