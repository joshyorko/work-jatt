#!/usr/bin/env bash
# Never trace credentials, including when invoked from a traced parent shell.
set +x
set -euo pipefail
umask 077
export PATH="${HOME}/.local/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH}"

: "${HEADROOM_BASE_URL:?Set HEADROOM_BASE_URL before configuring Headroom}"
export HEADROOM_BASE_URL

CODEX_DIR="${CODEX_HOME:-${HOME}/.codex}"
CODEX_CONFIG="${CODEX_DIR}/config.toml"
OMP_DIR="${HOME}/.omp/profiles/review/agent"
OMP_CONFIG="${OMP_DIR}/models.yml"

case "${1:-}" in
  ''|--prompt) ;;
  *) echo 'Usage: bash .devcontainer/scripts/configure-headroom.sh [--prompt]' >&2; exit 2 ;;
esac

if ! command -v yq >/dev/null 2>&1; then
  echo 'ERROR: yq is required to configure Headroom.' >&2
  exit 1
fi

# Validate both inputs before replacing either. Parser diagnostics may contain
# existing credentials, so report only the failing path.
for config in "${CODEX_CONFIG}" "${OMP_CONFIG}"; do
  if [ -f "${config}" ]; then
    format=yaml
    [ "${config}" != "${CODEX_CONFIG}" ] || format=toml
    if ! yq -p "${format}" '.' "${config}" >/dev/null 2>&1; then
      echo "ERROR: cannot parse Headroom configuration: ${config}" >&2
      exit 1
    fi
  fi
done

if [ "${1:-}" = --prompt ]; then
  if ! IFS= read -r -s -p 'Headroom proxy token: ' HEADROOM_PROXY_TOKEN; then
    printf '\nERROR: could not read the Headroom proxy token.\n' >&2
    exit 1
  fi
  printf '\n' >&2
  if [ -z "${HEADROOM_PROXY_TOKEN}" ]; then
    echo 'ERROR: the Headroom proxy token cannot be empty.' >&2
    exit 1
  fi
elif [ -z "${HEADROOM_PROXY_TOKEN:-}" ] && [ -f "${CODEX_CONFIG}" ]; then
  HEADROOM_PROXY_TOKEN="$(yq -p toml -r '.model_providers.headroom.http_headers."X-Headroom-Proxy-Token" // ""' "${CODEX_CONFIG}" 2>/dev/null)"
fi

if [ -z "${HEADROOM_PROXY_TOKEN:-}" ]; then
  echo 'Headroom authentication is not configured. The IDE can still start.'
  echo 'Connect with VS Code to enter the token in the Headroom prompt.'
  echo 'To change it later, use Headroom: Update Proxy Token in the Command Palette.'
  exit 0
fi

# OMP interprets a leading ! as a shell command; HTTP headers forbid newlines.
case "${HEADROOM_PROXY_TOKEN}" in
  '!'*|*$'\r'*|*$'\n'*) echo 'ERROR: invalid Headroom proxy token format.' >&2; exit 1 ;;
esac
export HEADROOM_PROXY_TOKEN

mkdir -p "${CODEX_DIR}" "${OMP_DIR}"
codex_temporary="$(mktemp "${CODEX_CONFIG}.tmp.XXXXXX")"
omp_temporary=''
cleanup() {
  rm -f -- "${codex_temporary}"
  [ -z "${omp_temporary}" ] || rm -f -- "${omp_temporary}"
}
trap cleanup EXIT
omp_temporary="$(mktemp "${OMP_CONFIG}.tmp.XXXXXX")"

codex_input=/dev/null
omp_input=/dev/null
[ ! -f "${CODEX_CONFIG}" ] || codex_input="${CODEX_CONFIG}"
[ ! -f "${OMP_CONFIG}" ] || omp_input="${OMP_CONFIG}"

if ! yq -p toml -o toml '
  .model_provider = "headroom" |
  .model_providers.headroom.name = "OpenAI" |
  .model_providers.headroom.base_url = strenv(HEADROOM_BASE_URL) |
  .model_providers.headroom.wire_api = "responses" |
  .model_providers.headroom.requires_openai_auth = true |
  .model_providers.headroom.http_headers."X-Headroom-Proxy-Token" = strenv(HEADROOM_PROXY_TOKEN)
' "${codex_input}" > "${codex_temporary}" 2>/dev/null ||
   ! yq '
  .providers."openai-codex".baseUrl = strenv(HEADROOM_BASE_URL) |
  .providers."openai-codex".headers."X-Headroom-Proxy-Token" = strenv(HEADROOM_PROXY_TOKEN)
' "${omp_input}" > "${omp_temporary}" 2>/dev/null; then
  echo 'ERROR: cannot update Headroom configuration; existing files were preserved.' >&2
  exit 1
fi

mv -- "${codex_temporary}" "${CODEX_CONFIG}"
mv -- "${omp_temporary}" "${OMP_CONFIG}"
trap - EXIT
echo 'Headroom headers configured for Codex and Review OMP (private files).'
echo 'Restart running Codex and Review sessions to load the updated configuration.'
