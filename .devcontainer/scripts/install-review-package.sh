#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo '==> Trusting Josh Review dev tap'
brew trust --tap joshyorko/review-dev
brew tap joshyorko/review-dev
brew update

echo '==> Installing latest Bluefin Review dev package'
brew install -y joshyorko/review-dev/bluefin-review-dev
