#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo '==> Trusting Review formula'
brew trust --formula joshyorko/tools/review
# Let install fetch the tap without explicit tap's cross-platform validation
# of unrelated formulae and casks. Bootstrap already disables auto-updates.

echo '==> Installing stable Review package'
brew install joshyorko/tools/review
