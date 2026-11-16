#!/usr/bin/env bash
# Shared by staging and the explicit-release updater; never stores credentials.
AUTOMATION_REPOSITORY="automation-control-plane/automation-vscode"

validate_automation_coordinates() {
  if [[ ! "${VERSION:-}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
     [[ "${TAG:-}" != "automation-vscode-v${VERSION}" ]] ||
     [[ "${ASSET:-}" != "automation-vscode-${VERSION}-linux-x64.vsix" ]] ||
     [[ ! "${EXPECTED_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]; then
    echo 'ERROR: Automation VS Code requires a verified published Linux x64 release pin.' >&2
    return 1
  fi
  if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
    echo 'ERROR: The pinned Automation VS Code VSIX supports Linux x64 only.' >&2
    return 1
  fi
}

load_automation_pin() {
  source "$1"
  validate_automation_coordinates
}

download_automation_asset() {
  local tag="$1" asset="$2" output="$3" directory
  # Public release downloads need no login. Private releases use the operator's
  # existing gh authentication without copying tokens into files or arguments.
  if curl --fail --location --silent --show-error --output "${output}" \
      "https://github.com/${AUTOMATION_REPOSITORY}/releases/download/${tag}/${asset}"; then
    return 0
  fi
  if command -v gh >/dev/null 2>&1; then
    directory="$(mktemp -d "${output}.download.XXXXXX")" || return 1
    if GH_PROMPT_DISABLED=1 gh release download "${tag}" \
        --repo "${AUTOMATION_REPOSITORY}" --pattern "${asset}" --dir "${directory}" &&
        [[ -f "${directory}/${asset}" ]]; then
      mv -f "${directory}/${asset}" "${output}"
      rmdir "${directory}"
      return 0
    fi
    rm -rf -- "${directory}"
  fi
  echo "ERROR: Could not download ${asset}. For private releases, authenticate gh with access to ${AUTOMATION_REPOSITORY} and retry." >&2
  return 1
}
