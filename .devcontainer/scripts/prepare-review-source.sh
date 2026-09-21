#!/usr/bin/env bash
set -euo pipefail

REVIEW_DIR="${HOME}/src/review"
UPSTREAM_REF="${REVIEW_UPSTREAM_REF:-main}"

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo "==> Preparing Review source checkout from upstream ${UPSTREAM_REF}"
mkdir -p "${HOME}/src"
if [ ! -d "${REVIEW_DIR}/.git" ]; then
  git clone https://github.com/joshyorko/review.git "${REVIEW_DIR}"
fi

cd "${REVIEW_DIR}"
git remote get-url upstream >/dev/null 2>&1 || git remote add upstream https://github.com/projectbluefin/review.git
git fetch upstream "${UPSTREAM_REF}"

if [ -n "$(git status --porcelain)" ]; then
  echo 'ERROR: Review source has local changes; refusing to switch or update it.' >&2
  echo "       Commit, stash, or remove changes in ${REVIEW_DIR} and rerun bootstrap." >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/${UPSTREAM_REF}"; then
  git switch "${UPSTREAM_REF}"
  if ! git merge --ff-only "upstream/${UPSTREAM_REF}"; then
    echo "ERROR: local ${UPSTREAM_REF} has diverged from upstream/${UPSTREAM_REF}; refusing to reset it." >&2
    echo "       Reconcile the branches in ${REVIEW_DIR} and rerun bootstrap." >&2
    exit 1
  fi
else
  git switch -c "${UPSTREAM_REF}" --track "upstream/${UPSTREAM_REF}"
fi
