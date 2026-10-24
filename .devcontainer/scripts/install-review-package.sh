#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo '==> Trusting Josh tools tap'
brew trust --tap joshyorko/tools
brew tap joshyorko/tools
brew update

echo '==> Installing stable Review package'
brew install joshyorko/tools/review
