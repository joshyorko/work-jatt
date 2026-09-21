#!/usr/bin/env bash
set -euo pipefail

: "${HEADROOM_BASE_URL:?Set HEADROOM_BASE_URL before enabling the Headroom OMP profile}"

AGENT_DIR="${HOME}/.omp/profiles/review/agent"
MODELS_FILE="${AGENT_DIR}/models.yml"

echo '==> Configuring shared Review OMP profile for Headroom'
mkdir -p "${AGENT_DIR}"

if [ ! -f "${MODELS_FILE}" ]; then
  printf 'providers:\n  openai-codex:\n    baseUrl: %s\n' "${HEADROOM_BASE_URL}" > "${MODELS_FILE}"
else
  echo "OMP models config already exists: ${MODELS_FILE}"
fi