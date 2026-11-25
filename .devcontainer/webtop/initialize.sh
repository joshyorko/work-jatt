#!/usr/bin/env bash
set -euo pipefail

checkout=$(cd -- "${1:?Pass the checkout directory}" && pwd -P)
profile=$checkout/.devcontainer/webtop
[[ ! -e $profile/.env ]] || exit 0
umask 077
settings=$(mktemp "$profile/.env.XXXXXX")
trap 'rm -f -- "$settings"' EXIT
{
  printf 'WEBTOP_PROJECT_NAME=work-jatt-webtop-%s\n' "$(printf '%s' "$checkout" | sha256sum | cut -c1-12)"
  printf 'WEBTOP_WORKSPACE_DIR=%s\n' "$checkout"
  printf 'WEBTOP_PUID=1000\nWEBTOP_PGID=1000\n'
  cat "$profile/.env.example"
  # VKMS needs an explicit DRM card; the vgem render node is not a renderer.
  for card in /sys/class/drm/card[0-9]*; do
    case "${card##*/}" in *-*) continue ;; esac
    device=$(readlink -f "$card/device" || true)
    driver=$(readlink -f "$card/device/driver" || true)
    if [[ ${device##*/} == vkms || ${driver##*/} == vkms ]]; then
      printf '\nWEBTOP_RENDER_NODE=/dev/dri/%s\nWEBTOP_SOFTWARE_RENDERING=1\n' "${card##*/}"
      break
    fi
  done
} > "$settings"
# Publish once without overwriting operator settings if two launchers race.
ln "$settings" "$profile/.env" 2>/dev/null || [[ -e $profile/.env ]]
