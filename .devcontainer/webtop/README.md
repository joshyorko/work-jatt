# Work-Jatt Webtop devcontainer

This opt-in profile runs the published Webtop image on a Docker host with
`/dev/dri`. The `work-jatt` image tag is pending the integrated browser test
and publication. Set `WEBTOP_IMAGE` to a tested local image for prepublication
validation.

Copy `.devcontainer/webtop/.env.example` to `.devcontainer/webtop/.env` to
customize the image, ports, host UID/GID, and desktop Git identity. Keep
`WEBTOP_USER` aligned with `remoteUser` in `devcontainer.json`.

From the Work-Jatt checkout, select this profile with either CLI.

```sh
devcontainer up --workspace-folder . --config .devcontainer/webtop/devcontainer.json
devsy workspace up --provider docker --devcontainer id:webtop .
```

Open <http://localhost:3010> on the Docker host or use the editor's forwarded
port. The editor and desktop share the Work-Jatt checkout. A named volume
keeps the Webtop home across container replacements.
