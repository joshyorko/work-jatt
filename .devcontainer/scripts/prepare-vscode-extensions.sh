#!/usr/bin/env bash
set -euo pipefail

# Startup hooks and the manual installer must use the same extension ownership.
if [ "$(id -u)" -eq 0 ]; then
  target_user="${_REMOTE_USER:-${SUDO_USER:-vscode}}"
  passwd_entry="$(getent passwd "${target_user}")"
  IFS=: read -r _ _ target_uid target_gid _ target_home _ <<< "${passwd_entry}"
  if [ "${target_uid}" -eq 0 ]; then
    echo 'ERROR: run extension preparation for the non-root remote user.' >&2
    exit 1
  fi
else
  target_uid="$(id -u)"
  target_gid="$(id -g)"
  target_home="${HOME}"
fi
target_home="$(cd -- "${target_home}" && pwd -P)"

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo -n "$@"; then
    return 0
  else
    echo 'ERROR: repairing VS Code extension ownership requires root or passwordless sudo. Run this helper as the remote user with sudo available.' >&2
    return 1
  fi
}

refuse_symlink() {
  if [ -L "$1" ]; then
    echo "ERROR: refusing symlinked VS Code extension path: $1" >&2
    exit 1
  fi
}

umask 077
for server in .vscode-server .vscode-server-insiders; do
  server_dir="${target_home}/${server}"
  extensions_dir="${server_dir}/extensions"
  refuse_symlink "${server_dir}"
  mkdir -p -- "${server_dir}"
  if [ "$(stat -c '%u:%g' -- "${server_dir}")" != "${target_uid}:${target_gid}" ]; then
    as_root chown -h -- "${target_uid}:${target_gid}" "${server_dir}"
  fi
  refuse_symlink "${extensions_dir}"
  mkdir -p -- "${extensions_dir}"
  # find -P and chown -h leave targets of nested symlinks untouched. Existing
  # private modes are retained, including root-created 0700 directories.
  if ! misowned="$(find -P "${extensions_dir}" \( ! -uid "${target_uid}" -o ! -gid "${target_gid}" \) -print -quit)" || [ -n "${misowned}" ]; then
    as_root find -P "${extensions_dir}" \( ! -uid "${target_uid}" -o ! -gid "${target_gid}" \) -exec chown -h -- "${target_uid}:${target_gid}" '{}' +
  fi
done
