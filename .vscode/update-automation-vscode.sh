#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo 'Usage: bash .vscode/update-automation-vscode.sh RELEASE_TAG CHECKSUM_MANIFEST_ASSET' >&2
  exit 1
fi
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../.devcontainer/scripts/automation-vscode-common.sh"
TAG="$1"
VERSION="${TAG#automation-vscode-v}"
ASSET="automation-vscode-${VERSION}-linux-x64.vsix"
MANIFEST="$2"
# Validate before any network call; the digest is filled from the manifest below.
EXPECTED_SHA256="$(printf '%064d' 0)"
validate_automation_coordinates
if [[ ! "${MANIFEST}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo 'ERROR: expected a checksum manifest asset basename.' >&2
  exit 1
fi
PIN_FILE="${SCRIPT_DIR}/../.devcontainer/automation-vscode.env"
work="$(mktemp -d "${PIN_FILE}.update.XXXXXX")"
trap 'rm -rf -- "${work}"' EXIT

download_automation_asset "${TAG}" "${MANIFEST}" "${work}/checksums"
EXPECTED_SHA256="$(awk -v asset="${ASSET}" '{ name=$2; sub(/^\*/, "", name); if (name == asset && NF == 2) print $1 }' "${work}/checksums")"
validate_automation_coordinates
printf 'VERSION="%s"\nTAG="%s"\nASSET="%s"\nEXPECTED_SHA256="%s"\n' \
  "${VERSION}" "${TAG}" "${ASSET}" "${EXPECTED_SHA256}" > "${work}/pin"
AUTOMATION_VSCODE_PIN_FILE="${work}/pin" /bin/bash "${SCRIPT_DIR}/../.devcontainer/scripts/stage-automation-vscode.sh"
chmod 0644 "${work}/pin"
mv -f "${work}/pin" "${PIN_FILE}"
echo "Pinned Automation VS Code ${VERSION}."
echo 'After attaching to VS Code, run: sh .vscode/install-automation-vscode.sh'
