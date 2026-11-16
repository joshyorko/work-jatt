#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/automation-vscode-common.sh"
load_automation_pin "${AUTOMATION_VSCODE_PIN_FILE:-${SCRIPT_DIR}/../automation-vscode.env}"
CACHE_DIR="${AUTOMATION_VSCODE_CACHE_DIR:-${HOME}/.cache/automation-vscode}"
VSIX="${CACHE_DIR}/${ASSET}"
STABLE_VSIX="${CACHE_DIR}/automation-vscode.vsix"

sha256_for() {
  local file="$1"

  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${file}" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${file}" | awk '{print $1}'
  else
    echo 'ERROR: sha256sum or shasum is required to verify Automation VS Code.' >&2
    return 1
  fi
}

stage_stable_vsix() {
  if [ -f "${STABLE_VSIX}" ] && [ "$(sha256_for "${STABLE_VSIX}")" = "${EXPECTED_SHA256}" ]; then
    return
  fi
  tmp="$(mktemp "${CACHE_DIR}/.automation-vscode-stable.XXXXXX")"
  trap 'rm -f "${tmp}"' EXIT
  cp "${VSIX}" "${tmp}"
  chmod 0644 "${tmp}"
  mv -f "${tmp}" "${STABLE_VSIX}"
  trap - EXIT
}

mkdir -p "${CACHE_DIR}"

if [ -f "${VSIX}" ] && [ "$(sha256_for "${VSIX}")" = "${EXPECTED_SHA256}" ]; then
  echo "Automation VS Code ${VERSION} VSIX is already staged at ${VSIX}."
  stage_stable_vsix
  exit 0
fi

tmp="$(mktemp "${CACHE_DIR}/.automation-vscode-${VERSION}.XXXXXX")"
cleanup() {
  rm -f "${tmp}"
}
trap cleanup EXIT

echo "==> Downloading Automation VS Code ${VERSION} VSIX"
download_automation_asset "${TAG}" "${ASSET}" "${tmp}"

actual_sha256="$(sha256_for "${tmp}")"
if [ "${actual_sha256}" != "${EXPECTED_SHA256}" ]; then
  echo 'ERROR: Automation VS Code VSIX checksum verification failed.' >&2
  echo "       expected: ${EXPECTED_SHA256}" >&2
  echo "       actual:   ${actual_sha256}" >&2
  exit 1
fi

chmod 0644 "${tmp}"
mv -f "${tmp}" "${VSIX}"
trap - EXIT

stage_stable_vsix
echo "Staged Automation VS Code ${VERSION} VSIX at ${VSIX}."
