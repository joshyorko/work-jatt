#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

require_command() {
  local command_name="$1"

  if command -v "${command_name}" >/dev/null 2>&1; then
    printf '%-12s %s\n' "${command_name}:" "$(command -v "${command_name}")"
  else
    echo "ERROR: required Review runtime command is missing: ${command_name}" >&2
    return 1
  fi
}

printf '\n=== Review source ===\n'
git -C "${HOME}/src/review" log -1 --oneline
printf '\n=== Installed Review package ===\n'
brew list --versions joshyorko/review-dev/bluefin-review-dev
printf '\n=== Review runtime ===\n'
require_command gh
require_command apptainer
require_command squashfuse
require_command gocryptfs
require_command fuse2fs
require_command bluefin
printf '\n'
if [ -e /dev/fuse ]; then
  echo '/dev/fuse: READY'
else
  echo 'WARNING: /dev/fuse is missing'
fi
if [ -e /dev/kvm ]; then
  echo '/dev/kvm: READY'
else
  echo 'WARNING: /dev/kvm is missing'
fi
printf '\nBootstrap complete.\n'
echo 'Next: gh auth login'
echo 'Review source: ~/src/review (upstream/main)'
echo 'Run: bluefin review projectbluefin/review'
