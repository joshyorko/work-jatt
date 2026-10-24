#!/usr/bin/env bash
set -euo pipefail

REVIEW_DIR="${HOME}/src/review"
UPSTREAM_REF="${REVIEW_UPSTREAM_REF:-main}"
UPSTREAM_URL="https://github.com/joshyorko/review.git"

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

echo "==> Preparing Review source checkout from upstream ${UPSTREAM_REF}"
mkdir -p "${HOME}/src"
checkout_exists=0
incompatible_checkout=0
if [ -e "${REVIEW_DIR}" ]; then
  checkout_exists=1
  if [ -d "${REVIEW_DIR}/.git" ]; then
    cd "${REVIEW_DIR}"
    compatible_remote=0
    for remote in origin upstream; do
      if remote_url="$(git remote get-url "${remote}" 2>/dev/null)"; then
        if [ "${remote_url}" = "${UPSTREAM_URL}" ]; then
          compatible_remote=1
        else
          incompatible_checkout=1
        fi
      fi
    done
    if [ "${compatible_remote}" -eq 0 ]; then
      incompatible_checkout=1
    fi
  else
    incompatible_checkout=1
  fi
fi

preserve_and_clone() {
  local fresh_dir backup_dir suffix
  fresh_dir="$(mktemp -d "${HOME}/src/.review-fresh.XXXXXX")"
  rmdir "${fresh_dir}"
  if ! git clone --branch "${UPSTREAM_REF}" --single-branch "${UPSTREAM_URL}" "${fresh_dir}"; then
    echo 'ERROR: could not clone a clean Review checkout; the existing source was left untouched.' >&2
    return 1
  fi

  suffix="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="${REVIEW_DIR}.preserved.${suffix}"
  while [ -e "${backup_dir}" ]; do
    suffix="${suffix}.1"
    backup_dir="${REVIEW_DIR}.preserved.${suffix}"
  done
  if [ -e "${REVIEW_DIR}" ]; then
    mv "${REVIEW_DIR}" "${backup_dir}"
  fi
  if ! mv "${fresh_dir}" "${REVIEW_DIR}"; then
    if [ -e "${backup_dir}" ] && [ ! -e "${REVIEW_DIR}" ]; then
      mv "${backup_dir}" "${REVIEW_DIR}"
    fi
    echo 'ERROR: could not install the clean Review checkout; preserved source remains available.' >&2
    return 1
  fi
  if [ -e "${backup_dir}" ]; then
    echo "==> Preserved the previous Review checkout at ${backup_dir}"
  fi
}

if [ "${checkout_exists}" -eq 0 ]; then
  git clone --branch "${UPSTREAM_REF}" --single-branch "${UPSTREAM_URL}" "${REVIEW_DIR}"
elif [ "${incompatible_checkout}" -eq 1 ]; then
  echo '==> Existing Review checkout has an incompatible remote; preserving it before migration.'
  preserve_and_clone
fi

cd "${REVIEW_DIR}"
if ! git remote get-url upstream >/dev/null 2>&1; then
  git remote add upstream "${UPSTREAM_URL}"
fi
git fetch upstream "${UPSTREAM_REF}"

if ! git merge-base HEAD "upstream/${UPSTREAM_REF}" >/dev/null 2>&1; then
  echo '==> Existing Review checkout has unrelated Git history; preserving it before migration.'
  preserve_and_clone
  cd "${REVIEW_DIR}"
  git remote add upstream "${UPSTREAM_URL}"
  git fetch upstream "${UPSTREAM_REF}"
fi

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
