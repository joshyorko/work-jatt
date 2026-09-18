#!/usr/bin/env bash
set -euo pipefail

export PATH="/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/install-review-tools.sh"
"${SCRIPT_DIR}/install-review-package.sh"
"${SCRIPT_DIR}/prepare-review-source.sh"
"${SCRIPT_DIR}/build-fuse2fs.sh"
"${SCRIPT_DIR}/check-review-runtime.sh"
