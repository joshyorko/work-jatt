#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo '==> Installing GitHub CLI and gocryptfs'
brew install gh gocryptfs
