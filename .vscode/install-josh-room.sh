#!/usr/bin/env sh
set -u

VERSION="0.1.24"
URL="https://github.com/joshyorko/josh-room/releases/download/v${VERSION}-standalone-vsix/josh-room-${VERSION}.vsix"
EXPECTED_SHA256="c2768bf96edf70f4cd8b187754d89d6ea84a59afb7634224a6830873b0e48e7d"
VSIX="${TMPDIR:-/tmp}/josh-room-${VERSION}.vsix"

# Prefer code-insiders: in this dev container its shim installs into the
# running VS Code Insiders server, which is where the extension must live.
if command -v code-insiders >/dev/null 2>&1; then
  CODE="code-insiders"
elif command -v code >/dev/null 2>&1; then
  CODE="code"
else
  # No editor server attached yet (e.g. run via bare `devcontainer` CLI) - not fatal.
  echo "VS Code CLI (code-insiders or code) was not found on PATH; skipping Josh Room install." >&2
  exit 0
fi

echo "Using VS Code CLI: $CODE ($(command -v "$CODE"))"

if "$CODE" --list-extensions --show-versions 2>/dev/null | grep -qx "joshyorko.josh-room@${VERSION}"; then
  echo "Josh Room ${VERSION} is already installed."
  exit 0
fi

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

"$CODE" --install-extension "$VSIX" --force
rm -f "$VSIX"
echo "Installed Josh Room ${VERSION} from GitHub."