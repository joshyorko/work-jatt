#!/usr/bin/env bash
set -euo pipefail

REVIEW_DIR="${HOME}/src/review"

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo '==> Preparing Review source checkout from upstream main'
mkdir -p "${HOME}/src"
if [ ! -d "${REVIEW_DIR}/.git" ]; then
  git clone https://github.com/joshyorko/review.git "${REVIEW_DIR}"
fi

cd "${REVIEW_DIR}"
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream https://github.com/projectbluefin/review.git
git fetch upstream main
git switch -C main upstream/main
