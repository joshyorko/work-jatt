#!/usr/bin/env sh
set -eu

VERSION="0.1.24"
URL="https://github.com/joshyorko/josh-room/releases/download/v${VERSION}-standalone-vsix/josh-room-${VERSION}.vsix"
EXPECTED_SHA256="c2768bf96edf70f4cd8b187754d89d6ea84a59afb7634224a6830873b0e48e7d"
VSIX="${TMPDIR:-/tmp}/josh-room-${VERSION}.vsix"

CODE_CLIS=""
if command -v code-insiders >/dev/null 2>&1; then
  CODE_CLIS="${CODE_CLIS} code-insiders"
fi
if command -v code >/dev/null 2>&1; then
  CODE_CLIS="${CODE_CLIS} code"
fi

if [ -z "${CODE_CLIS}" ]; then
  # No editor server attached yet (e.g. run via bare `devcontainer` CLI) - not fatal.
  echo "VS Code CLI (code-insiders or code) was not found on PATH; skipping Josh Room install." >&2
  exit 0
fi

for CODE in ${CODE_CLIS}; do
  echo "Checking VS Code CLI: ${CODE} ($(command -v "${CODE}"))"
  if "${CODE}" --list-extensions --show-versions 2>/dev/null | grep -qx "joshyorko.josh-room@${VERSION}"; then
    echo "Josh Room ${VERSION} is already installed."
    exit 0
  fi
done

command -v curl >/dev/null 2>&1 || {
  echo "curl is required to install Josh Room." >&2
  exit 1
}

curl --fail --location --silent --show-error --output "$VSIX" "$URL" || {
  echo "Failed to download Josh Room VSIX." >&2
  exit 1
}

if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL_SHA256="$(sha256sum "$VSIX" | awk '{print $1}')"
else
  ACTUAL_SHA256="$(shasum -a 256 "$VSIX" | awk '{print $1}')"
fi

if [ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]; then
  echo "Josh Room VSIX checksum verification failed." >&2
  rm -f "$VSIX"
  exit 1
fi

for CODE in ${CODE_CLIS}; do
  echo "Installing Josh Room ${VERSION} with ${CODE}."
  if "${CODE}" --install-extension "$VSIX" --force; then
    echo "Installed Josh Room ${VERSION} from GitHub using ${CODE}."
    exit 0
  fi
  echo "VS Code CLI ${CODE} could not install Josh Room; trying the next CLI." >&2
done

echo "Failed to install Josh Room with the available VS Code CLI(s)." >&2
exit 1