#!/usr/bin/env bash
set -euo pipefail

VERSION="0.1.24"
URL="https://github.com/joshyorko/josh-room/releases/download/v${VERSION}-standalone-vsix/josh-room-${VERSION}.vsix"
EXPECTED_SHA256="c2768bf96edf70f4cd8b187754d89d6ea84a59afb7634224a6830873b0e48e7d"
CACHE_DIR="/home/vscode/.cache/josh-room"
VSIX="${CACHE_DIR}/josh-room-${VERSION}.vsix"

sha256_for() {
  local file="$1"

  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${file}" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${file}" | awk '{print $1}'
  else
    echo 'ERROR: sha256sum or shasum is required to verify Josh Room.' >&2
    return 1
  fi
}

mkdir -p "${CACHE_DIR}"

if [ -f "${VSIX}" ] && [ "$(sha256_for "${VSIX}")" = "${EXPECTED_SHA256}" ]; then
  echo "Josh Room ${VERSION} VSIX is already staged at ${VSIX}."
  exit 0
fi

command -v curl >/dev/null 2>&1 || {
  echo 'ERROR: curl is required to stage Josh Room.' >&2
  exit 1
}

tmp="$(mktemp "${CACHE_DIR}/.josh-room-${VERSION}.XXXXXX")"
cleanup() {
  rm -f "${tmp}"
}
trap cleanup EXIT

echo "==> Downloading Josh Room ${VERSION} VSIX"
curl --fail --location --silent --show-error --output "${tmp}" "${URL}"

actual_sha256="$(sha256_for "${tmp}")"
if [ "${actual_sha256}" != "${EXPECTED_SHA256}" ]; then
  echo 'ERROR: Josh Room VSIX checksum verification failed.' >&2
  echo "       expected: ${EXPECTED_SHA256}" >&2
  echo "       actual:   ${actual_sha256}" >&2
  exit 1
fi

chmod 0644 "${tmp}"
mv -f "${tmp}" "${VSIX}"
trap - EXIT

echo "Staged Josh Room ${VERSION} VSIX at ${VSIX}."
