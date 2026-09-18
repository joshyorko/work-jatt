#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

printf '\n=== Review source ===\n'
git -C "${HOME}/src/review" log -1 --oneline
printf '\n=== Installed Review package ===\n'
brew list --versions joshyorko/review-dev/bluefin-review-dev
printf '\n=== Review runtime ===\n'
command -v gh
command -v apptainer
command -v squashfuse
command -v gocryptfs
command -v fuse2fs
command -v bluefin
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
